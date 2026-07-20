"""Apply configured methodology enforcement to one completed symbol analysis."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_selected_strategy_gate import (
    MethodologyGateMode,
    apply_selected_strategy_gate,
)
from apex.application.methodology_selected_strategy_verdict import (
    derive_selected_strategy_verdict,
    selected_strategy_verdict_payload,
)
from apex.application.methodology_strategy_enforcement import (
    derive_strategy_enforcement_registry,
)
from apex.application.methodology_strategy_evaluation import evaluate_strategy_registry


def apply_configured_methodology_gate(
    analysis: SymbolAnalysis,
    *,
    mode: MethodologyGateMode | str = MethodologyGateMode.SHADOW,
) -> SymbolAnalysis:
    """Apply the shared selected-strategy gate and retain audit metadata."""

    normalized_mode = MethodologyGateMode(mode)
    methodology = project_analysis_methodology(analysis)
    eligibility = evaluate_strategy_registry(
        market_state=(
            None if methodology.market_state is None else methodology.market_state.primary
        ),
        evidence=methodology.evidence,
    )
    enforcement = derive_strategy_enforcement_registry(eligibility)
    selected_strategy = (
        None if analysis.assessment.setup is None else analysis.assessment.setup.strategy
    )
    verdict = derive_selected_strategy_verdict(
        selected_strategy=selected_strategy,
        decisions=enforcement,
    )
    gate = apply_selected_strategy_gate(
        analysis.assessment,
        verdict,
        mode=normalized_mode,
    )
    gate_payload: dict[str, Any] = {
        "mode": gate.mode.value,
        "changed": gate.changed,
        "reason_codes": list(gate.reason_codes),
        "reasons": list(gate.reasons),
        "selected_strategy_verdict": selected_strategy_verdict_payload(verdict),
    }
    return replace(
        analysis,
        assessment=gate.assessment,
        methodology=methodology,
        methodology_gate=gate_payload,
    )


__all__ = ["apply_configured_methodology_gate"]
