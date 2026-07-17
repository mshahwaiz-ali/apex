"""Application-level analysis and scanner orchestration."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from apex.application.analysis_records import build_analysis_record
from apex.application.candidate_ranking import (
    CandidateRankingSnapshot,
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.application.futures_quality import analyze_futures_phase5
from apex.application.market_strategy_router import MarketStrategyRoute
from apex.application.precision_entry import build_precision_entry_plan
from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.config import DEFAULT_TIMEFRAME_ROLES
from apex.config.settings import DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
from apex.data.providers.base import MarketDataProvider
from apex.domain import (
    EntryClassificationInput,
    FuturesDirection,
    classify_entry_state,
)
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    LiquidationClusterSide,
    LiquidationClusterSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)
from apex.features.registry import create_default_feature_registry
from apex.market_analysis import analyze_structure_and_liquidity
from apex.risk import (
    DEFAULT_RISK_CONFIG,
    ExposureState,
    RiskAssessment,
    RiskConfig,
    RiskDecision,
    analyze_risk,
    load_risk_config,
)
from apex.risk.contracts import RiskApprovedSetup
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    analyze_phase4,
    strategy_evidence_payload,
    strategy_evidence_summary,
    timeframe_role_sort_key,
)


@dataclass(frozen=True, slots=True)
class SymbolAnalysis:
    """Full deterministic analysis output for one symbol."""

    symbol: str
    generated_at: datetime
    assessment: RiskAssessment
    candidate_count: int
    evaluated_timeframes: tuple[str, ...]
    regime_by_timeframe: Mapping[str, str]
    data_quality_by_timeframe: Mapping[str, Mapping[str, Any]]
    strategy_routing: Mapping[str, Any] | None = None
    precision_entry: Mapping[str, Any] | None = None
    phase5_diagnostics: Mapping[str, Any] | None = None
    candidate_ranking: CandidateRankingSnapshot | None = None
    risk_rejection_diagnostics: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Scanner output with isolated failures."""

    generated_at: datetime
    analyses: tuple[SymbolAnalysis, ...]
    failures: Mapping[str, str]

    @property
    def approved(self) -> tuple[SymbolAnalysis, ...]:
        return tuple(
            item for item in self.analyses if item.assessment.decision is RiskDecision.APPROVED
        )


def load_symbols(path: str | Path) -> tuple[str, ...]:
    """Load the configured scanner symbol universe."""

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("symbols"), list):
        raise ValueError("symbol configuration must contain a symbols list")
    symbols = tuple(str(symbol).strip() for symbol in raw["symbols"] if str(symbol).strip())
    if not symbols:
        raise ValueError("symbol configuration must contain at least one symbol")
    if len(set(symbols)) != len(symbols):
        raise ValueError("symbol configuration cannot contain duplicate symbols")
    return symbols


