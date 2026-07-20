"""Read-only advisory decisions derived from high-value market evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.aggregate_trade_imbalance import (
    AggregateTradeImbalanceAudit,
    TradeImbalanceState,
)
from apex.strategies.price_open_interest import (
    PriceOpenInterestAudit,
    PriceOpenInterestState,
)
from apex.strategies.pullback_volume_decay import (
    PullbackVolumeAudit,
    PullbackVolumeState,
)
from apex.strategies.spread_deterioration import (
    SpreadDeteriorationAudit,
    SpreadDeteriorationState,
)


class EvidenceDecisionArea(StrEnum):
    """Explicit decision area affected by one evidence family."""

    ACTIVATION = "activation"
    EXECUTION = "execution"
    CONTINUATION = "continuation"


class EvidenceDecisionImpact(StrEnum):
    """Advisory impact without live strategy activation."""

    SUPPORTS = "supports"
    NEUTRAL = "neutral"
    CAUTION = "caution"
    BLOCKS = "blocks"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    """One explicit strategy/state decision mapping."""

    source: str
    area: EvidenceDecisionArea
    impact: EvidenceDecisionImpact
    reason: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("decision source cannot be empty")
        if not self.reason.strip():
            raise ValueError("decision reason cannot be empty")


@dataclass(frozen=True, slots=True)
class MarketEvidenceDecisionBundle:
    """Combined advisory evidence decisions for activation/execution/continuation."""

    decisions: tuple[EvidenceDecision, ...]

    @property
    def blocks_activation(self) -> bool:
        return any(
            decision.area is EvidenceDecisionArea.ACTIVATION
            and decision.impact is EvidenceDecisionImpact.BLOCKS
            for decision in self.decisions
        )

    @property
    def blocks_execution(self) -> bool:
        return any(
            decision.area is EvidenceDecisionArea.EXECUTION
            and decision.impact is EvidenceDecisionImpact.BLOCKS
            for decision in self.decisions
        )

    @property
    def continuation_caution(self) -> bool:
        return any(
            decision.area is EvidenceDecisionArea.CONTINUATION
            and decision.impact
            in {
                EvidenceDecisionImpact.CAUTION,
                EvidenceDecisionImpact.BLOCKS,
            }
            for decision in self.decisions
        )


def decision_from_trade_imbalance(
    audit: AggregateTradeImbalanceAudit,
) -> EvidenceDecision:
    """Tie aggregate-trade imbalance to activation confirmation."""

    mapping = {
        TradeImbalanceState.SUPPORTIVE: (
            EvidenceDecisionImpact.SUPPORTS,
            "aggressive flow supports the proposed direction",
        ),
        TradeImbalanceState.NEUTRAL: (
            EvidenceDecisionImpact.NEUTRAL,
            "aggressive flow is balanced",
        ),
        TradeImbalanceState.CONTRADICTORY: (
            EvidenceDecisionImpact.BLOCKS,
            "aggressive flow materially opposes activation",
        ),
        TradeImbalanceState.INSUFFICIENT: (
            EvidenceDecisionImpact.UNAVAILABLE,
            "aggregate-trade sample is insufficient",
        ),
    }
    impact, reason = mapping[audit.state]
    return EvidenceDecision(
        source="aggregate_trade_imbalance",
        area=EvidenceDecisionArea.ACTIVATION,
        impact=impact,
        reason=reason,
    )


def decision_from_price_open_interest(
    audit: PriceOpenInterestAudit,
) -> EvidenceDecision:
    """Tie price/OI behavior to activation or continuation confidence."""

    if audit.state is PriceOpenInterestState.NEW_POSITION_CONFIRMATION:
        impact = EvidenceDecisionImpact.SUPPORTS
        reason = "price movement is confirmed by new position growth"
    elif audit.state is PriceOpenInterestState.POSITION_BUILD_AGAINST_MOVE:
        impact = EvidenceDecisionImpact.BLOCKS
        reason = "open interest is building while price moves against the thesis"
    elif audit.state in {
        PriceOpenInterestState.SHORT_COVERING_OR_LONG_LIQUIDATION,
        PriceOpenInterestState.LOW_PARTICIPATION,
    }:
        impact = EvidenceDecisionImpact.CAUTION
        reason = "price movement lacks clean new-position confirmation"
    else:
        impact = EvidenceDecisionImpact.NEUTRAL
        reason = "price/open-interest relationship is neutral"
    return EvidenceDecision(
        source="price_open_interest_relationship",
        area=EvidenceDecisionArea.ACTIVATION,
        impact=impact,
        reason=reason,
    )


def decision_from_pullback_volume(
    audit: PullbackVolumeAudit,
) -> EvidenceDecision:
    """Tie pullback-volume behavior to continuation management."""

    mapping = {
        PullbackVolumeState.HEALTHY_DECAY: (
            EvidenceDecisionImpact.SUPPORTS,
            "pullback participation decays relative to the impulse",
        ),
        PullbackVolumeState.MIXED: (
            EvidenceDecisionImpact.CAUTION,
            "pullback participation is not clearly decaying",
        ),
        PullbackVolumeState.EXPANDING_AGAINST: (
            EvidenceDecisionImpact.BLOCKS,
            "pullback participation expands against continuation",
        ),
        PullbackVolumeState.INSUFFICIENT: (
            EvidenceDecisionImpact.UNAVAILABLE,
            "impulse volume is insufficient for comparison",
        ),
    }
    impact, reason = mapping[audit.state]
    return EvidenceDecision(
        source="pullback_volume_decay",
        area=EvidenceDecisionArea.CONTINUATION,
        impact=impact,
        reason=reason,
    )


def decision_from_spread(
    audit: SpreadDeteriorationAudit,
) -> EvidenceDecision:
    """Tie spread deterioration directly to execution quality."""

    mapping = {
        SpreadDeteriorationState.HEALTHY: (
            EvidenceDecisionImpact.SUPPORTS,
            "spread remains within normal execution conditions",
        ),
        SpreadDeteriorationState.DETERIORATING: (
            EvidenceDecisionImpact.CAUTION,
            "spread has widened relative to baseline",
        ),
        SpreadDeteriorationState.BLOCKING: (
            EvidenceDecisionImpact.BLOCKS,
            "spread deterioration makes execution quality unacceptable",
        ),
    }
    impact, reason = mapping[audit.state]
    return EvidenceDecision(
        source="spread_deterioration",
        area=EvidenceDecisionArea.EXECUTION,
        impact=impact,
        reason=reason,
    )


def build_market_evidence_decision_bundle(
    *,
    trade_imbalance: AggregateTradeImbalanceAudit,
    price_open_interest: PriceOpenInterestAudit,
    pullback_volume: PullbackVolumeAudit,
    spread: SpreadDeteriorationAudit,
) -> MarketEvidenceDecisionBundle:
    """Build deterministic advisory decisions from the four evidence families."""

    return MarketEvidenceDecisionBundle(
        decisions=(
            decision_from_trade_imbalance(trade_imbalance),
            decision_from_price_open_interest(price_open_interest),
            decision_from_pullback_volume(pullback_volume),
            decision_from_spread(spread),
        )
    )
