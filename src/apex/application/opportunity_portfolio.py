"""Typed multi-opportunity portfolio contracts for the planv3 analysis core.

The portfolio is the canonical symbol-level opportunity view. Legacy single-setup
assessments remain available during rollout, but they must not hide valid current,
nearby, follow-up, or runner opportunities.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from apex.application.discovery_contracts import DiscoveryAssessment, DiscoverySetup
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


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


class OpportunityLane(StrEnum):
    """Methodology lane used to retain materially different trade horizons."""

    CMP_SCALP = "cmp_scalp"
    CONFIRMATION_SCALP = "confirmation_scalp"
    PULLBACK_SCALP = "pullback_scalp"
    NEARBY_STRUCTURED = "nearby_structured"
    RUNNER = "runner"
    DEVELOPING = "developing"

    @property
    def is_scalp(self) -> bool:
        return self in {
            OpportunityLane.CMP_SCALP,
            OpportunityLane.CONFIRMATION_SCALP,
            OpportunityLane.PULLBACK_SCALP,
            OpportunityLane.NEARBY_STRUCTURED,
        }


class PortfolioDecisionState(StrEnum):
    """Highest-priority public state represented by a symbol portfolio."""

    ACTIONABLE_AT_CMP = "actionable_at_cmp"
    CONFIRMATION_AT_CMP = "confirmation_at_cmp"
    NEARBY_SETUP_AVAILABLE = "nearby_setup_available"
    FOLLOW_UP_AVAILABLE = "follow_up_available"
    RUNNER_MANAGEMENT = "runner_management"
    NO_VALID_SETUP = "no_valid_setup"


def classify_setup_sequence_role(setup: DiscoverySetup) -> SequenceRole:
    if not setup.canonical_actionability:
        return SequenceRole.CURRENT if setup.execution_allowed_now else SequenceRole.NEARBY

    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.CURRENT,
    )
    current_state = assessment.state in {
        ActionabilityState.EXECUTE_NOW,
        ActionabilityState.AGGRESSIVE_NOW,
        ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION,
    }
    if not current_state:
        return SequenceRole.NEARBY

    canonical_activation = setup.confirmation_required or setup.provisional
    if canonical_activation or setup.execution_allowed_now:
        return SequenceRole.CURRENT
    return SequenceRole.NEARBY


def setup_is_portfolio_eligible(setup: DiscoverySetup) -> bool:
    if not setup.canonical_actionability:
        return setup.entry_status is not EntryStatus.INVALIDATED

    # Invalidated and chased setups are not tradable opportunities.
    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=SequenceRole.NEARBY,
    )
    return assessment.state not in {
        ActionabilityState.INVALIDATED,
        ActionabilityState.MISSED_OR_CHASING,
    }


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
    EXECUTABLE_INSIDE_ZONE = "executable_inside_zone"
    STRUCTURAL_INVALIDATION = "structural_invalidation"
    SOURCE_INVALIDATION = "source_invalidation"
    MAXIMUM_CHASE = "maximum_chase"
    STALE_OR_EXPIRED_TRIGGER = "stale_or_expired_trigger"
    CONFIRMED_INSIDE_ZONE = "confirmed_inside_zone"
    AGGRESSIVE_INSIDE_ZONE = "aggressive_inside_zone"
    MICRO_CONFIRMATION_INSIDE_ZONE = "micro_confirmation_inside_zone"
    EXECUTABLE_POOR_LOCATION = "executable_poor_location"
    LIMIT_ZONE = "limit_zone"
    LIMIT_WITH_ACTIVATION = "limit_with_activation"
    RETEST_PATH = "retest_path"
    RECLAIM_PATH = "reclaim_path"
    NEAR_ZONE_MICRO_CONFIRMATION = "near_zone_micro_confirmation"
    DEFINED_BUT_IMMATURE = "defined_but_immature"


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
    is_legacy_projection: bool = False


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


def _build_legacy_actionability_projection(
    setup: DiscoverySetup,
    *,
    sequence_role: SequenceRole,
    cmp_distance: CmpDistanceDiagnostics | None = None,
    consistency_audit: ActionabilityConsistencyAudit | None = None,
    stale_trigger: StaleTriggerDiagnostics | None = None,
    entry_boundary_audit: EntryBoundaryConsistencyAudit | None = None,
) -> ActionabilityStateAssessment:
    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance
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

    if setup.entry_status is EntryStatus.INVALIDATED:
        state = ActionabilityState.INVALIDATED
        basis = ActionabilityClassificationBasis.SOURCE_INVALIDATION
    elif distance.beyond_maximum_chase:
        state = ActionabilityState.MISSED_OR_CHASING
        basis = ActionabilityClassificationBasis.MAXIMUM_CHASE
    elif (
        setup.execution_allowed_now
        and distance.location_state is not CmpLocationState.INSIDE_ENTRY_ZONE
    ):
        state = ActionabilityState.CMP_AVAILABLE_BUT_POOR_LOCATION
        basis = ActionabilityClassificationBasis.EXECUTABLE_POOR_LOCATION
    elif setup.entry_status is EntryStatus.READY_NOW:
        state = ActionabilityState.EXECUTE_NOW
        basis = ActionabilityClassificationBasis.EXECUTABLE_INSIDE_ZONE
    elif setup.entry_status is EntryStatus.AGGRESSIVE_NOW:
        state = ActionabilityState.AGGRESSIVE_NOW
        basis = ActionabilityClassificationBasis.EXECUTABLE_INSIDE_ZONE
    elif setup.entry_status is EntryStatus.PULLBACK_PREFERRED:
        state = ActionabilityState.RETEST_PREFERRED
        basis = ActionabilityClassificationBasis.RETEST_PATH
    elif setup.entry_status is EntryStatus.LATE_OR_CHASING:
        state = ActionabilityState.MISSED_OR_CHASING
        basis = ActionabilityClassificationBasis.MAXIMUM_CHASE
    else:
        state = ActionabilityState.DEVELOPING
        basis = ActionabilityClassificationBasis.DEFINED_BUT_IMMATURE

    return ActionabilityStateAssessment(
        state=state,
        basis=basis,
        source_entry_status=setup.entry_status,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=distance.location_state,
        sequence_role=sequence_role,
        issues=tuple(issues),
        has_blocking_issue=blocking,
        is_legacy_projection=True,
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
    if not setup.canonical_actionability:
        return _build_legacy_actionability_projection(
            setup,
            sequence_role=sequence_role,
            cmp_distance=cmp_distance,
            consistency_audit=consistency_audit,
            stale_trigger=stale_trigger,
            entry_boundary_audit=entry_boundary_audit,
        )

    # Classify native actionability from price geometry and activation maturity.
    distance = build_cmp_distance_diagnostics(setup) if cmp_distance is None else cmp_distance
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

    cmp = setup.entry.current_price
    structurally_invalidated = (
        cmp <= setup.stop_loss.price
        if setup.direction is TradeDirection.LONG
        else cmp >= setup.stop_loss.price
    )
    if structurally_invalidated:
        state = ActionabilityState.INVALIDATED
        basis = ActionabilityClassificationBasis.STRUCTURAL_INVALIDATION
    elif setup.entry_status is EntryStatus.INVALIDATED:
        state = ActionabilityState.INVALIDATED
        basis = ActionabilityClassificationBasis.SOURCE_INVALIDATION
    elif distance.beyond_maximum_chase:
        state = ActionabilityState.MISSED_OR_CHASING
        basis = ActionabilityClassificationBasis.MAXIMUM_CHASE
    elif stale_trigger is not None and stale_trigger.state in {
        TriggerFreshnessState.STALE,
        TriggerFreshnessState.CLOCK_SKEW,
    }:
        state = ActionabilityState.DEVELOPING
        basis = ActionabilityClassificationBasis.STALE_OR_EXPIRED_TRIGGER
    elif distance.location_state is CmpLocationState.INSIDE_ENTRY_ZONE:
        if setup.confirmation_complete:
            state = ActionabilityState.EXECUTE_NOW
            basis = ActionabilityClassificationBasis.CONFIRMED_INSIDE_ZONE
        elif setup.entry_mode is EntryMode.MARKET_NEAR:
            state = ActionabilityState.AGGRESSIVE_NOW
            basis = ActionabilityClassificationBasis.AGGRESSIVE_INSIDE_ZONE
        else:
            state = ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION
            basis = ActionabilityClassificationBasis.MICRO_CONFIRMATION_INSIDE_ZONE
    elif setup.execution_allowed_now:
        state = ActionabilityState.CMP_AVAILABLE_BUT_POOR_LOCATION
        basis = ActionabilityClassificationBasis.EXECUTABLE_POOR_LOCATION
    elif setup.entry_mode is EntryMode.PULLBACK:
        state = ActionabilityState.PLACE_LIMIT
        basis = ActionabilityClassificationBasis.LIMIT_ZONE
    elif setup.entry_mode is EntryMode.SCALED_ENTRY:
        state = ActionabilityState.PLACE_LIMIT_WITH_ACTIVATION
        basis = ActionabilityClassificationBasis.LIMIT_WITH_ACTIVATION
    elif setup.entry_mode is EntryMode.RETEST:
        state = ActionabilityState.RETEST_PREFERRED
        basis = ActionabilityClassificationBasis.RETEST_PATH
    elif setup.entry_mode is EntryMode.SWEEP_RECOVERY:
        state = ActionabilityState.RECLAIM_REQUIRED
        basis = ActionabilityClassificationBasis.RECLAIM_PATH
    elif setup.entry_mode is EntryMode.MARKET_NEAR:
        state = ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION
        basis = ActionabilityClassificationBasis.NEAR_ZONE_MICRO_CONFIRMATION
    else:
        state = ActionabilityState.DEVELOPING
        basis = ActionabilityClassificationBasis.DEFINED_BUT_IMMATURE

    return ActionabilityStateAssessment(
        state=state,
        basis=basis,
        source_entry_status=setup.entry_status,
        execution_allowed_now=setup.execution_allowed_now,
        location_state=distance.location_state,
        sequence_role=sequence_role,
        issues=tuple(issues),
        has_blocking_issue=blocking,
        is_legacy_projection=False,
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

    canonical_role = classify_setup_sequence_role(setup)
    if sequence_role is SequenceRole.NEARBY and canonical_role is SequenceRole.CURRENT:
        codes.append(ActionabilityConsistencyCode.NEARBY_ROLE_EXECUTION_AUTHORIZED)

    if sequence_role is SequenceRole.CURRENT and canonical_role is SequenceRole.NEARBY:
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
    lane: OpportunityLane | None = None

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity identity cannot be empty")
        if self.setup.candidate_id != self.opportunity_id:
            raise ValueError("opportunity identity must match the wrapped setup candidate")
        if self.sequence_role in {SequenceRole.CURRENT, SequenceRole.NEARBY}:
            expected_role = classify_setup_sequence_role(self.setup)
            if self.sequence_role is not expected_role:
                raise ValueError(
                    "current opportunities must authorize execution now or satisfy "
                    "canonical actionability; nearby opportunities must remain pending"
                )
        if not setup_is_portfolio_eligible(self.setup):
            raise ValueError("invalidated or chased setups cannot be portfolio opportunities")
        if (
            self.sequence_role is SequenceRole.RUNNER
            and self.effective_lane is not OpportunityLane.RUNNER
        ):
            raise ValueError("runner opportunities must use the runner lane")

    @property
    def direction(self) -> TradeDirection:
        """Return the wrapped setup direction."""

        return self.setup.direction

    @property
    def effective_lane(self) -> OpportunityLane:
        """Return the explicit lane or derive it from immutable setup semantics."""

        return self.lane or classify_setup_opportunity_lane(
            self.setup,
            sequence_role=self.sequence_role,
        )


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
    retention_diagnostics: dict[str, Any] | None = None

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

    @property
    def all_opportunities(self) -> tuple[TradeOpportunity, ...]:
        """Backward-compatible alias for every populated opportunity."""

        return self.opportunities

    @property
    def best_opportunities_by_lane(self) -> tuple[TradeOpportunity, ...]:
        """Return the highest-ranked retained opportunity per lane and direction."""

        retained: list[TradeOpportunity] = []
        seen: set[tuple[OpportunityLane, TradeDirection]] = set()
        for opportunity in self.opportunities:
            key = (opportunity.effective_lane, opportunity.direction)
            if key in seen:
                continue
            seen.add(key)
            retained.append(opportunity)
        return tuple(retained)

    @property
    def current_opportunities(self) -> tuple[TradeOpportunity, ...]:
        """Return CMP opportunities, including confirmation-pending setups."""

        return tuple(item for item in (self.current_long, self.current_short) if item is not None)

    @property
    def execution_ready_opportunities(self) -> tuple[TradeOpportunity, ...]:
        """Return current opportunities that actually authorize execution now."""

        return tuple(
            opportunity
            for opportunity in self.current_opportunities
            if opportunity.setup.execution_allowed_now
            and not build_actionability_state_assessment(
                opportunity.setup,
                sequence_role=SequenceRole.CURRENT,
            ).has_blocking_issue
        )

    @property
    def nearby_opportunities(self) -> tuple[TradeOpportunity, ...]:
        """Return planned nearby opportunities in deterministic side order."""

        return tuple(item for item in (self.nearby_long, self.nearby_short) if item is not None)

    @property
    def public_decision(self) -> PortfolioDecisionState:
        """Return the canonical public decision represented by populated slots."""

        if self.execution_ready_opportunities:
            return PortfolioDecisionState.ACTIONABLE_AT_CMP
        if self.current_opportunities:
            return PortfolioDecisionState.CONFIRMATION_AT_CMP
        if self.nearby_opportunities:
            return PortfolioDecisionState.NEARBY_SETUP_AVAILABLE
        if self.follow_up_opportunities:
            return PortfolioDecisionState.FOLLOW_UP_AVAILABLE
        if self.runner_plan is not None:
            return PortfolioDecisionState.RUNNER_MANAGEMENT
        return PortfolioDecisionState.NO_VALID_SETUP

    @property
    def primary_opportunity(self) -> TradeOpportunity | None:
        """Return the highest-priority opportunity using stable slot precedence."""

        return next(iter(self.opportunities), None)

    def has_direction(self, direction: TradeDirection) -> bool:
        """Return whether any retained opportunity uses the requested direction."""

        return any(item.direction is direction for item in self.opportunities)


def _semantic_setup_identity(setup: DiscoverySetup) -> tuple[object, ...]:
    """Return a conservative identity for merging equivalent candidate theses."""

    return (
        setup.direction,
        setup.strategy.canonical_family,
        build_actionability_state_assessment(
            setup,
            sequence_role=classify_setup_sequence_role(setup),
        ).state,
        round(setup.entry.lower, 8),
        round(setup.entry.upper, 8),
        round(setup.entry.preferred, 8),
        round(setup.entry.maximum_chase_price, 8),
        round(setup.stop_loss.price, 8),
    )


_SCALP_STRATEGIES = {
    StrategyType.MOMENTUM_SCALP,
    StrategyType.VWAP_RECLAIM_REJECTION,
    StrategyType.RANGE_REVERSAL,
    StrategyType.FAILED_BREAKOUT_REVERSAL,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL,
    StrategyType.EXHAUSTION_REVERSAL,
}


def classify_setup_opportunity_lane(
    setup: DiscoverySetup,
    *,
    sequence_role: SequenceRole,
) -> OpportunityLane:
    """Assign one deterministic methodology lane without using score thresholds."""

    if sequence_role is SequenceRole.RUNNER:
        return OpportunityLane.RUNNER
    if sequence_role is SequenceRole.FOLLOW_UP:
        return OpportunityLane.DEVELOPING

    if sequence_role is SequenceRole.NEARBY:
        if setup.entry_mode in {EntryMode.PULLBACK, EntryMode.SCALED_ENTRY}:
            return OpportunityLane.PULLBACK_SCALP
        if setup.strategy in _SCALP_STRATEGIES:
            return OpportunityLane.PULLBACK_SCALP
        return OpportunityLane.NEARBY_STRUCTURED

    assessment = build_actionability_state_assessment(
        setup,
        sequence_role=sequence_role,
    )
    confirmation_pending = assessment.state in {
        ActionabilityState.EXECUTE_ON_MICRO_CONFIRMATION,
        ActionabilityState.PLACE_LIMIT_WITH_ACTIVATION,
        ActionabilityState.RETEST_PREFERRED,
        ActionabilityState.RECLAIM_REQUIRED,
    }
    if setup.confirmation_required and not setup.confirmation_complete:
        confirmation_pending = True
    return OpportunityLane.CONFIRMATION_SCALP if confirmation_pending else OpportunityLane.CMP_SCALP


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

    from apex.application.portfolio_retention import (
        build_portfolio_retention_audit,
        portfolio_retention_audit_payload,
    )

    materialized_setups = tuple(setups)
    retention_audit = build_portfolio_retention_audit(materialized_setups)
    retained_ids = set(retention_audit.retained_candidate_ids)
    retained_setups = sorted(
        (setup for setup in materialized_setups if setup.candidate_id in retained_ids),
        key=lambda setup: (-setup.confidence_score, setup.candidate_id),
    )

    current_long: TradeOpportunity | None = None
    current_short: TradeOpportunity | None = None
    nearby_long: TradeOpportunity | None = None
    nearby_short: TradeOpportunity | None = None
    follow_ups: list[TradeOpportunity] = []

    for setup in retained_setups:
        if setup.symbol != symbol:
            raise ValueError("setup symbol must match portfolio symbol")

        role = classify_setup_sequence_role(setup)
        lane = classify_setup_opportunity_lane(setup, sequence_role=role)
        opportunity = TradeOpportunity(setup.candidate_id, setup, role, lane)
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
                lane,
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
        follow_up_opportunities=tuple(follow_ups),
        retention_diagnostics=portfolio_retention_audit_payload(retention_audit),
    )


def portfolio_from_legacy_assessment(
    assessment: DiscoveryAssessment,
    *,
    cmp: float,
    analysis_mode: AnalysisMode,
) -> SymbolOpportunityPortfolio:
    """Adapt legacy setup fields through the canonical portfolio selector.

    Legacy selected and developing fields are inputs only. They cannot bypass
    eligibility, duplicate, lane-retention, or collision handling.
    """

    setups = tuple(
        setup for setup in (assessment.setup, assessment.developing_setup) if setup is not None
    )
    return portfolio_from_setups(
        setups,
        symbol=assessment.symbol,
        cmp=cmp,
        analysis_timestamp=assessment.decision_time,
        analysis_mode=analysis_mode,
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
            "lane": opportunity.effective_lane.value,
            "direction": setup.direction.value,
            "strategy": setup.strategy.value,
            "strategy_family": setup.strategy.canonical_family.value,
            "entry_status": setup.entry_status.value,
            **(
                {
                    "entry_mode": setup.entry_mode.value,
                    "confirmation_required": setup.confirmation_required,
                    "confirmation_complete": setup.confirmation_complete,
                    "provisional": setup.provisional,
                }
                if setup.canonical_actionability
                else {}
            ),
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
            **(
                {
                    "conditional_plan": {
                        "trigger": {
                            "type": setup.conditional_plan.trigger.kind.value,
                            "level": setup.conditional_plan.trigger.level,
                            "condition": setup.conditional_plan.trigger.condition,
                            "confirmation_timeframe": (
                                setup.conditional_plan.trigger.confirmation_timeframe
                            ),
                        },
                        "pre_entry_invalidation": {
                            "price": setup.conditional_plan.pre_entry_invalidation.price,
                            "condition": (setup.conditional_plan.pre_entry_invalidation.condition),
                            "rationale": list(
                                setup.conditional_plan.pre_entry_invalidation.rationale
                            ),
                        },
                        "conditional_order_eligible": (
                            setup.conditional_plan.conditional_order_eligible
                        ),
                        "recommended_order_intent": (
                            setup.conditional_plan.recommended_order_intent.value
                        ),
                        "reason_not_executable_now": (
                            setup.conditional_plan.reason_not_executable_now
                        ),
                        "expiry": {
                            "seconds": setup.setup_expiry_seconds,
                            "bars": setup.setup_expiry_bars,
                            "reason": setup.setup_expiry_reason,
                        },
                        "geometry": {
                            "geometry_basis": setup.conditional_plan.geometry_basis,
                            "entry_source": setup.conditional_plan.entry_source,
                            "trigger_matches_preferred_entry": (
                                setup.conditional_plan.trigger_matches_preferred_entry
                            ),
                            "stop_basis": setup.conditional_plan.stop_basis,
                            "targets_basis": setup.conditional_plan.targets_basis,
                            "geometry_is_trigger_relative": (
                                setup.conditional_plan.geometry_is_trigger_relative
                            ),
                        },
                    }
                }
                if setup.conditional_plan is not None
                else {}
            ),
        }

    best_by_lane: dict[str, list[dict[str, Any]]] = {}
    for opportunity in portfolio.best_opportunities_by_lane:
        serialized = serialize(opportunity)
        assert serialized is not None
        best_by_lane.setdefault(opportunity.effective_lane.value, []).append(serialized)

    return {
        "symbol": portfolio.symbol,
        "cmp": portfolio.cmp,
        "analysis_timestamp": portfolio.analysis_timestamp.isoformat(),
        "analysis_mode": portfolio.analysis_mode.value,
        "retention_diagnostics": portfolio.retention_diagnostics,
        "public_decision": portfolio.public_decision.value,
        "primary_opportunity_id": (
            None
            if portfolio.primary_opportunity is None
            else portfolio.primary_opportunity.opportunity_id
        ),
        "current_long": serialize(portfolio.current_long),
        "current_short": serialize(portfolio.current_short),
        "nearby_long": serialize(portfolio.nearby_long),
        "nearby_short": serialize(portfolio.nearby_short),
        "follow_up_opportunities": [
            serialize(opportunity) for opportunity in portfolio.follow_up_opportunities
        ],
        "runner_plan": serialize(portfolio.runner_plan),
        "best_opportunities_by_lane": best_by_lane,
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
    "OpportunityLane",
    "PortfolioDecisionState",
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
    "classify_setup_opportunity_lane",
    "classify_setup_sequence_role",
    "opportunity_portfolio_payload",
    "portfolio_from_legacy_assessment",
    "portfolio_from_setups",
]
