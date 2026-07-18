"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

import apex.application.decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_selected_strategy_verdict import (
    derive_selected_strategy_verdict,
    selected_strategy_verdict_payload,
)
from apex.application.methodology_setup_maturity import (
    SetupMaturityAssessment,
    derive_setup_maturity,
    setup_maturity_payload,
)
from apex.application.methodology_snapshot import methodology_snapshot_payload
from apex.application.methodology_strategy_contracts import SetupMaturity
from apex.application.methodology_strategy_enforcement import (
    derive_strategy_enforcement_registry,
    strategy_enforcement_payload,
)
from apex.application.methodology_strategy_evaluation import (
    evaluate_strategy_registry,
    strategy_eligibility_evaluation_payload,
)

_LEGACY_PUBLIC_KEYS = frozenset({"near_miss_state"})
_UNAVAILABLE_MATURITIES = frozenset(
    {
        SetupMaturity.ENTRY_LATE,
        SetupMaturity.ENTRY_MISSED,
        SetupMaturity.PATTERN_FAILED,
        SetupMaturity.INVALIDATED,
    }
)


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Return one discovery result with methodology-aware actionability."""

    payload = _without_legacy_keys(_decision.serialize_symbol_analysis(analysis))
    methodology = project_analysis_methodology(analysis)
    payload["methodology"] = methodology_snapshot_payload(methodology)
    eligibility = evaluate_strategy_registry(
        market_state=(
            None if methodology.market_state is None else methodology.market_state.primary
        ),
        evidence=methodology.evidence,
    )
    enforcement = derive_strategy_enforcement_registry(eligibility)
    payload["methodology_strategy_eligibility"] = [
        strategy_eligibility_evaluation_payload(item) for item in eligibility
    ]
    payload["methodology_strategy_enforcement_shadow"] = [
        strategy_enforcement_payload(item) for item in enforcement
    ]
    selected_strategy = (
        None if analysis.assessment.setup is None else analysis.assessment.setup.strategy
    )
    payload["methodology_selected_strategy_verdict"] = selected_strategy_verdict_payload(
        derive_selected_strategy_verdict(
            selected_strategy=selected_strategy,
            decisions=enforcement,
        )
    )
    selected_setup = analysis.assessment.setup
    developing_setup = analysis.assessment.developing_setup
    effective_setup = selected_setup or developing_setup
    maturity = (
        None
        if effective_setup is None
        else derive_setup_maturity(
            effective_setup.strategy,
            effective_setup.entry_status,
        )
    )
    payload["methodology_setup_maturity"] = (
        None if maturity is None else setup_maturity_payload(maturity)
    )
    payload["execution_ready"] = (
        False if maturity is None else maturity.execution_conditions_complete
    )

    setup = payload.get("setup")
    if not isinstance(setup, dict):
        developing = payload.get("developing_setup")
        if isinstance(developing, dict):
            status = developing.get("entry_status")
            payload["entry_status"] = status
            payload["strategy"] = developing.get("strategy")
            payload["confidence_score"] = developing.get("confidence_score")
            payload["decision_reason_code"] = _selected_reason_code(maturity, status)
            payload["result_group"] = _result_group(maturity)
            return cast(dict[str, Any], payload)
        payload["entry_status"] = None
        payload["strategy"] = None
        payload["confidence_score"] = None
        payload["decision_reason_code"] = _no_trade_reason_code(analysis)
        methodology_reason = _methodology_no_trade_reason(analysis)
        if methodology_reason is not None:
            payload["reasons"] = [methodology_reason]
        payload["result_group"] = "no_trade"
        return cast(dict[str, Any], payload)

    status = setup.get("entry_status")
    payload["entry_status"] = status
    payload["strategy"] = setup.get("strategy")
    payload["confidence_score"] = setup.get("confidence_score")
    payload["decision_reason_code"] = _selected_reason_code(maturity, status)
    payload["result_group"] = _result_group(maturity)
    return cast(dict[str, Any], payload)


def serialize_scan_result(
    result: ScanResult,
    *,
    display_limit: int = _decision.DEFAULT_SCAN_DISPLAY_LIMIT,
    direction: str = "both",
) -> dict[str, Any]:
    """Return ranked scan output grouped by methodology actionability."""

    if display_limit < 1:
        raise ValueError("display limit must be positive")
    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"long", "short", "both"}:
        raise ValueError("direction must be one of: long, short, both")

    ranked = (
        result.analyses
        if normalized_direction == "both"
        else tuple(
            item
            for item in result.analyses
            if (effective := item.assessment.setup or item.assessment.developing_setup) is not None
            and effective.direction.value == normalized_direction
        )
    )
    displayed = tuple(ranked[:display_limit])
    serialized = [serialize_symbol_analysis(item) for item in displayed]
    actionable = [item for item in serialized if item.get("result_group") == "actionable"]
    developing = [item for item in serialized if item.get("result_group") == "developing"]
    unavailable = [item for item in serialized if item.get("result_group") == "unavailable"]
    no_trade = [item for item in serialized if item.get("result_group") == "no_trade"]
    selected = [item for item in serialized if item.get("setup") is not None]
    valid = [
        item
        for item in serialized
        if item.get("setup") is not None or item.get("developing_setup") is not None
    ]
    maturity_counts = Counter(
        str(maturity["maturity"])
        for item in valid
        if isinstance((maturity := item.get("methodology_setup_maturity")), Mapping)
        and maturity.get("maturity") is not None
    )
    status_counts = Counter(
        str(item["entry_status"]) for item in valid if item.get("entry_status") is not None
    )
    long_count = sum(_effective_direction(item) == "long" for item in valid)
    short_count = sum(_effective_direction(item) == "short" for item in valid)
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": selected[0] if selected else None,
        "best_actionable": actionable[0] if actionable else None,
        "best_developing": developing[0] if developing else None,
        "actionable_setups": actionable,
        "developing_setups": developing,
        "unavailable_setups": unavailable,
        "no_trade_results": no_trade,
        "results": serialized,
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(serialized),
        "display_limit": display_limit,
        "direction_filter": normalized_direction,
        "selected_setup_count": len(selected),
        "execution_ready_count": len(actionable),
        "actionable_count": len(actionable),
        "developing_count": len(developing),
        "unavailable_count": len(unavailable),
        "no_trade_count": len(no_trade),
        "long_candidate_count": long_count,
        "short_candidate_count": short_count,
        "status_counts": dict(sorted(status_counts.items())),
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "failures": dict(result.failures),
    }


def _effective_direction(item: Mapping[str, Any]) -> str | None:
    setup = item.get("setup")
    if not isinstance(setup, Mapping):
        setup = item.get("developing_setup")
    if not isinstance(setup, Mapping):
        return None
    direction = setup.get("direction")
    return None if direction is None else str(direction)


def _selected_reason_code(
    maturity: SetupMaturityAssessment | None,
    legacy_status: object,
) -> str:
    if maturity is None:
        return str(legacy_status)
    if maturity.execution_conditions_complete:
        return maturity.legacy_status.value
    return maturity.reason_codes[0]


def _result_group(maturity: SetupMaturityAssessment | None) -> str:
    if maturity is None:
        return "no_trade"
    if maturity.execution_conditions_complete:
        return "actionable"
    if maturity.maturity in _UNAVAILABLE_MATURITIES:
        return "unavailable"
    return "developing"


def _no_trade_reason_code(analysis: SymbolAnalysis) -> str:
    diagnostics = analysis.phase5_diagnostics or {}
    methodology_routing = diagnostics.get("methodology_candidate_routing")
    if (
        isinstance(methodology_routing, Mapping)
        and methodology_routing.get("all_generated_candidates_suppressed") is True
    ):
        return "METHODOLOGY_ALL_CANDIDATES_SUPPRESSED"
    gate = analysis.methodology_gate
    if isinstance(gate, Mapping) and gate.get("changed") is True:
        return "METHODOLOGY_SELECTED_STRATEGY_SUPPRESSED"
    return "NO_TRADE"


def _methodology_no_trade_reason(analysis: SymbolAnalysis) -> str | None:
    diagnostics = analysis.phase5_diagnostics or {}
    methodology_routing = diagnostics.get("methodology_candidate_routing")
    if not isinstance(methodology_routing, Mapping):
        return None
    if methodology_routing.get("all_generated_candidates_suppressed") is not True:
        return None
    strategies = methodology_routing.get("suppressed_strategies")
    if isinstance(strategies, Sequence) and not isinstance(strategies, str | bytes):
        strategy_names = ", ".join(str(item) for item in strategies) or "generated strategies"
    else:
        strategy_names = "generated strategies"
    return f"methodology suppressed all generated candidates: {strategy_names}"


def _without_legacy_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_legacy_keys(item)
            for key, item in value.items()
            if str(key) not in _LEGACY_PUBLIC_KEYS
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_without_legacy_keys(item) for item in value]
    return value


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]
