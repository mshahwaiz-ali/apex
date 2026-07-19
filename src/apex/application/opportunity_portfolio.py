"""Typed multi-opportunity portfolio contracts for the planv3 compatibility phase.

This module is intentionally additive.  It can represent the existing single-setup
assessment without changing live scan/analyze behavior, giving later batches a safe
contract boundary for multi-opportunity selection.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from apex.application.discovery_contracts import DiscoveryAssessment, DiscoverySetup
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus


class AnalysisMode(StrEnum):
    """Supported breadth/detail modes for the shared analysis engine."""

    SCAN_CMP_FIRST = "scan_cmp_first"
    ANALYZE_FULL = "analyze_full"


class SequenceRole(StrEnum):
    """Structural role of an opportunity within one symbol portfolio."""

    CURRENT = "current"
    NEARBY = "nearby"
    FOLLOW_UP = "follow_up"
    RUNNER = "runner"


def classify_setup_sequence_role(setup: DiscoverySetup) -> SequenceRole:
    """Classify a setup as current or nearby from canonical execution validity.

    This classifier intentionally preserves the existing validity decision. It does
    not reinterpret entry status, score, distance, or geometry. Later CMP-first work
    can evolve the canonical validity source without duplicating slot logic.
    """

    return SequenceRole.CURRENT if setup.execution_allowed_now else SequenceRole.NEARBY


class CmpZonePosition(StrEnum):
    """Raw CMP position relative to a setup's existing entry zone."""

    BELOW_ENTRY_ZONE = "below_entry_zone"
    INSIDE_ENTRY_ZONE = "inside_entry_zone"
    ABOVE_ENTRY_ZONE = "above_entry_zone"


class CmpLocationState(StrEnum):
    """Normalized CMP location for diagnostics and presentation only."""

    BELOW_ENTRY_ZONE = "below_entry_zone"
    INSIDE_ENTRY_ZONE = "inside_entry_zone"
    ABOVE_ENTRY_ZONE = "above_entry_zone"
    BEYOND_MAXIMUM_CHASE = "beyond_maximum_chase"


class CmpActionabilityState(StrEnum):
    """Diagnostic interpretation of existing CMP execution facts."""

    EXECUTABLE_AT_CMP = "executable_at_cmp"
    EXECUTION_GEOMETRY_CONFLICT = "execution_geometry_conflict"
    NEARBY_SETUP = "nearby_setup"
    CHASE_BREACHED = "chase_breached"
    INVALIDATED = "invalidated"


class TriggerFreshnessState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    FRESH = "fresh"
    STALE = "stale"
    BAR_EXPIRY_UNEVALUATED = "bar_expiry_unevaluated"
    CLOCK_SKEW = "clock_skew"


class StaleTriggerDiagnosticCode(StrEnum):
    EXPIRED_BY_SECONDS = "expired_by_seconds"
    EXECUTION_AUTHORIZED_AFTER_EXPIRY = "execution_authorized_after_expiry"
    BAR_EXPIRY_REQUIRES_CONTEXT = "bar_expiry_requires_context"
    EVALUATED_BEFORE_DECISION_TIME = "evaluated_before_decision_time"


@dataclass(frozen=True, slots=True)
class StaleTriggerDiagnostics:
    state: TriggerFreshnessState
    codes: tuple[StaleTriggerDiagnosticCode, ...]
    evaluated_at: datetime
    decision_time: datetime
    age_seconds: float
    setup_expiry_seconds: int | None
    setup_expiry_bars: int | None
    setup_expiry_reason: str
    execution_allowed_now: bool

    @property
    def is_stale(self) -> bool:
        return self.state is TriggerFreshnessState.STALE


class EntryBoundaryConsistencyCode(StrEnum):
    MAXIMUM_CHASE_EQUALS_IDEAL_ENTRY = "maximum_chase_equals_ideal_entry"
    CHASE_BREACHED_WITHOUT_LATE_STATUS = "chase_breached_without_late_status"
    LATE_STATUS_WITHOUT_CHASE_BREACH = "late_status_without_chase_breach"


@dataclass(frozen=True, slots=True)
class EntryBoundaryConsistencyAudit:
    codes: tuple[EntryBoundaryConsistencyCode, ...]
    ideal_entry_inside_zone: bool
    maximum_chase_directionally_valid: bool
    maximum_chase_equals_ideal_entry: bool
    beyond_maximum_chase: bool
    source_entry_status: EntryStatus

    @property
    def is_consistent(self) -> bool:
        return not self.codes


class SetupExistenceState(StrEnum):
    STRUCTURALLY_VALID = "structurally_valid"
    INVALIDATED = "invalidated"


class CmpEntryAssessmentState(StrEnum):
    AVAILABLE_NOW = "available_now"
    AVAILABLE_BUT_POOR_LOCATION = "available_but_poor_location"
    NOT_AVAILABLE_NEARBY_SETUP = "not_available_nearby_setup"
    MISSED_OR_CHASING = "missed_or_chasing"
    SETUP_INVALIDATED = "setup_invalidated"


@dataclass(frozen=True, slots=True)
class SetupExistenceAssessment:
    state: SetupExistenceState
    source_entry_status: EntryStatus
    setup_exists: bool


@dataclass(frozen=True, slots=True)
class CmpEntryAssessment:
    state: CmpEntryAssessmentState
    execution_allowed_now: bool
    location_state: CmpLocationState
    beyond_maximum_chase: bool
    setup_existence_state: SetupExistenceState


