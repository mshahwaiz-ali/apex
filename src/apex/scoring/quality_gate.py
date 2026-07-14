"""Candidate-level N3 quality guards for controlled futures approval."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.config.strategy_approval import StrategyApprovalConfig
from apex.domain import RiskMode
from apex.scoring.contracts import ScoredCandidate
from apex.strategies import EntryMode, StrategyType


class QualityGateReasonCode(StrEnum):
    """Stable machine-readable candidate quality reasons."""

    STRATEGY_SCORE_BELOW_MODE_THRESHOLD = "STRATEGY_SCORE_BELOW_MODE_THRESHOLD"
    DIRECT_BREAKOUT_EXTENSION_TOO_HIGH = "DIRECT_BREAKOUT_EXTENSION_TOO_HIGH"
    DIRECT_BREAKOUT_VOLUME_TOO_WEAK = "DIRECT_BREAKOUT_VOLUME_TOO_WEAK"
    DIRECT_BREAKOUT_TARGET_SPACE_INSUFFICIENT = "DIRECT_BREAKOUT_TARGET_SPACE_INSUFFICIENT"
    BREAKOUT_RETEST_PREFERRED = "BREAKOUT_RETEST_PREFERRED"
    MOMENTUM_EXTENSION_TOO_HIGH = "MOMENTUM_EXTENSION_TOO_HIGH"
    MOMENTUM_VOLUME_CONFIRMATION_MISSING = "MOMENTUM_VOLUME_CONFIRMATION_MISSING"
    MOMENTUM_QUALITY_INSUFFICIENT = "MOMENTUM_QUALITY_INSUFFICIENT"
    GAINER_PROVISIONAL_EVIDENCE = "GAINER_PROVISIONAL_EVIDENCE"


@dataclass(frozen=True, slots=True)
class QualityGateReason:
    code: QualityGateReasonCode
    message: str
    blocking: bool

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("quality-gate reason message cannot be empty")

    def to_payload(self) -> dict[str, str | bool]:
        return {
            "code": self.code.value,
            "message": self.message,
            "blocking": self.blocking,
        }


@dataclass(frozen=True, slots=True)
class CandidateQualityGateDecision:
    approved: bool
    required_score: float
    reasons: tuple[QualityGateReason, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.required_score <= 100.0:
            raise ValueError("required score must be between zero and 100")
        if self.approved and any(reason.blocking for reason in self.reasons):
            raise ValueError("approved quality decision cannot contain blocking reasons")
        if not self.approved and not any(reason.blocking for reason in self.reasons):
            raise ValueError("rejected quality decision requires a blocking reason")

    def to_payload(self) -> dict[str, object]:
        return {
            "approved": self.approved,
            "required_score": self.required_score,
            "reasons": [reason.to_payload() for reason in self.reasons],
        }


def evaluate_candidate_quality_gate(
    candidate: ScoredCandidate,
    *,
    risk_mode: RiskMode,
    config: StrategyApprovalConfig,
) -> CandidateQualityGateDecision:
    """Apply strategy-specific score and structure guards without rescoring."""

    strategy = candidate.candidate.strategy
    entry_mode = candidate.candidate.entry.mode
    quality = candidate.candidate.quality
    required_score = config.minimum_score_for(strategy, risk_mode)
    reasons: list[QualityGateReason] = []

    if strategy is StrategyType.BREAKOUT_CONTINUATION and entry_mode is EntryMode.RETEST:
        required_score = max(0.0, required_score - 8.0)
        reasons.append(
            QualityGateReason(
                code=QualityGateReasonCode.BREAKOUT_RETEST_PREFERRED,
                message=(
                    "Breakout retest receives the controlled-entry threshold adjustment "
                    f"to {required_score:.2f}."
                ),
                blocking=False,
            )
        )

    if candidate.final_score < required_score:
        reasons.append(
            QualityGateReason(
                code=QualityGateReasonCode.STRATEGY_SCORE_BELOW_MODE_THRESHOLD,
                message=(
                    f"{strategy.value} scored {candidate.final_score:.2f} but "
                    f"{risk_mode.value} requires {required_score:.2f}."
                ),
                blocking=True,
            )
        )

    if strategy is StrategyType.BREAKOUT_CONTINUATION and entry_mode is not EntryMode.RETEST:
        if quality.extension_penalty > 0.45:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.DIRECT_BREAKOUT_EXTENSION_TOO_HIGH,
                    message="Direct breakout extension penalty exceeds the controlled limit.",
                    blocking=True,
                )
            )
        if quality.volume_quality < 0.65:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.DIRECT_BREAKOUT_VOLUME_TOO_WEAK,
                    message="Direct breakout lacks the required volume quality.",
                    blocking=True,
                )
            )
        if quality.target_space_quality < 0.60:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.DIRECT_BREAKOUT_TARGET_SPACE_INSUFFICIENT,
                    message="Direct breakout target space is insufficient after entry.",
                    blocking=True,
                )
            )

    if strategy in {
        StrategyType.MOMENTUM_CONTINUATION,
        StrategyType.MOMENTUM_GAINER_CONTINUATION,
    }:
        if quality.extension_penalty > 0.40:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.MOMENTUM_EXTENSION_TOO_HIGH,
                    message="Momentum setup is too extended for controlled approval.",
                    blocking=True,
                )
            )
        if quality.volume_quality < 0.70:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.MOMENTUM_VOLUME_CONFIRMATION_MISSING,
                    message="Momentum setup lacks required volume confirmation.",
                    blocking=True,
                )
            )
        if quality.momentum_quality < 0.70:
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.MOMENTUM_QUALITY_INSUFFICIENT,
                    message="Momentum quality is below the controlled minimum.",
                    blocking=True,
                )
            )
        if (
            strategy is StrategyType.MOMENTUM_GAINER_CONTINUATION
            and candidate.candidate.provisional
        ):
            reasons.append(
                QualityGateReason(
                    code=QualityGateReasonCode.GAINER_PROVISIONAL_EVIDENCE,
                    message="Provisional gainer evidence cannot receive controlled approval.",
                    blocking=risk_mode is RiskMode.STANDARD,
                )
            )

    blocking = any(reason.blocking for reason in reasons)
    return CandidateQualityGateDecision(
        approved=not blocking,
        required_score=required_score,
        reasons=tuple(reasons),
    )
