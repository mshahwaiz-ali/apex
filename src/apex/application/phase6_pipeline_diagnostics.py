"""Stable Phase 6 risk-decision diagnostics for futures scan runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import SymbolAnalysis
from apex.risk import RiskDecision


@dataclass(frozen=True, slots=True)
class Phase6DiagnosticSummary:
    """Deterministic run-level Phase 6 approval and rejection statistics."""

    analyses_observed: int
    approved: int
    rejected: int
    rejection_code_counts: Mapping[str, int]
    rejection_counts_by_strategy: Mapping[str, Mapping[str, int]]
    approved_counts_by_strategy: Mapping[str, int]
    approved_counts_by_direction: Mapping[str, int]
    stop_quality_band_counts: Mapping[str, int]
    leverage_band_counts: Mapping[str, int]
    target_count_distribution: Mapping[str, int]
    total_required_leverage: float
    leverage_observations: int
    total_account_risk_pct: float
    account_risk_observations: int
    total_stop_distance_pct: float
    stop_distance_observations: int

    def to_payload(self) -> dict[str, Any]:
        """Serialize Phase 6 analytics with deterministic key ordering."""

        return {
            "decision_funnel": {
                "observed": self.analyses_observed,
                "approved": self.approved,
                "rejected": self.rejected,
            },
            "rejection_code_counts": _sorted_counts(self.rejection_code_counts),
            "rejection_counts_by_strategy": _sorted_nested_counts(
                self.rejection_counts_by_strategy
            ),
            "approved_counts_by_strategy": _sorted_counts(
                self.approved_counts_by_strategy
            ),
            "approved_counts_by_direction": _sorted_counts(
                self.approved_counts_by_direction
            ),
            "stop_quality_band_counts": _sorted_counts(self.stop_quality_band_counts),
            "leverage_band_counts": _ordered_leverage_bands(self.leverage_band_counts),
            "target_count_distribution": _sorted_counts(
                self.target_count_distribution
            ),
            "averages": {
                "required_leverage": _average(
                    self.total_required_leverage,
                    self.leverage_observations,
                ),
                "account_risk_pct": _average(
                    self.total_account_risk_pct,
                    self.account_risk_observations,
                ),
                "stop_distance_pct": _average(
                    self.total_stop_distance_pct,
                    self.stop_distance_observations,
                ),
            },
        }


def build_phase6_diagnostic_summary(
    analyses: Sequence[SymbolAnalysis],
) -> Phase6DiagnosticSummary:
    """Aggregate structured Phase 6 decisions without parsing human-readable reasons."""

    rejection_codes: Counter[str] = Counter()
    rejection_by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    approved_by_strategy: Counter[str] = Counter()
    approved_by_direction: Counter[str] = Counter()
    stop_quality_bands: Counter[str] = Counter()
    leverage_bands: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()

    approved = rejected = 0
    total_required_leverage = 0.0
    leverage_observations = 0
    total_account_risk_pct = 0.0
    account_risk_observations = 0
    total_stop_distance_pct = 0.0
    stop_distance_observations = 0

    for analysis in analyses:
        assessment = analysis.assessment
        selected_strategy = _selected_strategy(analysis)

        if assessment.decision is RiskDecision.APPROVED:
            approved += 1
            setup = assessment.setup
            if setup is None:
                continue
            strategy = setup.strategy.value
            direction = setup.direction.value
            approved_by_strategy[strategy] += 1
            approved_by_direction[direction] += 1
            stop_quality_bands[setup.stop_loss.quality_band.value] += 1
            leverage_bands[_leverage_band(setup.position_size.required_leverage)] += 1
            target_counts[str(len(setup.take_profits))] += 1
            total_required_leverage += setup.position_size.required_leverage
            leverage_observations += 1
            total_account_risk_pct += setup.position_size.account_risk_pct
            account_risk_observations += 1
            total_stop_distance_pct += setup.stop_loss.distance_pct
            stop_distance_observations += 1
            continue

        rejected += 1
        for code in assessment.rejection_codes:
            value = code.value
            rejection_codes[value] += 1
            if selected_strategy is not None:
                rejection_by_strategy[selected_strategy][value] += 1

    return Phase6DiagnosticSummary(
        analyses_observed=len(analyses),
        approved=approved,
        rejected=rejected,
        rejection_code_counts=rejection_codes,
        rejection_counts_by_strategy=rejection_by_strategy,
        approved_counts_by_strategy=approved_by_strategy,
        approved_counts_by_direction=approved_by_direction,
        stop_quality_band_counts=stop_quality_bands,
        leverage_band_counts=leverage_bands,
        target_count_distribution=target_counts,
        total_required_leverage=total_required_leverage,
        leverage_observations=leverage_observations,
        total_account_risk_pct=total_account_risk_pct,
        account_risk_observations=account_risk_observations,
        total_stop_distance_pct=total_stop_distance_pct,
        stop_distance_observations=stop_distance_observations,
    )


def phase6_analysis_payload(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Return one stable Phase 6 audit payload for a symbol."""

    assessment = analysis.assessment
    setup = assessment.setup
    payload: dict[str, Any] = {
        "symbol": analysis.symbol,
        "decision": assessment.decision.value,
        "configuration_id": assessment.configuration_id,
        "rejection_codes": [code.value for code in assessment.rejection_codes],
        "reasons": list(assessment.reasons),
        "selected_strategy": _selected_strategy(analysis),
        "risk_rejection_diagnostics": [
            dict(sorted(item.items()))
            for item in getattr(analysis, "risk_rejection_diagnostics", ())
        ],
    }
    if setup is None:
        payload["approved_setup"] = None
        return payload

    payload["approved_setup"] = {
        "candidate_id": setup.candidate_id,
        "strategy": setup.strategy.value,
        "direction": setup.direction.value,
        "confidence_score": setup.confidence_score,
        "entry": {
            "lower": setup.entry.lower,
            "upper": setup.entry.upper,
            "preferred": setup.entry.preferred,
            "current_price": setup.entry.current_price,
            "maximum_chase_price": setup.entry.maximum_chase_price,
            "current_price_inside_zone": setup.entry.current_price_inside_zone,
        },
        "stop_loss": {
            "price": setup.stop_loss.price,
            "distance": setup.stop_loss.distance,
            "distance_pct": setup.stop_loss.distance_pct,
            "quality_score": setup.stop_loss.quality_score,
            "quality_band": setup.stop_loss.quality_band.value,
        },
        "position_size": {
            "risk_amount": setup.position_size.risk_amount,
            "quantity": setup.position_size.quantity,
            "notional_value": setup.position_size.notional_value,
            "account_risk_pct": setup.position_size.account_risk_pct,
            "required_leverage": setup.position_size.required_leverage,
        },
        "leverage": {
            "minimum": setup.leverage.minimum,
            "maximum": setup.leverage.maximum,
            "modeled_maximum": setup.leverage.modeled_maximum,
            "liquidation_price_at_maximum": setup.leverage.liquidation_price_at_maximum,
            "stop_to_liquidation_buffer_pct": setup.leverage.stop_to_liquidation_buffer_pct,
        },
        "take_profit_count": len(setup.take_profits),
        "management_policy_count": len(setup.management_policies),
        "warning_count": len(setup.warnings),
    }
    return payload