class ActionabilityState(StrEnum):
    # Planned CMP-first states; additive until legacy behavior is replaced.
    EXECUTE_NOW = "execute_now"
    AGGRESSIVE_NOW = "aggressive_now"
    EXECUTE_ON_MICRO_CONFIRMATION = "execute_on_micro_confirmation"
    PLACE_LIMIT = "place_limit"
    PLACE_LIMIT_WITH_ACTIVATION = "place_limit_with_activation"
    CMP_AVAILABLE_BUT_POOR_LOCATION = "cmp_available_but_poor_location"
    RETEST_PREFERRED = "retest_preferred"
    RECLAIM_REQUIRED = "reclaim_required"
    MISSED_OR_CHASING = "missed_or_chasing"
    DEVELOPING = "developing"
    INVALIDATED = "invalidated"


class ActionabilityClassificationBasis(StrEnum):
    LEGACY_INVALIDATION = "legacy_invalidation"
    MAXIMUM_CHASE = "maximum_chase"
    LEGACY_LATE_STATUS = "legacy_late_status"
    EXECUTABLE_INSIDE_ZONE = "executable_inside_zone"
    EXECUTABLE_POOR_LOCATION = "executable_poor_location"
    LEGACY_PULLBACK = "legacy_pullback"
    LEGACY_WATCH = "legacy_watch"
    CONTRADICTORY_LEGACY_FACTS = "contradictory_legacy_facts"


class ActionabilityProjectionIssue(StrEnum):
    ACTIONABILITY_CONTRADICTION = "actionability_contradiction"
    STALE_TRIGGER = "stale_trigger"
    CLOCK_SKEW = "clock_skew"
    BAR_EXPIRY_UNEVALUATED = "bar_expiry_unevaluated"
    ENTRY_BOUNDARY_CONTRADICTION = "entry_boundary_contradiction"


@dataclass(frozen=True, slots=True)
class ActionabilityStateAssessment:
    state: ActionabilityState
    basis: ActionabilityClassificationBasis
    source_entry_status: EntryStatus
    execution_allowed_now: bool
    location_state: CmpLocationState
    sequence_role: SequenceRole
    issues: tuple[ActionabilityProjectionIssue, ...] = ()
    has_blocking_issue: bool = False
    is_legacy_projection: bool = True


class ActionabilityConsistencyCode(StrEnum):
    """Machine-readable contradictions among existing actionability facts."""

    INVALIDATED_EXECUTION_AUTHORIZED = "invalidated_execution_authorized"
    CHASE_BREACHED_EXECUTION_AUTHORIZED = "chase_breached_execution_authorized"
    READY_NOW_OUTSIDE_ENTRY_ZONE = "ready_now_outside_entry_zone"
    IMMEDIATE_STATUS_EXECUTION_DISABLED = "immediate_status_execution_disabled"
    NON_IMMEDIATE_STATUS_EXECUTION_AUTHORIZED = "non_immediate_status_execution_authorized"
    NEARBY_ROLE_EXECUTION_AUTHORIZED = "nearby_role_execution_authorized"
    CURRENT_ROLE_EXECUTION_DISABLED = "current_role_execution_disabled"


@dataclass(frozen=True, slots=True)
class ActionabilityConsistencyAudit:
    """Additive consistency findings that preserve all canonical decisions."""

    codes: tuple[ActionabilityConsistencyCode, ...]
    source_entry_status: EntryStatus
    execution_allowed_now: bool
    location_state: CmpLocationState
    beyond_maximum_chase: bool
    sequence_role: SequenceRole

    @property
    def is_consistent(self) -> bool:
        """Return whether no known contradiction was observed."""

        return not self.codes


@dataclass(frozen=True, slots=True)
class CmpActionabilityDiagnostics:
    """Additive actionability facts that never alter canonical setup validity."""

    state: CmpActionabilityState
    source_entry_status: EntryStatus
    execution_allowed_now: bool
    location_state: CmpLocationState


@dataclass(frozen=True, slots=True)
class CmpDistanceDiagnostics:
    """Additive CMP-distance facts derived from existing setup geometry.

    These diagnostics do not classify validity, change sequence role, or apply any
    threshold. They expose the current geometry for later CMP-first actionability work.
    """

    zone_position: CmpZonePosition
    location_state: CmpLocationState
    distance_to_entry_zone: float
    distance_to_entry_zone_pct: float
    distance_to_ideal_entry: float
    distance_to_ideal_entry_pct: float
    distance_to_maximum_chase: float
    distance_to_maximum_chase_pct: float
    beyond_maximum_chase: bool


def classify_cmp_location_state(
    *,
    zone_position: CmpZonePosition,
    beyond_maximum_chase: bool,
) -> CmpLocationState:
    """Normalize existing CMP facts without changing actionability or validity."""

    if beyond_maximum_chase:
        return CmpLocationState.BEYOND_MAXIMUM_CHASE
    return CmpLocationState(zone_position.value)


