"""Overlay N3 candidate-quality decisions onto deterministic Phase 5 ranking."""

from __future__ import annotations

from dataclasses import replace

from apex.config.strategy_approval import StrategyApprovalConfig
from apex.domain import RiskMode
from apex.scoring.contracts import CandidateOutcome, RankedCandidate
from apex.scoring.quality_gate import evaluate_candidate_quality_gate

_ALREADY_REJECTED = {
    CandidateOutcome.REJECTED_CONTRADICTION,
    CandidateOutcome.REJECTED_DUPLICATE,
    CandidateOutcome.REJECTED_BELOW_THRESHOLD,
}


def apply_strategy_quality_gate(
    ranked: tuple[RankedCandidate, ...],
    *,
    risk_mode: RiskMode,
    config: StrategyApprovalConfig,
) -> tuple[RankedCandidate, ...]:
    """Reject candidates that fail N3 while preserving deterministic rank order."""

    gated: list[RankedCandidate] = []
    for item in ranked:
        if item.outcome in _ALREADY_REJECTED:
            gated.append(item)
            continue

        decision = evaluate_candidate_quality_gate(
            item.scored,
            risk_mode=risk_mode,
            config=config,
        )
        reason_text = tuple(
            f"{reason.code.value}: {reason.message}" for reason in decision.reasons
        )
        if decision.approved:
            gated.append(replace(item, reasons=(*item.reasons, *reason_text)))
            continue

        gated.append(
            replace(
                item,
                outcome=CandidateOutcome.REJECTED_BELOW_THRESHOLD,
                reasons=(*item.reasons, *reason_text),
            )
        )
    return tuple(gated)