def analyze_symbol(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    risk_config: RiskConfig = DEFAULT_RISK_CONFIG,
    exposure: ExposureState | None = None,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    market_strategy_route: MarketStrategyRoute | None = None,
) -> SymbolAnalysis:
    """Run the deterministic Phase 4 to risk analysis stack for one symbol."""

    if candle_limit < 40:
        raise ValueError("analysis requires at least 40 candles per timeframe")
    decision_time = generated_at or datetime.now(UTC)
    context, regimes = build_strategy_context(
        symbol,
        provider,
        timeframes=timeframes,
        timeframe_roles=timeframe_roles,
        timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
        candle_limit=candle_limit,
        received_at=decision_time,
    )
    phase4 = analyze_phase4(context, decision_time=decision_time)
    routed_phase4 = apply_strategy_routing(
        phase4,
        routing_config=strategy_routing,
    )
    phase5 = analyze_futures_phase5(
        routed_phase4,
        environment_route=market_strategy_route,
    )
    assessment = analyze_risk(
        phase5,
        config=risk_config,
        exposure=exposure,
    )
    precision_entry = (
        build_precision_entry_plan(assessment.setup, timeframe_contexts=context.frames).model_dump(
            mode="json"
        )
        if assessment.setup is not None
        else None
    )
    candidate_ranking = build_candidate_ranking_snapshot(phase5)
    risk_rejection_diagnostics = _build_risk_rejection_diagnostics(
        phase5=phase5,
        assessment=assessment,
        context=context,
        config=risk_config,
    )
    return SymbolAnalysis(
        symbol=symbol,
        generated_at=decision_time,
        assessment=assessment,
        candidate_count=len(routed_phase4.candidates),
        evaluated_timeframes=tuple(frame.timeframe for frame in context.frames),
        regime_by_timeframe=regimes,
        data_quality_by_timeframe={
            frame.timeframe: _frame_data_quality_payload(frame) for frame in context.frames
        },
        strategy_routing=_strategy_routing_payload(
            assessment, routed_phase4, strategy_routing
        ),
        precision_entry=precision_entry,
        candidate_ranking=candidate_ranking,
        phase5_diagnostics={
            "candidate_count": len(phase5.all_scored_candidates),
            "ranked_count": len(phase5.ranked_candidates),
            "rejected_count": len(phase5.rejected_candidates),
            "selected": phase5.selected_candidate is not None,
            "selected_candidate_id": (
                phase5.selected_candidate.scored.candidate_id
                if phase5.selected_candidate is not None
                else None
            ),
            "no_trade_reason": phase5.no_trade_reason,
            "candidates": [
                {
                    "candidate_id": item.scored.candidate_id,
                    "strategy": item.candidate.strategy.value,
                    "direction": item.candidate.direction.value,
                    "outcome": item.outcome.value,
                    "final_score": item.final_score,
                    "evidence": strategy_evidence_payload(item.candidate.evidence),
                    "evidence_summary": strategy_evidence_summary(
                        item.candidate.evidence
                    ),
                    "metadata": dict(item.candidate.metadata),
                    "environment_route_alignment": (
                        {
                            "state": item.scored.environment_route_alignment.state.value,
                            "route_priority": item.scored.environment_route_alignment.route_priority,
                            "preferred_direction": (
                                item.scored.environment_route_alignment.preferred_direction
                            ),
                            "routing_score": item.scored.environment_route_alignment.routing_score,
                            "score_adjustment": (
                                item.scored.environment_route_alignment.score_adjustment
                            ),
                            "reason_codes": list(
                                item.scored.environment_route_alignment.reason_codes
                            ),
                            "reasons": list(item.scored.environment_route_alignment.reasons),
                        }
                        if item.scored.environment_route_alignment is not None
                        else None
                    ),
                    "reasons": list(item.reasons),
                }
                for item in phase5.ranked_candidates
            ],
        },
        risk_rejection_diagnostics=risk_rejection_diagnostics,
    )