def build_cmp_actionability_diagnostics(
    setup: DiscoverySetup,
    *,
    location_state: CmpLocationState | None = None,
) -> CmpActionabilityDiagnostics:
    """Interpret existing actionability facts without promoting or rejecting a setup."""

    resolved_location = (
        build_cmp_distance_diagnostics(setup).location_state
        if location_state is None
        else location_state
    )
    if setup.entry_status is EntryStatus.INVALIDATED:
        state = CmpActionabilityState.INVALIDATED
    elif (
        resolved_location is CmpLocationState.BEYOND_MAXIMUM_CHASE
        or setup.entry_status is EntryStatus.LATE_OR_CHASING
    ):
        state = CmpActionabilityState.CHASE_BREACHED
    elif setup.execution_allowed_now:
        state = (
            CmpActionabilityState.EXECUTABLE_AT_CMP
            if resolved_location is CmpLocationState.INSIDE_ENTRY_ZONE
            else CmpActionabilityState.EXECUTION_GEOMETRY_CONFLICT
        )
    else:
        state = CmpActionabilityState.NEARBY_SETUP

    return CmpActionabilityDiagnostics(
        state=state,
        source_entry_status=setup.entry_status,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=resolved_location,
    )


def build_stale_trigger_diagnostics(
    setup: DiscoverySetup,
    *,
    evaluated_at: datetime,
) -> StaleTriggerDiagnostics:
    # Time expiry can be evaluated exactly. Bar expiry requires candle context and
    # is therefore exposed as unevaluated rather than guessed.
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("stale-trigger evaluation time must be timezone-aware")

    age_seconds = (evaluated_at - setup.decision_time).total_seconds()
    codes: list[StaleTriggerDiagnosticCode] = []

    if age_seconds < 0.0:
        state = TriggerFreshnessState.CLOCK_SKEW
        codes.append(StaleTriggerDiagnosticCode.EVALUATED_BEFORE_DECISION_TIME)
    elif setup.setup_expiry_seconds is not None and age_seconds >= setup.setup_expiry_seconds:
        state = TriggerFreshnessState.STALE
        codes.append(StaleTriggerDiagnosticCode.EXPIRED_BY_SECONDS)
        if setup.execution_allowed_now:
            codes.append(StaleTriggerDiagnosticCode.EXECUTION_AUTHORIZED_AFTER_EXPIRY)
    elif setup.setup_expiry_seconds is not None:
        state = TriggerFreshnessState.FRESH
    elif setup.setup_expiry_bars is not None:
        state = TriggerFreshnessState.BAR_EXPIRY_UNEVALUATED
        codes.append(StaleTriggerDiagnosticCode.BAR_EXPIRY_REQUIRES_CONTEXT)
    else:
        state = TriggerFreshnessState.NOT_CONFIGURED

    return StaleTriggerDiagnostics(
        state=state,
        codes=tuple(codes),
        evaluated_at=evaluated_at,
        decision_time=setup.decision_time,
        age_seconds=age_seconds,
        setup_expiry_seconds=setup.setup_expiry_seconds,
        setup_expiry_bars=setup.setup_expiry_bars,
        setup_expiry_reason=setup.setup_expiry_reason,
        execution_allowed_now=setup.execution_allowed_now,
    )


def build_entry_boundary_consistency_audit(
    setup: DiscoverySetup,
    *,
    cmp_distance: CmpDistanceDiagnostics | None = None,
) -> EntryBoundaryConsistencyAudit:
    # Audit existing entry geometry without changing any boundary.
    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance
    entry = setup.entry
    codes: list[EntryBoundaryConsistencyCode] = []

    ideal_entry_inside_zone = entry.lower <= entry.preferred <= entry.upper
    chase_valid = (
        entry.maximum_chase_price >= entry.upper
        if setup.direction is TradeDirection.LONG
        else entry.maximum_chase_price <= entry.lower
    )

    same_boundary = entry.maximum_chase_price == entry.preferred
    if same_boundary:
        codes.append(EntryBoundaryConsistencyCode.MAXIMUM_CHASE_EQUALS_IDEAL_ENTRY)

    if distance.beyond_maximum_chase and setup.entry_status is not EntryStatus.LATE_OR_CHASING:
        codes.append(EntryBoundaryConsistencyCode.CHASE_BREACHED_WITHOUT_LATE_STATUS)

    if setup.entry_status is EntryStatus.LATE_OR_CHASING and not distance.beyond_maximum_chase:
        codes.append(EntryBoundaryConsistencyCode.LATE_STATUS_WITHOUT_CHASE_BREACH)

    return EntryBoundaryConsistencyAudit(
        codes=tuple(codes),
        ideal_entry_inside_zone=ideal_entry_inside_zone,
        maximum_chase_directionally_valid=chase_valid,
        maximum_chase_equals_ideal_entry=same_boundary,
        beyond_maximum_chase=distance.beyond_maximum_chase,
        source_entry_status=setup.entry_status,
    )


def build_setup_existence_assessment(
    setup: DiscoverySetup,
) -> SetupExistenceAssessment:
    # Setup existence is intentionally independent from current CMP availability.
    invalidated = setup.entry_status is EntryStatus.INVALIDATED
    return SetupExistenceAssessment(
        state=(
            SetupExistenceState.INVALIDATED
            if invalidated
            else SetupExistenceState.STRUCTURALLY_VALID
        ),
        source_entry_status=setup.entry_status,
        setup_exists=not invalidated,
    )


