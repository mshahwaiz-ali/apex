"""Unified read-only composition for Batch 9 market evidence."""

from __future__ import annotations

from dataclasses import dataclass

from apex.strategies.depth_imbalance import (
    DepthImbalanceAudit,
    DepthImbalanceState,
)
from apex.strategies.liquidation_impulse import (
    LiquidationImpulseAudit,
    LiquidationImpulseState,
)
from apex.strategies.market_evidence import (
    DataQualityDisposition,
    MarketEvidenceSetAudit,
)
from apex.strategies.market_evidence_decisions import (
    EvidenceDecision,
    EvidenceDecisionArea,
    EvidenceDecisionImpact,
    MarketEvidenceDecisionBundle,
)


@dataclass(frozen=True, slots=True)
class UnifiedMarketEvidenceAudit:
    """Combined evidence quality and advisory decision result."""

    quality: MarketEvidenceSetAudit
    decisions: MarketEvidenceDecisionBundle

    @property
    def blocks_activation(self) -> bool:
        return self.decisions.blocks_activation

    @property
    def blocks_execution(self) -> bool:
        return self.decisions.blocks_execution

    @property
    def continuation_caution(self) -> bool:
        return self.decisions.continuation_caution

    @property
    def data_sufficient(self) -> bool:
        return self.quality.disposition is not DataQualityDisposition.INSUFFICIENT

    @property
    def degraded(self) -> bool:
        return self.quality.disposition is DataQualityDisposition.DEGRADED


def decision_from_depth(
    audit: DepthImbalanceAudit | None,
) -> EvidenceDecision:
    """Tie optional near-touch depth to activation quality."""

    if audit is None or audit.state is DepthImbalanceState.INSUFFICIENT:
        impact = EvidenceDecisionImpact.UNAVAILABLE
        reason = "depth imbalance evidence is unavailable"
    elif audit.state is DepthImbalanceState.SUPPORTIVE:
        impact = EvidenceDecisionImpact.SUPPORTS
        reason = "near-touch depth supports the proposed direction"
    elif audit.state is DepthImbalanceState.CONTRADICTORY:
        impact = EvidenceDecisionImpact.CAUTION
        reason = "near-touch depth opposes the proposed direction"
    else:
        impact = EvidenceDecisionImpact.NEUTRAL
        reason = "near-touch depth is balanced"
    return EvidenceDecision(
        source="depth_imbalance",
        area=EvidenceDecisionArea.ACTIVATION,
        impact=impact,
        reason=reason,
    )


def decision_from_liquidation_impulse(
    audit: LiquidationImpulseAudit | None,
) -> EvidenceDecision:
    """Tie optional liquidation impulse to activation confirmation."""

    if audit is None or audit.state is LiquidationImpulseState.INSUFFICIENT:
        impact = EvidenceDecisionImpact.UNAVAILABLE
        reason = "liquidation impulse evidence is unavailable"
    elif audit.state is LiquidationImpulseState.SUPPORTIVE:
        impact = EvidenceDecisionImpact.SUPPORTS
        reason = "forced-liquidation flow supports the proposed direction"
    elif audit.state is LiquidationImpulseState.CONTRADICTORY:
        impact = EvidenceDecisionImpact.CAUTION
        reason = "forced-liquidation flow opposes the proposed direction"
    else:
        impact = EvidenceDecisionImpact.NEUTRAL
        reason = "forced-liquidation flow is balanced"
    return EvidenceDecision(
        source="liquidation_impulse",
        area=EvidenceDecisionArea.ACTIVATION,
        impact=impact,
        reason=reason,
    )


def compose_unified_market_evidence(
    *,
    quality: MarketEvidenceSetAudit,
    core: MarketEvidenceDecisionBundle,
    depth: DepthImbalanceAudit | None,
    liquidation: LiquidationImpulseAudit | None,
) -> UnifiedMarketEvidenceAudit:
    """Append optional evidence without silently converting absence into opposition."""

    decisions = MarketEvidenceDecisionBundle(
        decisions=(
            *core.decisions,
            decision_from_depth(depth),
            decision_from_liquidation_impulse(liquidation),
        )
    )
    return UnifiedMarketEvidenceAudit(
        quality=quality,
        decisions=decisions,
    )


__all__ = [
    "UnifiedMarketEvidenceAudit",
    "compose_unified_market_evidence",
    "decision_from_depth",
    "decision_from_liquidation_impulse",
]
