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
from apex.application.portfolio_ranking import portfolio_ranking_key
from apex.application.rollout_comparison import (
    NamedAnalysisComparison,
    analysis_comparison_payload,
    compare_analysis_outputs,
    comparison_summary_payload,
    summarize_analysis_comparisons,
)
from apex.application.target_runner_serialization import (
    serialize_assessment_target_runner_diagnostics,
)
from apex.strategies.contracts import TradeDirection


def serialize_symbol_analysis(
    analysis: SymbolAnalysis,
    *,
    include_rollout_diagnostics: bool = False,
) -> dict[str, Any]:
    """Serialize one analysis with the opportunity portfolio as public authority."""

    legacy_payload = _base.serialize_symbol_analysis(analysis)
    payload = _serialize_symbol_analysis_core(analysis, legacy_payload=legacy_payload)
    if include_rollout_diagnostics:
        payload["rollout_comparison"] = analysis_comparison_payload(
            compare_analysis_outputs(legacy_payload, payload)
        )
    return payload


def _serialize_symbol_analysis_core(
    analysis: SymbolAnalysis,
    *,
    legacy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = (
        _base.serialize_symbol_analysis(analysis)
        if legacy_payload is None
        else dict(legacy_payload)
    )
    _project_portfolio(analysis, payload)
    methodology = project_analysis_methodology(analysis)
    payload.update(methodology_public_enrichment(analysis, methodology))
    verdict = _methodology_verdict(analysis)
    payload["methodology_verdict"] = verdict
    _attach_opportunity_methodology_verdict(payload, verdict)
    _attach_setup_plan(analysis, payload)
    _attach_target_runner_diagnostics(analysis, payload)
    return payload


def serialize_scan_result(
    result: ScanResult,
    *,
    display_limit: int = DEFAULT_SCAN_DISPLAY_LIMIT,
    direction: str = "both",
    include_rollout_diagnostics: bool = False,
) -> dict[str, Any]:
    """Serialize a scan using the same portfolio projection as selected analysis."""

    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"long", "short", "both"}:
        raise ValueError("direction must be one of: long, short, both")

    globally_ranked = rank_scan_analyses(result.analyses)
    global_rank_by_symbol = {
        analysis.symbol: index for index, analysis in enumerate(globally_ranked, start=1)
    }
    ranked = tuple(
        analysis
        for analysis in globally_ranked
        if normalized_direction == "both"
        or _portfolio_has_direction(analysis, normalized_direction)
    )
    displayed = ranked[:display_limit]
    legacy_payloads = [_base.serialize_symbol_analysis(analysis) for analysis in displayed]
    serialized = [
        _serialize_symbol_analysis_core(analysis, legacy_payload=legacy_payload)
        for analysis, legacy_payload in zip(displayed, legacy_payloads, strict=True)
    ]
    for display_rank, (analysis, item) in enumerate(
        zip(displayed, serialized, strict=True),
        start=1,
    ):
        item["global_rank"] = global_rank_by_symbol[analysis.symbol]
        item["display_rank"] = display_rank
    comparisons: list[NamedAnalysisComparison] = []
    if include_rollout_diagnostics:
        for index, (analysis, legacy_payload, item) in enumerate(
            zip(displayed, legacy_payloads, serialized, strict=True)
        ):
            report = compare_analysis_outputs(legacy_payload, item)
            item["rollout_comparison"] = analysis_comparison_payload(report)
            comparisons.append(
                NamedAnalysisComparison(
                    fixture_id=f"{analysis.symbol}:{index}",
                    report=report,
                )
            )
    selected = [item for item in serialized if item.get("setup") is not None]
    actionable = [item for item in serialized if item.get("result_group") == "actionable"]
    developing = [item for item in serialized if item.get("result_group") == "developing"]
    no_trade = [
        item
        for item in serialized
        if item.get("setup") is None and item.get("developing_setup") is None
    ]
    valid = actionable + developing
    displayed_opportunities = [
        opportunity for item in serialized for opportunity in _payload_opportunities(item)
    ]
    retained_opportunities = [
        opportunity for analysis in ranked for opportunity in _analysis_opportunities(analysis)
    ]
    payload = {
        "schema_version": 5,
        "generated_at": result.generated_at.isoformat(),
        "best_overall": valid[0] if valid else None,
        "best_actionable": actionable[0] if actionable else None,
        "best_developing": developing[0] if developing else None,
        "actionable_setups": actionable,
        "developing_setups": developing,
        "unavailable_setups": [],
        "no_trade_results": no_trade,
        "results": serialized,
        "attempted_symbol_count": len(result.analyses) + len(result.failures),
        "failed_symbol_count": len(result.failures),
        "total_analysis_count": len(result.analyses),
        "displayed_analysis_count": len(serialized),
        "total_symbol_count": len(result.analyses),
        "filtered_symbol_count": len(ranked),
        "displayed_symbol_count": len(serialized),
        "retained_opportunity_count": len(retained_opportunities),
        "displayed_opportunity_count": len(displayed_opportunities),
        "current_opportunity_count": _count_opportunity_category(
            displayed_opportunities, "current"
        ),
        "nearby_opportunity_count": _count_opportunity_category(displayed_opportunities, "nearby"),
        "follow_up_opportunity_count": _count_opportunity_category(
            displayed_opportunities, "follow_up"
        ),
        "runner_opportunity_count": _count_opportunity_category(displayed_opportunities, "runner"),
        "display_limit": display_limit,
        "direction_filter": normalized_direction,
        "ranking_behavior": {
            "mode": "global_ranked_symbols_with_lane_labeled_opportunities",
            "direction_filter_stage": "after_global_ranking",
            "display_limit_stage": "after_direction_filter",
            "global_rank_is_direction_independent": True,
        },
        "selected_setup_count": len(selected),
        "execution_ready_count": len(actionable),
        "actionable_count": len(actionable),
        "developing_count": len(developing),
        "unavailable_count": 0,
        "no_trade_count": len(no_trade),
        "long_candidate_count": sum(
            opportunity.get("direction") == "long" for opportunity in displayed_opportunities
        ),
        "short_candidate_count": sum(
            opportunity.get("direction") == "short" for opportunity in displayed_opportunities
        ),
        "failures": dict(result.failures),
    }
    if include_rollout_diagnostics:
        payload["rollout_comparison_summary"] = comparison_summary_payload(
            summarize_analysis_comparisons(comparisons)
        )
    return payload