def build_cmp_entry_assessment(
    setup: DiscoverySetup,
    *,
    cmp_distance: CmpDistanceDiagnostics | None = None,
    setup_existence: SetupExistenceAssessment | None = None,
) -> CmpEntryAssessment:
    # Describe only CMP availability; do not replace the underlying setup state.
    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance
    existence = (
        build_setup_existence_assessment(setup) if setup_existence is None else setup_existence
    )

    if existence.state is SetupExistenceState.INVALIDATED:
        state = CmpEntryAssessmentState.SETUP_INVALIDATED
    elif distance.beyond_maximum_chase or setup.entry_status is EntryStatus.LATE_OR_CHASING:
        state = CmpEntryAssessmentState.MISSED_OR_CHASING
    elif setup.execution_allowed_now:
        state = (
            CmpEntryAssessmentState.AVAILABLE_NOW
            if distance.location_state is CmpLocationState.INSIDE_ENTRY_ZONE
            else CmpEntryAssessmentState.AVAILABLE_BUT_POOR_LOCATION
        )
    else:
        state = CmpEntryAssessmentState.NOT_AVAILABLE_NEARBY_SETUP

    return CmpEntryAssessment(
        state=state,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=distance.location_state,
        beyond_maximum_chase=distance.beyond_maximum_chase,
        setup_existence_state=existence.state,
    )


def build_actionability_state_assessment(
    setup: DiscoverySetup,
    *,
    sequence_role: SequenceRole,
    cmp_distance: CmpDistanceDiagnostics | None = None,
    consistency_audit: ActionabilityConsistencyAudit | None = None,
    stale_trigger: StaleTriggerDiagnostics | None = None,
    entry_boundary_audit: EntryBoundaryConsistencyAudit | None = None,
) -> ActionabilityStateAssessment:
    # Project current facts into the planned state contract without mutation.
    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance

    if setup.entry_status is EntryStatus.INVALIDATED:
        state = ActionabilityState.INVALIDATED
        basis = ActionabilityClassificationBasis.LEGACY_INVALIDATION
    elif distance.beyond_maximum_chase:
        state = ActionabilityState.MISSED_OR_CHASING
        basis = ActionabilityClassificationBasis.MAXIMUM_CHASE
    elif setup.entry_status is EntryStatus.LATE_OR_CHASING:
        state = ActionabilityState.MISSED_OR_CHASING
        basis = ActionabilityClassificationBasis.LEGACY_LATE_STATUS
    elif setup.execution_allowed_now:
        if distance.location_state is CmpLocationState.INSIDE_ENTRY_ZONE:
            state = (
                ActionabilityState.AGGRESSIVE_NOW
                if setup.entry_status is EntryStatus.AGGRESSIVE_NOW
                else ActionabilityState.EXECUTE_NOW
            )
            basis = ActionabilityClassificationBasis.EXECUTABLE_INSIDE_ZONE
        else:
            state = ActionabilityState.CMP_AVAILABLE_BUT_POOR_LOCATION
            basis = ActionabilityClassificationBasis.EXECUTABLE_POOR_LOCATION
    elif setup.entry_status is EntryStatus.PULLBACK_PREFERRED:
        state = ActionabilityState.RETEST_PREFERRED
        basis = ActionabilityClassificationBasis.LEGACY_PULLBACK
    elif setup.entry_status is EntryStatus.WATCH_NEAR_ENTRY:
        state = ActionabilityState.DEVELOPING
        basis = ActionabilityClassificationBasis.LEGACY_WATCH
    else:
        state = ActionabilityState.DEVELOPING
        basis = ActionabilityClassificationBasis.CONTRADICTORY_LEGACY_FACTS

    issues: list[ActionabilityProjectionIssue] = []
    if consistency_audit is not None and not consistency_audit.is_consistent:
        issues.append(ActionabilityProjectionIssue.ACTIONABILITY_CONTRADICTION)
    if stale_trigger is not None:
        if stale_trigger.state is TriggerFreshnessState.STALE:
            issues.append(ActionabilityProjectionIssue.STALE_TRIGGER)
        elif stale_trigger.state is TriggerFreshnessState.CLOCK_SKEW:
            issues.append(ActionabilityProjectionIssue.CLOCK_SKEW)
        elif stale_trigger.state is TriggerFreshnessState.BAR_EXPIRY_UNEVALUATED:
            issues.append(ActionabilityProjectionIssue.BAR_EXPIRY_UNEVALUATED)
    if entry_boundary_audit is not None and not entry_boundary_audit.is_consistent:
        issues.append(ActionabilityProjectionIssue.ENTRY_BOUNDARY_CONTRADICTION)

    blocking = any(
        issue
        in {
            ActionabilityProjectionIssue.ACTIONABILITY_CONTRADICTION,
            ActionabilityProjectionIssue.STALE_TRIGGER,
            ActionabilityProjectionIssue.CLOCK_SKEW,
            ActionabilityProjectionIssue.ENTRY_BOUNDARY_CONTRADICTION,
        }
        for issue in issues
    )

    return ActionabilityStateAssessment(
        state=state,
        basis=basis,
        source_entry_status=setup.entry_status,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=distance.location_state,
        sequence_role=sequence_role,
        issues=tuple(issues),
        has_blocking_issue=blocking,
    )


