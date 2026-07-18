"""Optionally enforce the methodology verdict for the selected discovery setup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.application.methodology_selected_strategy_verdict import (
    SelectedStrategyVerdict,
    SelectedStrategyVerdictState,
)


class MethodologyGateMode(StrEnum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class MethodologyGateResult:
    assessment: DiscoveryAssessment
    mode: MethodologyGateMode
    changed: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.reason_codes or not self.reasons:
            raise ValueError("methodology gate result requires reasons")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("methodology gate reason codes must be unique")


def apply_selected_strategy_gate(
    assessment: DiscoveryAssessment,
    verdict: SelectedStrategyVerdict,
    *,
    mode: MethodologyGateMode = MethodologyGateMode.SHADOW,
) -> MethodologyGateResult:
    """Apply only explicit methodology suppression when enforcement is enabled.

    Shadow mode never changes discovery output. Enforcement mode converts a selected
    setup to no-trade only when the selected strategy verdict is explicitly
    suppressed. Deferred, unavailable, allowed, and no-setup verdicts remain
    unchanged so incomplete migration metadata cannot reject a trade.
    """

    if mode is MethodologyGateMode.SHADOW:
        return MethodologyGateResult(
            assessment=assessment,
            mode=mode,
            changed=False,
            reason_codes=("METHODOLOGY_GATE_SHADOW",),
            reasons=("methodology enforcement is running in shadow mode",),
        )

    if assessment.setup is not None and verdict.state is SelectedStrategyVerdictState.SUPPRESSED:
        reasons = tuple(verdict.reasons) or (
            "selected strategy conflicts with methodology eligibility",
        )
        return MethodologyGateResult(
            assessment=DiscoveryAssessment(
                symbol=assessment.symbol,
                decision_time=assessment.decision_time,
                setup=None,
                reasons=reasons,
            ),
            mode=mode,
            changed=True,
            reason_codes=("METHODOLOGY_SELECTED_STRATEGY_SUPPRESSED",),
            reasons=reasons,
        )

    return MethodologyGateResult(
        assessment=assessment,
        mode=mode,
        changed=False,
        reason_codes=("METHODOLOGY_GATE_NO_CHANGE",),
        reasons=("selected setup is not explicitly suppressed by methodology",),
    )


__all__ = [
    "MethodologyGateMode",
    "MethodologyGateResult",
    "apply_selected_strategy_gate",
]
