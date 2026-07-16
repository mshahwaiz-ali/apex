"""Deterministic strategy-routing metadata for scanner and analysis output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.config import DEFAULT_STRATEGY_ROUTING
from apex.domain import GainerState, GainerStateResult, MarketCategory
from apex.risk import RiskAssessment
from apex.strategies import Phase4AnalysisResult, StrategyType, TradeCandidate

_GAINER_CONTINUATION_STATES = frozenset(
    {
        GainerState.FRESH_BREAKOUT,
        GainerState.ACCELERATION,
        GainerState.CONTROLLED_CONTINUATION,
    }
)


def apply_strategy_routing(
    phase4: Phase4AnalysisResult,
    *,
    scanner_type: MarketCategory,
    gainer_result: GainerStateResult | None,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> Phase4AnalysisResult:
    """Filter Phase 4 candidates by configured scanner and gainer-state routing."""

    routes = _normalize_routing_config(routing_config)
    route_key = _route_key(scanner_type)
    configured = routes[route_key]
    gainer_state_rejections = _gainer_state_rejections(scanner_type, gainer_result)
    eligible = tuple(
        strategy
        for strategy in phase4.eligible_strategies or ()
        if strategy in configured and strategy not in gainer_state_rejections
    )
    skipped = dict(phase4.skipped_strategies or {})
    for strategy in phase4.evaluated_strategies:
        if strategy not in configured:
            skipped.setdefault(
                strategy,
                f"{strategy.value} is disabled by configured {route_key} scanner route",
            )
        if strategy in gainer_state_rejections:
            skipped[strategy] = gainer_state_rejections[strategy]
    candidates = tuple(
        candidate for candidate in phase4.candidates if candidate.strategy in eligible
    )
    return Phase4AnalysisResult(
        symbol=phase4.symbol,
        decision_time=phase4.decision_time,
        candidates=candidates,
        evaluated_strategies=phase4.evaluated_strategies,
        eligible_strategies=eligible,
        skipped_strategies=skipped,
        strategy_diagnostics=phase4.strategy_diagnostics,
        decision_regime=phase4.decision_regime,
        higher_timeframe_breakout=phase4.higher_timeframe_breakout,
    )


def build_strategy_routing_payload(
    *,
    scanner_type: MarketCategory,
    assessment: RiskAssessment,
    gainer_result: GainerStateResult | None,
    phase4: Phase4AnalysisResult | None = None,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Return reproducible routing metadata without rerunning strategy logic."""

    routes = _normalize_routing_config(routing_config)
    route_key = _route_key(scanner_type)
    enabled = routes[route_key]
    disabled = tuple(strategy for strategy in StrategyType if strategy not in enabled)
    setup = assessment.setup
    reasons = [f"{scanner_type.value} scanner path used configured {route_key} route"]
    if gainer_result is not None:
        reasons.append(f"gainer state {gainer_result.state.value} included in routing context")
    selected_strategy = setup.strategy if setup is not None else None
    selected_strategy_enabled = (
        selected_strategy in enabled if selected_strategy is not None else False
    )
    routed_eligible = tuple(phase4.eligible_strategies or ()) if phase4 is not None else ()
    selected_strategy_routed_eligible = (
        selected_strategy in routed_eligible if selected_strategy is not None else False
    )
    if phase4 is not None:
        reasons.append(f"decision regime {phase4.decision_regime.value} applied to routing")
        if phase4.higher_timeframe_breakout:
            reasons.append("higher-timeframe breakout continuation routing was active")
    diagnostics = (
        {
            strategy.value: {
                "candidate_count": diagnostic.candidate_count,
                "rejection_codes": [code.value for code in diagnostic.rejection_codes],
                "reasons": list(diagnostic.reasons),
                "near_miss_state": diagnostic.near_miss_state.value,
                "higher_timeframe_breakout": diagnostic.higher_timeframe_breakout,
            }
            for strategy, diagnostic in phase4.strategy_diagnostics.items()
        }
        if phase4 is not None and phase4.strategy_diagnostics is not None
        else {}
    )
    near_miss_counts: dict[str, int] = {}
    for diagnostic in diagnostics.values():
        state = str(diagnostic["near_miss_state"])
        near_miss_counts[state] = near_miss_counts.get(state, 0) + 1
    return {
        "scanner_type": scanner_type.value,
        "route_key": route_key,
        "enabled_strategies": [
            strategy.value for strategy in sorted(enabled, key=lambda item: item.value)
        ],
        "disabled_strategies": [strategy.value for strategy in disabled],
        "selected_strategy": selected_strategy.value if selected_strategy is not None else None,
        "selected_strategy_enabled": selected_strategy_enabled,
        "selected_strategy_routed_eligible": selected_strategy_routed_eligible,
        "decision_regime": phase4.decision_regime.value if phase4 is not None else None,
        "higher_timeframe_breakout": (
            phase4.higher_timeframe_breakout if phase4 is not None else False
        ),
        "routed_eligible_strategies": [strategy.value for strategy in routed_eligible],
        "skipped_strategies": (
            {strategy.value: reason for strategy, reason in phase4.skipped_strategies.items()}
            if phase4 is not None and phase4.skipped_strategies is not None
            else {}
        ),
        "phase4_strategy_diagnostics": diagnostics,
        "candidate_diagnostics": _candidate_diagnostics(phase4),
        "near_miss_state_counts": near_miss_counts,
        "eligible": setup is not None,
        "reasons": reasons,
        "rejections": list(assessment.reasons),
    }