def build_actionability_consistency_audit(
    setup: DiscoverySetup,
    *,
    sequence_role: SequenceRole,
    cmp_distance: CmpDistanceDiagnostics | None = None,
) -> ActionabilityConsistencyAudit:
    """Record contradictory legacy facts without correcting or reclassifying them."""

    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance
    codes: list[ActionabilityConsistencyCode] = []

    # Ordering is a public diagnostic contract: structural contradictions first,
    # then status/geometry contradictions, then role/authorization contradictions.
    if setup.entry_status is EntryStatus.INVALIDATED and setup.execution_allowed_now:
        codes.append(ActionabilityConsistencyCode.INVALIDATED_EXECUTION_AUTHORIZED)

    if distance.beyond_maximum_chase and setup.execution_allowed_now:
        codes.append(ActionabilityConsistencyCode.CHASE_BREACHED_EXECUTION_AUTHORIZED)

    if (
        setup.entry_status is EntryStatus.READY_NOW
        and distance.location_state is not CmpLocationState.INSIDE_ENTRY_ZONE
    ):
        codes.append(ActionabilityConsistencyCode.READY_NOW_OUTSIDE_ENTRY_ZONE)

    if (
        setup.entry_status in {EntryStatus.READY_NOW, EntryStatus.AGGRESSIVE_NOW}
        and not setup.execution_allowed_now
    ):
        codes.append(ActionabilityConsistencyCode.IMMEDIATE_STATUS_EXECUTION_DISABLED)

    if (
        setup.entry_status
        in {
            EntryStatus.PULLBACK_PREFERRED,
            EntryStatus.WATCH_NEAR_ENTRY,
            EntryStatus.LATE_OR_CHASING,
            EntryStatus.INVALIDATED,
        }
        and setup.execution_allowed_now
    ):
        codes.append(ActionabilityConsistencyCode.NON_IMMEDIATE_STATUS_EXECUTION_AUTHORIZED)

    if sequence_role is SequenceRole.NEARBY and setup.execution_allowed_now:
        codes.append(ActionabilityConsistencyCode.NEARBY_ROLE_EXECUTION_AUTHORIZED)

    if sequence_role is SequenceRole.CURRENT and not setup.execution_allowed_now:
        codes.append(ActionabilityConsistencyCode.CURRENT_ROLE_EXECUTION_DISABLED)

    return ActionabilityConsistencyAudit(
        codes=tuple(codes),
        source_entry_status=setup.entry_status,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=distance.location_state,
        beyond_maximum_chase=distance.beyond_maximum_chase,
        sequence_role=sequence_role,
    )


def build_cmp_distance_diagnostics(setup: DiscoverySetup) -> CmpDistanceDiagnostics:
    """Describe CMP distance without changing the setup's canonical validity."""

    entry = setup.entry
    cmp = entry.current_price
    if cmp < entry.lower:
        position = CmpZonePosition.BELOW_ENTRY_ZONE
        zone_distance = entry.lower - cmp
    elif cmp > entry.upper:
        position = CmpZonePosition.ABOVE_ENTRY_ZONE
        zone_distance = cmp - entry.upper
    else:
        position = CmpZonePosition.INSIDE_ENTRY_ZONE
        zone_distance = 0.0

    ideal_distance = abs(cmp - entry.preferred)
    chase_distance = abs(cmp - entry.maximum_chase_price)
    beyond_chase = (
        cmp > entry.maximum_chase_price
        if setup.direction is TradeDirection.LONG
        else cmp < entry.maximum_chase_price
    )

    return CmpDistanceDiagnostics(
        zone_position=position,
        location_state=classify_cmp_location_state(
            zone_position=position,
            beyond_maximum_chase=beyond_chase,
        ),
        distance_to_entry_zone=zone_distance,
        distance_to_entry_zone_pct=zone_distance / cmp * 100.0,
        distance_to_ideal_entry=ideal_distance,
        distance_to_ideal_entry_pct=ideal_distance / cmp * 100.0,
        distance_to_maximum_chase=chase_distance,
        distance_to_maximum_chase_pct=chase_distance / cmp * 100.0,
        beyond_maximum_chase=beyond_chase,
    )


@dataclass(frozen=True, slots=True)
class TradeOpportunity:
    """Compatibility wrapper around one fully constructed discovery setup."""

    opportunity_id: str
    setup: DiscoverySetup
    sequence_role: SequenceRole

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity identity cannot be empty")
        if self.setup.candidate_id != self.opportunity_id:
            raise ValueError("opportunity identity must match the wrapped setup candidate")
        if self.sequence_role is SequenceRole.CURRENT and not self.setup.execution_allowed_now:
            raise ValueError("current opportunities must authorize execution now")
        if self.sequence_role is SequenceRole.NEARBY and self.setup.execution_allowed_now:
            raise ValueError("nearby opportunities must not authorize immediate execution")

    @property
    def direction(self) -> TradeDirection:
        """Return the wrapped setup direction."""

        return self.setup.direction