def _build_risk_rejection_diagnostics(
    *,
    phase5: Any,
    assessment: RiskAssessment,
    context: StrategyContext,
    config: RiskConfig,
) -> tuple[Mapping[str, object], ...]:
    """Describe a candidate selection rejected by risk analysis."""

    selected = phase5.selected_candidate
    if selected is None or assessment.decision is RiskDecision.APPROVED:
        return ()

    candidate = selected.candidate
    entry_price = candidate.entry.preferred

    structural_buffer = entry_price * config.structural_stop_buffer_pct / 100.0

    stop_price = (
        candidate.invalidation.price - structural_buffer
        if candidate.direction.value == "long"
        else candidate.invalidation.price + structural_buffer
    )

    absolute_stop_distance = abs(entry_price - stop_price)
    stop_distance_percentage = absolute_stop_distance / entry_price * 100.0

    configured_risk_amount = config.account_equity * config.risk_per_trade_pct / 100.0
    structural_loss_fraction = absolute_stop_distance / entry_price
    execution_cost_fraction = (
        config.entry_fee_pct
        + config.exit_fee_pct
        + config.entry_slippage_pct
        + config.exit_slippage_pct
    ) / 100.0
    modeled_total_loss_fraction = structural_loss_fraction + execution_cost_fraction
    modeled_position_notional = (
        configured_risk_amount / modeled_total_loss_fraction
        if modeled_total_loss_fraction > 0.0
        else 0.0
    )
    modeled_required_leverage = max(
        1.0,
        modeled_position_notional / config.account_equity,
    )

    atr_value = candidate.metadata.get("decision_atr")
    candidate_atr = (
        float(atr_value) if isinstance(atr_value, int | float) and atr_value > 0.0 else None
    )

    if candidate_atr is not None:
        required_minimum_stop_distance = candidate_atr * config.minimum_stop_atr_multiple
        noise_floor_model = "decision_atr_multiple"
        atr_used_by_noise_floor = True
    else:
        required_minimum_stop_distance = entry_price * config.minimum_stop_distance_pct / 100.0
        noise_floor_model = "static_entry_percentage_fallback"
        atr_used_by_noise_floor = False

    atr = candidate_atr if candidate_atr is not None else context.atr
    atr_percentage = atr / entry_price * 100.0

    return (
        {
            "decision_time": candidate.decision_time.isoformat(),
            "candidate_id": selected.scored.candidate_id,
            "strategy": candidate.strategy.value,
            "direction": candidate.direction.value,
            "score": selected.final_score,
            "decision_timeframe": str(
                candidate.metadata.get(
                    "decision_timeframe",
                    context.decision_frame.timeframe,
                )
            ),
            "entry_price": entry_price,
            "candidate_invalidation_price": candidate.invalidation.price,
            "structural_stop_buffer_percentage": config.structural_stop_buffer_pct,
            "structural_stop_buffer_distance": structural_buffer,
            "stop_price": stop_price,
            "absolute_stop_distance": absolute_stop_distance,
            "stop_distance_percentage": stop_distance_percentage,
            "configured_minimum_noise_floor_percentage": config.minimum_stop_distance_pct,
            "configured_minimum_stop_atr_multiple": config.minimum_stop_atr_multiple,
            "required_minimum_stop_distance": required_minimum_stop_distance,
            "required_minimum_stop_percentage": (
                required_minimum_stop_distance / entry_price * 100.0
            ),
            "stop_shortfall_distance": max(
                0.0,
                required_minimum_stop_distance - absolute_stop_distance,
            ),
            "stop_shortfall_percentage_points": max(
                0.0,
                required_minimum_stop_distance / entry_price * 100.0 - stop_distance_percentage,
            ),
            "atr": atr,
            "atr_percentage": atr_percentage,
            "stop_distance_in_atr": absolute_stop_distance / atr if atr > 0.0 else None,
            "invalidation_distance_in_atr": (
                abs(entry_price - candidate.invalidation.price) / atr if atr > 0.0 else None
            ),
            "noise_floor_model": noise_floor_model,
            "atr_used_by_noise_floor": atr_used_by_noise_floor,
            "configured_risk_amount": configured_risk_amount,
            "configured_entry_fee_percentage": config.entry_fee_pct,
            "configured_exit_fee_percentage": config.exit_fee_pct,
            "configured_entry_slippage_percentage": config.entry_slippage_pct,
            "configured_exit_slippage_percentage": config.exit_slippage_pct,
            "structural_loss_fraction": structural_loss_fraction,
            "execution_cost_fraction": execution_cost_fraction,
            "modeled_total_loss_fraction": modeled_total_loss_fraction,
            "modeled_position_notional": modeled_position_notional,
            "modeled_quantity": modeled_position_notional / entry_price,
            "modeled_structural_loss_amount": (
                modeled_position_notional * structural_loss_fraction
            ),
            "modeled_execution_cost_amount": (modeled_position_notional * execution_cost_fraction),
            "modeled_total_loss_amount": (modeled_position_notional * modeled_total_loss_fraction),
            "modeled_required_leverage": modeled_required_leverage,
            "rejection_codes": [code.value for code in assessment.rejection_codes],
            "rejection_reasons": list(assessment.reasons),
        },
    )


def build_strategy_context(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    candle_limit: int,
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    received_at: datetime | None = None,
) -> tuple[StrategyContext, Mapping[str, str]]:
    """Fetch candles and build a strategy context in deterministic role order."""

    role_config = timeframe_roles or DEFAULT_TIMEFRAME_ROLES
    staleness_config = timeframe_max_staleness_seconds or DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
    timestamp = received_at or datetime.now(UTC)
    ticker_snapshot = _fetch_ticker_snapshot(provider, symbol)
    ticker_price = ticker_snapshot.last_price if ticker_snapshot is not None else None
    spread_percentage = ticker_snapshot.spread_percentage if ticker_snapshot is not None else None
    order_book_snapshot = _fetch_order_book_snapshot(provider, symbol)
    exchange_filter_snapshot = _fetch_exchange_filter_snapshot(provider, symbol)
    liquidation_cluster_snapshot = _fetch_liquidation_cluster_snapshot(provider, symbol)
    frames: list[TimeframeContext] = []
    regimes: dict[str, str] = {}
    for timeframe in timeframes:
        role_name = role_config.get(timeframe)
        role = TimeframeRole(role_name) if role_name is not None else None
        if role is None:
            continue
        candles = tuple(provider.fetch_candles(symbol, timeframe, limit=candle_limit))
        frame, regime = _frame_from_candles(
            symbol,
            timeframe,
            role,
            candles,
            received_at=timestamp,
            max_staleness_seconds=staleness_config.get(timeframe),
            ticker_price=ticker_price,
            spread_percentage=spread_percentage,
            order_book_snapshot=order_book_snapshot,
            exchange_filter_snapshot=exchange_filter_snapshot,
            liquidation_cluster_snapshot=liquidation_cluster_snapshot,
        )
        frames.append(frame)
        regimes[timeframe] = regime

    if not frames:
        raise ValueError("no supported analysis timeframes were provided")
    return (
        StrategyContext(
            symbol=symbol,
            frames=tuple(sorted(frames, key=lambda frame: timeframe_role_sort_key(frame.role))),
        ),
        regimes,
    )