def scan_analysis_ranking_key(analysis: SymbolAnalysis) -> tuple[object, ...]:
    """Return deterministic best-first scan precedence for one symbol analysis."""

    portfolio = analysis.opportunity_portfolio
    primary = None if portfolio is None else portfolio.primary_opportunity
    if primary is None:
        return (1, analysis.symbol)
    return (0, *portfolio_ranking_key(primary.setup))


def rank_scan_analyses(
    analyses: tuple[SymbolAnalysis, ...],
) -> tuple[SymbolAnalysis, ...]:
    """Rank symbols globally before applying any display-only direction filter."""

    return tuple(sorted(analyses, key=scan_analysis_ranking_key))


def _attach_target_runner_diagnostics(
    analysis: SymbolAnalysis,
    payload: dict[str, Any],
) -> None:
    payload["target_runner_diagnostics"] = serialize_assessment_target_runner_diagnostics(
        analysis.assessment
    )


def _methodology_verdict(analysis: SymbolAnalysis) -> dict[str, Any]:
    gate = analysis.methodology_gate
    if not isinstance(gate, Mapping):
        return {
            "status": "unavailable",
            "allowed": None,
            "authoritative": False,
            "source": "methodology_gate",
            "reasons": [],
            "notice": "No canonical methodology-gate verdict was attached.",
        }

    status = _first_string(
        gate,
        ("verdict", "decision", "status", "mode", "outcome", "result"),
    )
    allowed = _first_bool(
        gate,
        ("allowed", "eligible", "passed", "accepted", "execution_allowed"),
    )
    reasons = _string_list(
        gate.get(
            "reasons",
            gate.get("reason_codes", gate.get("blocking_reasons", ())),
        )
    )
    if status is None:
        if allowed is True:
            status = "allowed"
        elif allowed is False:
            status = "blocked"
        else:
            status = "unavailable"

    return {
        "status": status,
        "allowed": allowed,
        "authoritative": True,
        "source": "methodology_gate",
        "reasons": reasons,
        "notice": "Canonical symbol-level methodology-gate verdict.",
    }