@dataclass(frozen=True, slots=True)
class SymbolOpportunityPortfolio:
    """Small deterministic portfolio of distinct opportunities for one symbol."""

    symbol: str
    cmp: float
    analysis_timestamp: datetime
    analysis_mode: AnalysisMode
    current_long: TradeOpportunity | None = None
    current_short: TradeOpportunity | None = None
    nearby_long: TradeOpportunity | None = None
    nearby_short: TradeOpportunity | None = None
    follow_up_opportunities: tuple[TradeOpportunity, ...] = ()
    runner_plan: TradeOpportunity | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("portfolio symbol cannot be empty")
        if self.cmp <= 0.0:
            raise ValueError("portfolio CMP must be greater than zero")
        if self.analysis_timestamp.tzinfo is None or self.analysis_timestamp.utcoffset() is None:
            raise ValueError("portfolio analysis timestamp must be timezone-aware")

        expected_slots = (
            ("current_long", self.current_long, TradeDirection.LONG, SequenceRole.CURRENT),
            ("current_short", self.current_short, TradeDirection.SHORT, SequenceRole.CURRENT),
            ("nearby_long", self.nearby_long, TradeDirection.LONG, SequenceRole.NEARBY),
            ("nearby_short", self.nearby_short, TradeDirection.SHORT, SequenceRole.NEARBY),
        )
        for name, opportunity, direction, role in expected_slots:
            if opportunity is None:
                continue
            if opportunity.setup.symbol != self.symbol:
                raise ValueError(f"{name} symbol must match portfolio symbol")
            if opportunity.direction is not direction:
                raise ValueError(f"{name} has the wrong direction")
            if opportunity.sequence_role is not role:
                raise ValueError(f"{name} has the wrong sequence role")

        for opportunity in self.follow_up_opportunities:
            if opportunity.setup.symbol != self.symbol:
                raise ValueError("follow-up symbol must match portfolio symbol")
            if opportunity.sequence_role is not SequenceRole.FOLLOW_UP:
                raise ValueError("follow-up opportunities must use the follow-up sequence role")

        if self.runner_plan is not None:
            if self.runner_plan.setup.symbol != self.symbol:
                raise ValueError("runner symbol must match portfolio symbol")
            if self.runner_plan.sequence_role is not SequenceRole.RUNNER:
                raise ValueError("runner plan must use the runner sequence role")

        identities = [item.opportunity_id for item in self.opportunities]
        if len(identities) != len(set(identities)):
            raise ValueError("portfolio slots cannot reference duplicate opportunities")

    @property
    def opportunities(self) -> tuple[TradeOpportunity, ...]:
        """Return every populated opportunity in deterministic slot order."""

        fixed = (
            self.current_long,
            self.current_short,
            self.nearby_long,
            self.nearby_short,
        )
        return (
            tuple(item for item in fixed if item is not None)
            + self.follow_up_opportunities
            + (() if self.runner_plan is None else (self.runner_plan,))
        )


def _semantic_setup_identity(setup: DiscoverySetup) -> tuple[object, ...]:
    """Return a conservative identity for merging equivalent candidate theses."""

    return (
        setup.direction,
        setup.strategy.canonical_family,
        setup.execution_allowed_now,
        round(setup.entry.lower, 8),
        round(setup.entry.upper, 8),
        round(setup.entry.preferred, 8),
        round(setup.entry.maximum_chase_price, 8),
        round(setup.stop_loss.price, 8),
    )


def portfolio_from_setups(
    setups: Iterable[DiscoverySetup],
    *,
    symbol: str,
    cmp: float,
    analysis_timestamp: datetime,
    analysis_mode: AnalysisMode,
) -> SymbolOpportunityPortfolio:
    """Classify distinct constructed setups into deterministic portfolio slots.

    This compatibility selector deliberately uses existing setup semantics only.
    Immediate setups fill current-side slots. Non-immediate setups fill nearby-side
    slots. Additional structurally distinct setups are retained as follow-ups in the
    same deterministic input order. Later batches can replace the input ordering with
    collision-aware and score-dimensional ranking without changing the contract.
    """

    current_long: TradeOpportunity | None = None
    current_short: TradeOpportunity | None = None
    nearby_long: TradeOpportunity | None = None
    nearby_short: TradeOpportunity | None = None
    follow_ups: list[TradeOpportunity] = []
    seen_candidate_ids: set[str] = set()
    seen_semantic_setups: set[tuple[object, ...]] = set()

    for setup in setups:
        if setup.symbol != symbol:
            raise ValueError("setup symbol must match portfolio symbol")

        semantic_identity = _semantic_setup_identity(setup)
        if setup.candidate_id in seen_candidate_ids or semantic_identity in seen_semantic_setups:
            continue
        seen_candidate_ids.add(setup.candidate_id)
        seen_semantic_setups.add(semantic_identity)

        role = classify_setup_sequence_role(setup)
        opportunity = TradeOpportunity(setup.candidate_id, setup, role)
        if role is SequenceRole.CURRENT:
            if setup.direction is TradeDirection.LONG and current_long is None:
                current_long = opportunity
                continue
            if setup.direction is TradeDirection.SHORT and current_short is None:
                current_short = opportunity
                continue
        else:
            if setup.direction is TradeDirection.LONG and nearby_long is None:
                nearby_long = opportunity
                continue
            if setup.direction is TradeDirection.SHORT and nearby_short is None:
                nearby_short = opportunity
                continue

        follow_ups.append(
            TradeOpportunity(
                setup.candidate_id,
                setup,
                SequenceRole.FOLLOW_UP,
            )
        )

    return SymbolOpportunityPortfolio(
        symbol=symbol,
        cmp=cmp,
        analysis_timestamp=analysis_timestamp,
        analysis_mode=analysis_mode,
        current_long=current_long,
        current_short=current_short,
        nearby_long=nearby_long,
        nearby_short=nearby_short,
        follow_up_opportunities=(
            tuple(follow_ups) if analysis_mode is AnalysisMode.ANALYZE_FULL else ()
        ),
    )