def scan_symbols(
    symbols: Iterable[str],
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    risk_config: RiskConfig = DEFAULT_RISK_CONFIG,
    generated_at: datetime | None = None,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
) -> ScanResult:
    """Analyze each symbol exactly once using the default market route."""

    timestamp = generated_at or datetime.now(UTC)
    analyses: list[SymbolAnalysis] = []
    failures: dict[str, str] = {}

    for symbol in symbols:
        try:
            analyses.append(
                analyze_symbol(
                    symbol,
                    provider,
                    timeframes=timeframes,
                    timeframe_roles=timeframe_roles,
                    timeframe_max_staleness_seconds=timeframe_max_staleness_seconds,
                    candle_limit=candle_limit,
                    risk_config=risk_config,
                    generated_at=timestamp,
                    strategy_routing=strategy_routing,
                )
            )
        except Exception as exc:  # Scanner must isolate per-symbol failures.
            failures[symbol] = str(exc)

    ranked = tuple(sorted(analyses, key=_scan_sort_key))
    return ScanResult(
        generated_at=timestamp,
        analyses=ranked,
        failures=failures,
    )


def load_default_risk_config(path: str | Path = "config/risk.yaml") -> RiskConfig:
    """Load risk configuration, falling back to defaults when the file is absent."""

    config_path = Path(path)
    if not config_path.exists():
        return DEFAULT_RISK_CONFIG
    return load_risk_config(config_path)