def _attach_opportunity_methodology_verdict(
    payload: dict[str, Any],
    verdict: Mapping[str, Any],
) -> None:
    portfolio = payload.get("opportunity_portfolio")
    if not isinstance(portfolio, dict):
        return

    for key in (
        "current_opportunities",
        "nearby_opportunities",
        "follow_up_opportunities",
        "runner_opportunities",
        "opportunities",
    ):
        opportunities = portfolio.get(key)
        if not isinstance(opportunities, list):
            continue
        for opportunity in opportunities:
            if isinstance(opportunity, dict):
                opportunity["methodology_verdict"] = dict(verdict)


def _attach_setup_plan(
    analysis: SymbolAnalysis,
    payload: dict[str, Any],
) -> None:
    portfolio = analysis.opportunity_portfolio
    if portfolio is not None and portfolio.opportunities:
        payload["setup_plan"] = {
            "status": portfolio.public_decision.value,
            "geometry_available": True,
            "opportunity_count": len(portfolio.opportunities),
            "primary_opportunity_id": (
                None
                if portfolio.primary_opportunity is None
                else portfolio.primary_opportunity.opportunity_id
            ),
        }
        return

    reasons = list(analysis.assessment.reasons)
    current_state, main_risk = _no_trade_summary(payload, reasons)
    payload["setup_plan"] = {
        "status": "no_valid_setup_yet",
        "geometry_available": False,
        "current_state": current_state,
        "long_trigger": None,
        "short_trigger": None,
        "invalidation": None,
        "stop": None,
        "targets": [],
        "main_risk": main_risk,
        "reasons": reasons,
        "notice": (
            "No entry, trigger, stop, or target geometry was fabricated. "
            "Re-run analysis after market structure changes."
        ),
    }


def _no_trade_summary(
    payload: Mapping[str, Any],
    reasons: list[str],
) -> tuple[str, str]:
    # Return a stage-specific no-trade summary without inventing geometry.
    fallback = "No structurally valid opportunity is available."
    ignored_reasons = {
        "no portfolio opportunity was explicitly suppressed",
        "candidate selection produced no setup",
    }
    primary_reason = next(
        (
            reason.strip()
            for reason in reasons
            if reason.strip() and reason.strip().lower() not in ignored_reasons
        ),
        "",
    )

    diagnostics = payload.get("phase5_diagnostics")
    if not isinstance(diagnostics, Mapping):
        resolved = primary_reason or fallback
        return resolved, resolved

    zero_trade = diagnostics.get("zero_trade_diagnostics")
    if not isinstance(zero_trade, Mapping):
        resolved = primary_reason or fallback
        return resolved, resolved

    summary = zero_trade.get("selection_summary")
    selection_summary = summary if isinstance(summary, Mapping) else {}
    raw_count = _non_negative_int(selection_summary.get("raw_candidate_count"))
    retained_count = _non_negative_int(selection_summary.get("retained_candidate_count"))
    ranked_count = _non_negative_int(selection_summary.get("ranked_count"))
    rejected_count = _non_negative_int(selection_summary.get("rejected_count"))

    if raw_count == 0:
        current_state = "No strategy produced a structurally valid candidate."
    elif retained_count == 0:
        current_state = (
            f"{raw_count} candidate(s) were generated, but none remained "
            "eligible after strategy and methodology routing."
        )
    elif ranked_count == 0:
        current_state = (
            f"{retained_count} routed candidate(s) reached selection, but none "
            "qualified for ranking."
        )
    elif rejected_count > 0:
        current_state = (
            f"{ranked_count} candidate(s) were ranked; no candidate satisfied "
            "the complete execution and risk geometry."
        )
    else:
        current_state = primary_reason or fallback

    top_rejected = zero_trade.get("top_rejected_reasons")
    if isinstance(top_rejected, list):
        for item in top_rejected:
            if not isinstance(item, Mapping):
                continue
            reason = item.get("reason")
            if isinstance(reason, str) and reason.strip():
                return current_state, reason.strip()

    return current_state, primary_reason or fallback


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(int(value), 0)