def _selected_strategy(analysis: SymbolAnalysis) -> str | None:
    diagnostics = getattr(analysis, "phase5_diagnostics", None)
    if not isinstance(diagnostics, Mapping):
        return None
    selected_id = diagnostics.get("selected_candidate_id")
    candidates = diagnostics.get("candidates")
    if not isinstance(selected_id, str) or not isinstance(candidates, Sequence):
        return None
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("candidate_id") == selected_id:
            strategy = candidate.get("strategy")
            return strategy if isinstance(strategy, str) and strategy else None
    return None


def _leverage_band(leverage: float) -> str:
    if leverage <= 5.0:
        return "1_5x"
    if leverage <= 10.0:
        return "5_10x"
    if leverage <= 20.0:
        return "10_20x"
    return "above_20x"


def _average(total: float, count: int) -> float | None:
    return round(total / count, 6) if count > 0 else None


def _sorted_counts(values: Mapping[str, int]) -> dict[str, int]:
    return {key: values[key] for key in sorted(values)}


def _sorted_nested_counts(
    values: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    return {
        outer: {inner: values[outer][inner] for inner in sorted(values[outer])}
        for outer in sorted(values)
    }


def _ordered_leverage_bands(values: Mapping[str, int]) -> dict[str, int]:
    order = ("1_5x", "5_10x", "10_20x", "above_20x")
    return {band: values.get(band, 0) for band in order}