def portfolio_from_legacy_assessment(
    assessment: DiscoveryAssessment,
    *,
    cmp: float,
    analysis_mode: AnalysisMode,
) -> SymbolOpportunityPortfolio:
    """Represent the current selected/developing assessment without changing behavior.

    This adapter is deliberately conservative: the selected setup occupies either a
    current slot or a nearby slot according to its existing execution flag.  The
    existing developing setup occupies an unused nearby slot, or a follow-up slot when
    that directional nearby slot is already occupied.
    """

    current_long: TradeOpportunity | None = None
    current_short: TradeOpportunity | None = None
    nearby_long: TradeOpportunity | None = None
    nearby_short: TradeOpportunity | None = None
    follow_ups: list[TradeOpportunity] = []

    def place(setup: DiscoverySetup, *, developing: bool) -> None:
        nonlocal current_long, current_short, nearby_long, nearby_short

        role = SequenceRole.NEARBY if developing else classify_setup_sequence_role(setup)
        opportunity = TradeOpportunity(setup.candidate_id, setup, role)
        if role is SequenceRole.CURRENT:
            if setup.direction is TradeDirection.LONG:
                current_long = opportunity
            else:
                current_short = opportunity
            return

        if setup.direction is TradeDirection.LONG and nearby_long is None:
            nearby_long = opportunity
            return
        if setup.direction is TradeDirection.SHORT and nearby_short is None:
            nearby_short = opportunity
            return

        follow_ups.append(
            TradeOpportunity(
                setup.candidate_id,
                setup,
                SequenceRole.FOLLOW_UP,
            )
        )

    if assessment.setup is not None:
        place(assessment.setup, developing=False)
    if assessment.developing_setup is not None:
        place(assessment.developing_setup, developing=True)

    return SymbolOpportunityPortfolio(
        symbol=assessment.symbol,
        cmp=cmp,
        analysis_timestamp=assessment.decision_time,
        analysis_mode=analysis_mode,
        current_long=current_long,
        current_short=current_short,
        nearby_long=nearby_long,
        nearby_short=nearby_short,
        follow_up_opportunities=tuple(follow_ups),
    )