def serialize_symbol_analysis(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Return stable machine-readable CLI output for one analysis."""

    assessment = analysis.assessment
    if assessment.decision is RiskDecision.APPROVED:
        if assessment.setup is None:
            raise ValueError("approved analysis is missing setup")
        payload = _approved_payload(assessment.setup, analysis.precision_entry)
    else:
        payload = {
            "symbol": analysis.symbol,
            "decision": "NO_TRADE",
            "reasons": list(assessment.reasons),
            "rejection_codes": [code.value for code in assessment.rejection_codes],
        }
    payload.update(
        {
            "generated_at": analysis.generated_at.isoformat(),
            # Scanner-category fields are intentionally omitted from new
            # payloads. Historical readers retain their compatibility handling.
            "strategy_routing": dict(analysis.strategy_routing or {}),
            "phase5_diagnostics": dict(analysis.phase5_diagnostics or {}),
            "candidate_ranking": (
                candidate_ranking_payload(analysis.candidate_ranking)
                if analysis.candidate_ranking is not None
                else None
            ),
            "candidate_count": analysis.candidate_count,
            "evaluated_timeframes": list(analysis.evaluated_timeframes),
            "market_regime": dict(analysis.regime_by_timeframe),
            "timeframe_data_quality": {
                timeframe: dict(payload)
                for timeframe, payload in analysis.data_quality_by_timeframe.items()
            },
            "configuration_id": assessment.configuration_id,
        }
    )
    return payload


def serialize_scan_result(result: ScanResult) -> dict[str, Any]:
    """Return stable scanner JSON."""

    approved = tuple(
        analysis for analysis in result.analyses if analysis.assessment.setup is not None
    )
    long_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None
        and item.assessment.setup.direction.value == "long"
    )
    short_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None
        and item.assessment.setup.direction.value == "short"
    )
    return {
        "generated_at": result.generated_at.isoformat(),
        "best_overall": serialize_symbol_analysis(approved[0]) if approved else None,
        "top_long_setups": [serialize_symbol_analysis(item) for item in long_setups],
        "top_short_setups": [serialize_symbol_analysis(item) for item in short_setups],
        "results": [serialize_symbol_analysis(item) for item in result.analyses],
        "failures": dict(result.failures),
    }


def write_json_report(payload: Mapping[str, Any], path: Path) -> None:
    """Write a deterministic JSON report."""

    record = build_analysis_record(payload)
    report_payload = dict(payload)
    report_payload["record_metadata"] = {
        key: value for key, value in record.items() if key != "payload"
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_symbol_text(analysis: SymbolAnalysis) -> str:
    """Return concise human-readable analysis output."""

    payload = serialize_symbol_analysis(analysis)
    if payload["decision"] == "NO_TRADE":
        reasons = "; ".join(payload["reasons"]) or "no qualifying setup"
        return f"{analysis.symbol}: NO_TRADE | {reasons}"

    return (
        f"{analysis.symbol}: {payload['decision']} {payload['strategy']} "
        f"| state={payload['entry_state']} "
        f"| score={payload['confidence_score']:.1f} "
        f"| entry={payload['entry_zone']['low']:.4f}-{payload['entry_zone']['high']:.4f} "
        f"| stop={payload['stop_loss']:.4f} "
        f"| max_rr={payload['max_risk_reward']:.2f}"
    )


def format_scan_text(result: ScanResult) -> str:
    """Return concise human-readable scanner output."""

    lines = [f"Scan generated at {result.generated_at.isoformat()}"]
    for analysis in result.analyses:
        lines.append(format_symbol_text(analysis))
    for symbol, reason in result.failures.items():
        lines.append(f"{symbol}: FAILED | {reason}")
    return "\n".join(lines)


def _frame_from_candles(
    symbol: str,
    timeframe: str,
    role: TimeframeRole,
    candles: Sequence[Candle],
    *,
    received_at: datetime,
    max_staleness_seconds: int | None,
    ticker_price: float | None,
    spread_percentage: float | None,
    order_book_snapshot: OrderBookSnapshot | None,
    exchange_filter_snapshot: ExchangeFilterSnapshot | None,
    liquidation_cluster_snapshot: LiquidationClusterSnapshot | None,
) -> tuple[TimeframeContext, str]:
    if not candles:
        raise ValueError(f"{symbol} {timeframe} returned no candles")
    features_by_name = create_default_feature_registry().calculate_all(candles)
    relative_volume = features_by_name["relative_volume_20"][0].values
    relative_volume_for_phase3 = relative_volume if len(relative_volume) == len(candles) else None
    phase3 = analyze_structure_and_liquidity(candles, relative_volume=relative_volume_for_phase3)
    latest_closed = candles[-2] if not candles[-1].is_closed and len(candles) > 1 else candles[-1]
    active_candle_price = candles[-1].close if not candles[-1].is_closed else None
    live_price, live_price_source = _select_current_price(
        ticker_price=ticker_price,
        active_candle_price=active_candle_price,
        latest_closed_price=latest_closed.close,
    )
    staleness_seconds = max(0.0, (received_at - latest_closed.close_time).total_seconds())
    is_stale = max_staleness_seconds is not None and staleness_seconds > float(
        max_staleness_seconds
    )
    snapshot = FeatureSnapshot(
        atr=_required_latest(features_by_name["atr_14"][0], "ATR"),
        ema_fast=_latest(features_by_name["ema_20"][0]),
        ema_slow=_latest(features_by_name["ema_50"][0]),
        vwap=_latest(features_by_name["vwap"][0]),
        rsi=_latest(features_by_name["rsi_14"][0]),
        rsi_slope=_latest(features_by_name["rsi_slope_14_3"][0]),
        macd_histogram=_latest(features_by_name["macd"][2]),
        rate_of_change=_latest(features_by_name["roc_12"][0]),
        relative_volume=_latest(features_by_name["relative_volume_20"][0]),
        trend_strength=phase3.structure.trend.strength,
        range_position=_unit_or_none(_latest(features_by_name["recent_range_position_20"][0])),
        volatility_expansion=_unit_or_none(_latest(features_by_name["candle_range_ratio_20"][0])),
    )
    return (
        TimeframeContext(
            timeframe=timeframe,
            role=role,
            current_price=live_price,
            latest_closed_price=latest_closed.close,
            active_candle_price=active_candle_price,
            ticker_price=ticker_price,
            spread_percentage=spread_percentage,
            order_book_spread_percentage=(
                order_book_snapshot.spread_percentage if order_book_snapshot is not None else None
            ),
            order_book_depth_imbalance=(
                order_book_snapshot.depth_imbalance if order_book_snapshot is not None else None
            ),
            exchange_tick_size=(
                exchange_filter_snapshot.tick_size if exchange_filter_snapshot is not None else None
            ),
            exchange_step_size=(
                exchange_filter_snapshot.step_size if exchange_filter_snapshot is not None else None
            ),
            exchange_min_notional=(
                exchange_filter_snapshot.min_notional
                if exchange_filter_snapshot is not None
                else None
            ),
            nearest_long_cluster_distance_pct=_nearest_liquidation_distance_pct(
                liquidation_cluster_snapshot,
                side=LiquidationClusterSide.LONG,
                reference_price=live_price,
            ),
            nearest_short_cluster_distance_pct=_nearest_liquidation_distance_pct(
                liquidation_cluster_snapshot,
                side=LiquidationClusterSide.SHORT,
                reference_price=live_price,
            ),
            analysis_price=latest_closed.close,
            last_closed_at=latest_closed.close_time,
            last_received_at=received_at,
            staleness_seconds=staleness_seconds,
            is_stale=is_stale,
            data_confidence=0.5 if is_stale else 1.0,
            current_price_source=live_price_source,
            features=snapshot,
            structure=phase3.structure,
            liquidity=phase3.liquidity,
            active_candle=not candles[-1].is_closed,
        ),
        phase3.regime.value,
    )


def _latest(result: Any) -> float | None:
    value = result.latest
    return value if value is None or math.isfinite(value) else None


def _required_latest(result: Any, name: str) -> float:
    value = _latest(result)
    if value is None or value <= 0:
        raise ValueError(f"{name} is unavailable")
    return value


def _unit_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, value))


def _fetch_ticker_snapshot(provider: MarketDataProvider, symbol: str) -> TickerSnapshot | None:
    fetch_ticker = getattr(provider, "fetch_ticker", None)
    if not callable(fetch_ticker):
        return None
    try:
        snapshot = fetch_ticker(symbol)
    except Exception:
        return None
    if not isinstance(snapshot, TickerSnapshot):
        return None
    return snapshot


def _fetch_order_book_snapshot(
    provider: MarketDataProvider,
    symbol: str,
) -> OrderBookSnapshot | None:
    fetch_order_book = getattr(provider, "fetch_order_book", None)
    if not callable(fetch_order_book):
        return None
    try:
        snapshot = fetch_order_book(symbol)
    except Exception:
        return None
    if not isinstance(snapshot, OrderBookSnapshot):
        return None
    return snapshot


def _fetch_exchange_filter_snapshot(
    provider: MarketDataProvider,
    symbol: str,
) -> ExchangeFilterSnapshot | None:
    fetch_exchange_filters = getattr(provider, "fetch_exchange_filters", None)
    if not callable(fetch_exchange_filters):
        return None
    try:
        snapshot = fetch_exchange_filters(symbol)
    except Exception:
        return None
    if not isinstance(snapshot, ExchangeFilterSnapshot):
        return None
    return snapshot


def _fetch_liquidation_cluster_snapshot(
    provider: MarketDataProvider,
    symbol: str,
) -> LiquidationClusterSnapshot | None:
    fetch_liquidation_clusters = getattr(provider, "fetch_liquidation_clusters", None)
    if not callable(fetch_liquidation_clusters):
        return None
    try:
        snapshot = fetch_liquidation_clusters(symbol)
    except Exception:
        return None
    if not isinstance(snapshot, LiquidationClusterSnapshot):
        return None
    return snapshot


def _nearest_liquidation_distance_pct(
    snapshot: LiquidationClusterSnapshot | None,
    *,
    side: LiquidationClusterSide,
    reference_price: float,
) -> float | None:
    if snapshot is None:
        return None
    distances = tuple(
        abs(cluster.price - reference_price) / reference_price * 100.0
        for cluster in snapshot.clusters
        if cluster.side is side
    )
    return min(distances) if distances else None


def _select_current_price(
    *,
    ticker_price: float | None,
    active_candle_price: float | None,
    latest_closed_price: float,
) -> tuple[float, str]:
    if ticker_price is not None:
        return ticker_price, "ticker_price"
    if active_candle_price is not None:
        return active_candle_price, "active_candle_price"
    return latest_closed_price, "latest_closed_price"


def _frame_data_quality_payload(frame: TimeframeContext) -> dict[str, Any]:
    return {
        "latest_closed_price": frame.latest_closed_price,
        "active_candle_price": frame.active_candle_price,
        "ticker_price": frame.ticker_price,
        "spread_percentage": frame.spread_percentage,
        "order_book_spread_percentage": frame.order_book_spread_percentage,
        "order_book_depth_imbalance": frame.order_book_depth_imbalance,
        "exchange_tick_size": frame.exchange_tick_size,
        "exchange_step_size": frame.exchange_step_size,
        "exchange_min_notional": frame.exchange_min_notional,
        "nearest_long_liquidation_distance_pct": frame.nearest_long_cluster_distance_pct,
        "nearest_short_liquidation_distance_pct": frame.nearest_short_cluster_distance_pct,
        "mark_price": frame.mark_price,
        "index_price": frame.index_price,
        "analysis_price": frame.analysis_price,
        "last_closed_at": frame.last_closed_at.isoformat() if frame.last_closed_at else None,
        "last_received_at": frame.last_received_at.isoformat() if frame.last_received_at else None,
        "staleness_seconds": frame.staleness_seconds,
        "is_stale": frame.is_stale,
        "data_confidence": frame.data_confidence,
        "current_price_source": frame.current_price_source,
    }


def _strategy_routing_payload(
    assessment: RiskAssessment,
    phase4: Any,
    routing_config: Mapping[str, Sequence[str]] | None,
) -> dict[str, Any]:
    return dict(
        build_strategy_routing_payload(
            assessment=assessment,
            phase4=phase4,
            routing_config=routing_config,
        )
    )


def _approved_payload(
    setup: RiskApprovedSetup,
    precision_entry_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    max_risk_reward = max(target.risk_reward for target in setup.take_profits)
    entry_classification = classify_entry_state(
        EntryClassificationInput(
            direction=FuturesDirection(setup.direction.value.upper()),
            current_price=setup.entry.current_price,
            zone_low=setup.entry.lower,
            zone_high=setup.entry.upper,
            ideal_entry=setup.entry.preferred,
            maximum_chase_price=setup.entry.maximum_chase_price,
            structural_invalidation=setup.stop_loss.price,
        )
    )
    precision_entry = precision_entry_payload or build_precision_entry_plan(setup).model_dump(
        mode="json"
    )
    return {
        "symbol": setup.symbol,
        "decision": setup.direction.value.upper(),
        "strategy": setup.strategy.value,
        "current_price": setup.entry.current_price,
        "entry_state": entry_classification.state.value,
        "entry_classification": entry_classification.model_dump(mode="json"),
        "precision_entry": dict(precision_entry),
        "entry_zone": {
            "low": setup.entry.lower,
            "high": setup.entry.upper,
            "preferred": setup.entry.preferred,
            "maximum_chase_price": setup.entry.maximum_chase_price,
            "current_price_inside_zone": setup.entry.current_price_inside_zone,
            "state": entry_classification.state.value,
        },
        "stop_loss": setup.stop_loss.price,
        "take_profits": [
            {
                "label": target.label,
                "price": target.price,
                "reward": target.reward,
                "risk_reward": target.risk_reward,
                "rationale": list(target.rationale),
            }
            for target in setup.take_profits
        ],
        "suggested_leverage": {
            "minimum": setup.leverage.minimum,
            "maximum": setup.leverage.maximum,
            "modeled_maximum": setup.leverage.modeled_maximum,
        },
        "position_size": {
            "risk_amount": setup.position_size.risk_amount,
            "quantity": setup.position_size.quantity,
            "notional_value": setup.position_size.notional_value,
            "account_risk_pct": setup.position_size.account_risk_pct,
        },
        "confidence_score": setup.confidence_score,
        "max_risk_reward": max_risk_reward,
        "risk_level": "high",
        "warnings": list(setup.warnings),
    }


def _scan_sort_key(analysis: SymbolAnalysis) -> tuple[int, float, float, str]:
    setup = analysis.assessment.setup
    if setup is None:
        return (1, 0.0, 0.0, analysis.symbol)
    max_risk_reward = max(target.risk_reward for target in setup.take_profits)
    return (0, -setup.confidence_score, -max_risk_reward, analysis.symbol)
