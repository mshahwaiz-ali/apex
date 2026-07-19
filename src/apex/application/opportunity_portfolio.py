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

        if setup.execution_allowed_now:
            opportunity = TradeOpportunity(setup.candidate_id, setup, SequenceRole.CURRENT)
            if setup.direction is TradeDirection.LONG and current_long is None:
                current_long = opportunity
                continue
            if setup.direction is TradeDirection.SHORT and current_short is None:
                current_short = opportunity
                continue
        else:
            opportunity = TradeOpportunity(setup.candidate_id, setup, SequenceRole.NEARBY)
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

        role = (
            SequenceRole.CURRENT
            if setup.execution_allowed_now and not developing
            else SequenceRole.NEARBY
        )
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
        return {
            "opportunity_id": opportunity.opportunity_id,
            "sequence_role": opportunity.sequence_role.value,
            "direction": setup.direction.value,
            "strategy": setup.strategy.value,
            "strategy_family": setup.strategy.canonical_family.value,
            "entry_status": setup.entry_status.value,
            "execution_allowed_now": setup.execution_allowed_now,
            "cmp": setup.entry.current_price,
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
    "SequenceRole",
    "SymbolOpportunityPortfolio",
    "TradeOpportunity",
    "opportunity_portfolio_payload",
    "portfolio_from_legacy_assessment",
    "portfolio_from_setups",
]
