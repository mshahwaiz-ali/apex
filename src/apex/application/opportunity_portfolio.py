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
    "AnalysisMode",
    "CmpActionabilityDiagnostics",
    "CmpActionabilityState",
    "CmpDistanceDiagnostics",
    "CmpLocationState",
    "CmpZonePosition",
    "SequenceRole",
    "SymbolOpportunityPortfolio",
    "TradeOpportunity",
    "build_cmp_actionability_diagnostics",
    "build_cmp_distance_diagnostics",
    "classify_cmp_location_state",
    "classify_setup_sequence_role",
    "opportunity_portfolio_payload",
    "portfolio_from_legacy_assessment",
    "portfolio_from_setups",
]