def _candidate_diagnostics(phase4: Phase4AnalysisResult | None) -> list[dict[str, object]]:
    """Describe generated candidates and explicit no-generation outcomes."""

    if phase4 is None:
        return []
    diagnostics = phase4.strategy_diagnostics or {}
    records: list[dict[str, object]] = []
    for strategy in phase4.evaluated_strategies:
        strategy_candidates = tuple(
            candidate for candidate in phase4.candidates if candidate.strategy is strategy
        )
        diagnostic = diagnostics.get(strategy)
        if strategy_candidates:
            records.extend(_generated_candidate_payload(candidate) for candidate in strategy_candidates)
            continue
        records.append(
            {
                "strategy": strategy.value,
                "direction": None,
                "generated": False,
                "candidate_score": None,
                "entry_zone_low": None,
                "entry_zone_high": None,
                "ideal_entry": None,
                "maximum_chase_price": None,
                "current_price": None,
                "entry_quality": None,
                "chase_classification": None,
                "accepted": False,
                "rejected": True,
                "rejection_codes": (
                    [code.value for code in diagnostic.rejection_codes]
                    if diagnostic is not None
                    else []
                ),
                "rejection_reasons": list(diagnostic.reasons) if diagnostic is not None else [],
                "nearest_future_trigger": None,
                "near_miss_state": (
                    diagnostic.near_miss_state.value if diagnostic is not None else None
                ),
                "invalidation": None,
            }
        )
    return records


def _generated_candidate_payload(candidate: TradeCandidate) -> dict[str, object]:
    metadata = candidate.metadata
    return {
        "strategy": candidate.strategy.value,
        "direction": candidate.direction.value,
        "generated": True,
        "candidate_score": None,
        "entry_zone_low": candidate.entry.lower,
        "entry_zone_high": candidate.entry.upper,
        "ideal_entry": candidate.entry.preferred,
        "maximum_chase_price": candidate.entry.max_chase_price,
        "current_price": candidate.entry.current_price,
        "entry_quality": candidate.quality.entry_quality * 100.0,
        "chase_classification": (
            "EXTENDED" if candidate.entry.is_extended else "WITHIN_LIMITS"
        ),
        "accepted": None,
        "rejected": None,
        "rejection_codes": [],
        "rejection_reasons": [],
        "nearest_future_trigger": _metadata_number(
            metadata,
            "reclaim_trigger",
            "retest_trigger",
            "trigger_price",
        ),
        "near_miss_state": None,
        "invalidation": candidate.invalidation.price,
    }


def _metadata_number(metadata: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        return float(value)
    return None


def _route_key(scanner_type: MarketCategory) -> str:
    return "gainer" if scanner_type is MarketCategory.GAINER else "normal_market"


def _normalize_routing_config(
    routing_config: Mapping[str, Sequence[str]] | None,
) -> dict[str, frozenset[StrategyType]]:
    source = routing_config or DEFAULT_STRATEGY_ROUTING
    routes: dict[str, frozenset[StrategyType]] = {}
    for key in ("normal_market", "gainer"):
        values = source.get(key)
        if values is None:
            raise ValueError(f"strategy routing missing route: {key}")
        strategies = frozenset(StrategyType(value) for value in values)
        if not strategies:
            raise ValueError(f"strategy routing route cannot be empty: {key}")
        routes[key] = strategies
    return routes


def _gainer_state_rejections(
    scanner_type: MarketCategory,
    gainer_result: GainerStateResult | None,
) -> dict[StrategyType, str]:
    if scanner_type is not MarketCategory.GAINER or gainer_result is None:
        return {}
    if gainer_result.state in _GAINER_CONTINUATION_STATES:
        return {}
    return {
        StrategyType.MOMENTUM_GAINER_CONTINUATION: (
            "momentum_gainer_continuation requires fresh, accelerating, "
            "or controlled gainer state; "
            f"received {gainer_result.state.value}"
        )
    }
