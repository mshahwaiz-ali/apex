"""Truthful public-output facade shared by scan and selected-symbol analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from apex.application import public_output as _base
from apex.application.decision_analysis import DEFAULT_SCAN_DISPLAY_LIMIT
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.methodology_projection import project_analysis_methodology
from apex.application.methodology_public_enrichment import methodology_public_enrichment


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Serialize one analysis with the opportunity portfolio as public authority."""

    payload = _base.serialize_symbol_analysis(analysis)
    _project_portfolio(analysis, payload)
    methodology = project_analysis_methodology(analysis)
    payload.update(methodology_public_enrichment(analysis, methodology))
    return payload


def serialize_scan_result(
    result: ScanResult,
    *,
    display_limit: int = DEFAULT_SCAN_DISPLAY_LIMIT,
    direction: str = "both",
) -> dict[str, Any]:
    """Serialize a scan using the same portfolio projection as selected analysis."""

    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"long", "short", "both"}:
        raise ValueError("direction must be one of: long, short, both")

    ranked = tuple(
        analysis
        for analysis in result.analyses
        if normalized_direction == "both" or _portfolio_has_direction(analysis, normalized_direction)
    )
    displayed = ranked[:display_limit]
    serialized = [serialize_symbol_analysis(analysis) for analysis in displayed]
    actionable = [item for item in serialized if item.get("setup") is not None]
    developing = [
        item
        for item in serialized
        if item.get("setup") is None and item.get("developing_setup") is not None
    ]
    no_trade = [
        item
        for item in serialized
        if item.get("setup") is None and item.get("developing_setup") is None
    ]
    valid = actionable + developing
    return {
        "schema_version": 3,
        "generated_at": result.generated_at.isoformat(),
        "best_overall": valid[0] if valid else None,
        "best_actionable": actionable[0] if actionable else None,
        "best_developing": developing[0] if developing else None,
        "actionable_setups": actionable,
        "developing_setups": developing,
        "unavailable_setups": [],
        "no_trade_results": no_trade,
        "results": serialized,
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(serialized),
        "display_limit": display_limit,
        "direction_filter": normalized_direction,
        "selected_setup_count": len(actionable),
        "execution_ready_count": len(actionable),
        "actionable_count": len(actionable),
        "developing_count": len(developing),
        "unavailable_count": 0,
        "no_trade_count": len(no_trade),
        "long_candidate_count": sum(_payload_direction(item) == "long" for item in valid),
        "short_candidate_count": sum(_payload_direction(item) == "short" for item in valid),
        "failures": dict(result.failures),
    }


def _project_portfolio(analysis: SymbolAnalysis, payload: dict[str, Any]) -> None:
    portfolio = analysis.opportunity_portfolio
    if portfolio is None:
        return

    current = portfolio.current_opportunities
    nearby = portfolio.nearby_opportunities
    follow_up = portfolio.follow_up_opportunities
    primary = current[0] if current else None
    developing = nearby[0] if nearby else follow_up[0] if follow_up else None
    payload["setup"] = None if primary is None else _normalize(primary.setup)
    payload["developing_setup"] = None if developing is None else _normalize(developing.setup)
    payload["portfolio_decision"] = portfolio.public_decision.value

    effective = payload["setup"] or payload["developing_setup"]
    if not isinstance(effective, Mapping):
        payload.update(
            entry_status=None,
            strategy=None,
            confidence_score=None,
            quality_score=None,
            result_group="no_trade",
        )
        return

    payload["entry_status"] = effective.get("entry_status")
    payload["strategy"] = effective.get("strategy")
    payload["confidence_score"] = effective.get("confidence_score")
    payload["quality_score"] = effective.get("confidence_score")
    payload["result_group"] = "actionable" if primary is not None else "developing"


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_normalize(item) for item in value]
    return value


def _portfolio_has_direction(analysis: SymbolAnalysis, direction: str) -> bool:
    portfolio = analysis.opportunity_portfolio
    return portfolio is not None and portfolio.has_direction(direction)


def _payload_direction(payload: Mapping[str, Any]) -> str | None:
    setup = payload.get("setup") or payload.get("developing_setup")
    return str(setup.get("direction")) if isinstance(setup, Mapping) else None


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]