def _first_string(
    value: Mapping[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, Enum):
            return str(candidate.value)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _first_bool(
    value: Mapping[str, Any],
    keys: tuple[str, ...],
) -> bool | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, bool):
            return candidate
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, tuple | list):
        return []
    return [str(item) for item in value if str(item).strip()]


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
    payload["opportunity_portfolio"] = {
        "symbol": portfolio.symbol,
        "cmp": portfolio.cmp,
        "analysis_timestamp": portfolio.analysis_timestamp.isoformat(),
        "analysis_mode": portfolio.analysis_mode.value,
        "decision": portfolio.public_decision.value,
        "opportunity_count": len(portfolio.opportunities),
        "current_opportunities": [
            _serialize_opportunity(opportunity) for opportunity in portfolio.current_opportunities
        ],
        "nearby_opportunities": [
            _serialize_opportunity(opportunity) for opportunity in portfolio.nearby_opportunities
        ],
        "follow_up_opportunities": [
            _serialize_opportunity(opportunity) for opportunity in portfolio.follow_up_opportunities
        ],
        "runner_opportunities": (
            [] if portfolio.runner_plan is None else [_serialize_opportunity(portfolio.runner_plan)]
        ),
        "best_opportunities_by_lane": {
            lane: [
                _serialize_opportunity(opportunity)
                for opportunity in portfolio.best_opportunities_by_lane
                if opportunity.effective_lane.value == lane
            ]
            for lane in dict.fromkeys(
                opportunity.effective_lane.value
                for opportunity in portfolio.best_opportunities_by_lane
            )
        },
        "opportunities": [
            _serialize_opportunity(opportunity) for opportunity in portfolio.opportunities
        ],
    }

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
    payload["result_group"] = (
        "actionable"
        if primary is not None and primary.setup.execution_allowed_now
        else "developing"
    )


def _serialize_opportunity(opportunity: Any) -> dict[str, Any]:
    setup = _normalize(opportunity.setup)
    if not isinstance(setup, dict):
        raise TypeError("serialized opportunity setup must be an object")
    return {
        **setup,
        "opportunity_id": opportunity.opportunity_id,
        "category": opportunity.sequence_role.value,
        "sequence_role": opportunity.sequence_role.value,
        "lane": opportunity.effective_lane.value,
        "direction": opportunity.direction.value,
        "strategy": setup.get("strategy"),
        "entry_status": setup.get("entry_status"),
        "execution_allowed_now": setup.get("execution_allowed_now"),
        "setup": setup,
    }


def _analysis_opportunities(analysis: SymbolAnalysis) -> list[dict[str, Any]]:
    portfolio = analysis.opportunity_portfolio
    if portfolio is None:
        return []
    return [_serialize_opportunity(item) for item in portfolio.opportunities]


def _payload_opportunities(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    portfolio = payload.get("opportunity_portfolio")
    if not isinstance(portfolio, Mapping):
        return []
    opportunities = portfolio.get("opportunities")
    if not isinstance(opportunities, list):
        return []
    return [item for item in opportunities if isinstance(item, Mapping)]


def _count_opportunity_category(
    opportunities: list[Mapping[str, Any]],
    category: str,
) -> int:
    return sum(item.get("category") == category for item in opportunities)


def _normalize(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
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
    return portfolio is not None and portfolio.has_direction(TradeDirection(direction))


def _payload_direction(payload: Mapping[str, Any]) -> str | None:
    setup = payload.get("setup") or payload.get("developing_setup")
    return str(setup.get("direction")) if isinstance(setup, Mapping) else None


__all__ = ["serialize_scan_result", "serialize_symbol_analysis"]