def opportunity_portfolio_payload(portfolio: SymbolOpportunityPortfolio) -> dict[str, Any]:
    """Serialize the additive compatibility portfolio without changing legacy fields."""

    def serialize(opportunity: TradeOpportunity | None) -> dict[str, Any] | None:
        if opportunity is None:
            return None
        setup = opportunity.setup
        cmp_distance = build_cmp_distance_diagnostics(setup)
        cmp_actionability = build_cmp_actionability_diagnostics(
            setup,
            location_state=cmp_distance.location_state,
        )
        consistency_audit = build_actionability_consistency_audit(
            setup,
            sequence_role=opportunity.sequence_role,
            cmp_distance=cmp_distance,
        )
        actionability_state = build_actionability_state_assessment(
            setup,
            sequence_role=opportunity.sequence_role,
            cmp_distance=cmp_distance,
        )
        setup_existence = build_setup_existence_assessment(setup)
        cmp_entry_assessment = build_cmp_entry_assessment(
            setup,
            cmp_distance=cmp_distance,
            setup_existence=setup_existence,
        )
        entry_boundary_consistency = build_entry_boundary_consistency_audit(
            setup,
            cmp_distance=cmp_distance,
        )
        stale_trigger = build_stale_trigger_diagnostics(
            setup,
            evaluated_at=portfolio.analysis_timestamp,
        )
        actionability_state = build_actionability_state_assessment(
            setup,
            sequence_role=opportunity.sequence_role,
            cmp_distance=cmp_distance,
            consistency_audit=consistency_audit,
            stale_trigger=stale_trigger,
            entry_boundary_audit=entry_boundary_consistency,
        )
        return {
            "opportunity_id": opportunity.opportunity_id,
            "sequence_role": opportunity.sequence_role.value,
            "direction": setup.direction.value,
            "strategy": setup.strategy.value,
            "strategy_family": setup.strategy.canonical_family.value,
            "entry_status": setup.entry_status.value,
            "execution_allowed_now": setup.execution_allowed_now,
            "cmp": setup.entry.current_price,
            "cmp_actionability": {
                "state": cmp_actionability.state.value,
                "source_entry_status": cmp_actionability.source_entry_status.value,
                "execution_allowed_now": cmp_actionability.execution_allowed_now,
                "location_state": cmp_actionability.location_state.value,
            },
            "actionability_consistency": {
                "is_consistent": consistency_audit.is_consistent,
                "codes": [code.value for code in consistency_audit.codes],
                "source_entry_status": consistency_audit.source_entry_status.value,
                "execution_allowed_now": consistency_audit.execution_allowed_now,
                "location_state": consistency_audit.location_state.value,
                "beyond_maximum_chase": consistency_audit.beyond_maximum_chase,
                "sequence_role": consistency_audit.sequence_role.value,
            },
            "actionability_state": {
                "state": actionability_state.state.value,
                "basis": actionability_state.basis.value,
                "source_entry_status": actionability_state.source_entry_status.value,
                "execution_allowed_now": actionability_state.execution_allowed_now,
                "location_state": actionability_state.location_state.value,
                "sequence_role": actionability_state.sequence_role.value,
                "issues": [issue.value for issue in actionability_state.issues],
                "has_blocking_issue": actionability_state.has_blocking_issue,
                "is_legacy_projection": actionability_state.is_legacy_projection,
            },
            "setup_existence": {
                "state": setup_existence.state.value,
                "source_entry_status": setup_existence.source_entry_status.value,
                "setup_exists": setup_existence.setup_exists,
            },
            "cmp_entry_assessment": {
                "state": cmp_entry_assessment.state.value,
                "execution_allowed_now": cmp_entry_assessment.execution_allowed_now,
                "location_state": cmp_entry_assessment.location_state.value,
                "beyond_maximum_chase": cmp_entry_assessment.beyond_maximum_chase,
                "setup_existence_state": cmp_entry_assessment.setup_existence_state.value,
            },
            "entry_boundary_consistency": {
                "is_consistent": entry_boundary_consistency.is_consistent,
                "codes": [code.value for code in entry_boundary_consistency.codes],
                "ideal_entry_inside_zone": (entry_boundary_consistency.ideal_entry_inside_zone),
                "maximum_chase_directionally_valid": (
                    entry_boundary_consistency.maximum_chase_directionally_valid
                ),
                "maximum_chase_equals_ideal_entry": (
                    entry_boundary_consistency.maximum_chase_equals_ideal_entry
                ),
                "beyond_maximum_chase": (entry_boundary_consistency.beyond_maximum_chase),
                "source_entry_status": (entry_boundary_consistency.source_entry_status.value),
            },
            "stale_trigger": {
                "state": stale_trigger.state.value,
                "codes": [code.value for code in stale_trigger.codes],
                "evaluated_at": stale_trigger.evaluated_at.isoformat(),
                "decision_time": stale_trigger.decision_time.isoformat(),
                "age_seconds": stale_trigger.age_seconds,
                "setup_expiry_seconds": stale_trigger.setup_expiry_seconds,
                "setup_expiry_bars": stale_trigger.setup_expiry_bars,
                "setup_expiry_reason": stale_trigger.setup_expiry_reason,
                "execution_allowed_now": stale_trigger.execution_allowed_now,
                "is_stale": stale_trigger.is_stale,
            },
            "cmp_distance": {
                "zone_position": cmp_distance.zone_position.value,
                "location_state": cmp_distance.location_state.value,
                "distance_to_entry_zone": cmp_distance.distance_to_entry_zone,
                "distance_to_entry_zone_pct": cmp_distance.distance_to_entry_zone_pct,
                "distance_to_ideal_entry": cmp_distance.distance_to_ideal_entry,
                "distance_to_ideal_entry_pct": cmp_distance.distance_to_ideal_entry_pct,
                "distance_to_maximum_chase": cmp_distance.distance_to_maximum_chase,
                "distance_to_maximum_chase_pct": cmp_distance.distance_to_maximum_chase_pct,
                "beyond_maximum_chase": cmp_distance.beyond_maximum_chase,
            },
            "entry_zone": {
                "lower": setup.entry.lower,
                "upper": setup.entry.upper,
                "preferred": setup.entry.preferred,
                "maximum_chase": setup.entry.maximum_chase_price,
            },
            "stop": setup.stop_loss.price,
            "targets": [
                {
                    "label": target.label,
                    "price": target.price,
                    "risk_reward": target.risk_reward,
                }
                for target in setup.take_profits
            ],
        }

    return {
        "symbol": portfolio.symbol,
        "cmp": portfolio.cmp,
        "analysis_timestamp": portfolio.analysis_timestamp.isoformat(),
        "analysis_mode": portfolio.analysis_mode.value,
        "current_long": serialize(portfolio.current_long),
        "current_short": serialize(portfolio.current_short),
        "nearby_long": serialize(portfolio.nearby_long),
        "nearby_short": serialize(portfolio.nearby_short),
        "follow_up_opportunities": [
            serialize(opportunity) for opportunity in portfolio.follow_up_opportunities
        ],
        "runner_plan": serialize(portfolio.runner_plan),
        "opportunity_count": len(portfolio.opportunities),
    }


__all__ = [
    "ActionabilityClassificationBasis",
    "ActionabilityConsistencyAudit",
    "ActionabilityConsistencyCode",
    "ActionabilityProjectionIssue",
    "ActionabilityState",
    "ActionabilityStateAssessment",
    "AnalysisMode",
    "CmpActionabilityDiagnostics",
    "CmpActionabilityState",
    "CmpDistanceDiagnostics",
    "CmpEntryAssessment",
    "CmpEntryAssessmentState",
    "CmpLocationState",
    "CmpZonePosition",
    "EntryBoundaryConsistencyAudit",
    "EntryBoundaryConsistencyCode",
    "SequenceRole",
    "SetupExistenceAssessment",
    "SetupExistenceState",
    "StaleTriggerDiagnosticCode",
    "StaleTriggerDiagnostics",
    "SymbolOpportunityPortfolio",
    "TradeOpportunity",
    "TriggerFreshnessState",
    "build_actionability_consistency_audit",
    "build_actionability_state_assessment",
    "build_cmp_actionability_diagnostics",
    "build_cmp_distance_diagnostics",
    "build_cmp_entry_assessment",
    "build_entry_boundary_consistency_audit",
    "build_setup_existence_assessment",
    "build_stale_trigger_diagnostics",
    "classify_cmp_location_state",
    "classify_setup_sequence_role",
    "opportunity_portfolio_payload",
    "portfolio_from_legacy_assessment",
    "portfolio_from_setups",
]
