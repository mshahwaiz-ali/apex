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

from apex.config import DEFAULT_TIMEFRAME_ROLES
from apex.config.settings import DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import Candle, TickerSnapshot
from apex.features.registry import create_default_feature_registry
from apex.phase3 import analyze_phase3
from apex.risk import (
    DEFAULT_RISK_CONFIG,
    ExposureState,
    RiskAssessment,
    RiskConfig,
    RiskDecision,
    analyze_phase6,
    load_risk_config,
)
from apex.risk.contracts import RiskApprovedSetup
from apex.scoring import analyze_phase5
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    analyze_phase4,
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
) -> SymbolAnalysis:
    """Run the deterministic Phase 4 to Phase 6 stack for one symbol."""

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
    phase5 = analyze_phase5(phase4)
    assessment = analyze_phase6(
        phase5,
        config=risk_config,
        exposure=exposure,
    )
    return SymbolAnalysis(
        symbol=symbol,
        generated_at=decision_time,
        assessment=assessment,
        candidate_count=len(phase4.candidates),
        evaluated_timeframes=tuple(frame.timeframe for frame in context.frames),
        regime_by_timeframe=regimes,
        data_quality_by_timeframe={
            frame.timeframe: _frame_data_quality_payload(frame) for frame in context.frames
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
    ticker_price = _fetch_ticker_price(provider, symbol)
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
) -> ScanResult:
    """Analyze each symbol independently and rank approved setups."""

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
                )
            )
        except Exception as exc:  # Scanner must isolate per-symbol failures.
            failures[symbol] = str(exc)

    ranked = tuple(sorted(analyses, key=_scan_sort_key))
    return ScanResult(generated_at=timestamp, analyses=ranked, failures=failures)


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
        payload = _approved_payload(assessment.setup)
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
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "long"
    )
    short_setups = tuple(
        item
        for item in approved
        if item.assessment.setup is not None and item.assessment.setup.direction.value == "short"
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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_symbol_text(analysis: SymbolAnalysis) -> str:
    """Return concise human-readable analysis output."""

    payload = serialize_symbol_analysis(analysis)
    if payload["decision"] == "NO_TRADE":
        reasons = "; ".join(payload["reasons"]) or "no qualifying setup"
        return f"{analysis.symbol}: NO_TRADE | {reasons}"

    return (
        f"{analysis.symbol}: {payload['decision']} {payload['strategy']} "
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
) -> tuple[TimeframeContext, str]:
    if not candles:
        raise ValueError(f"{symbol} {timeframe} returned no candles")
    features_by_name = create_default_feature_registry().calculate_all(candles)
    relative_volume = features_by_name["relative_volume_20"][0].values
    relative_volume_for_phase3 = relative_volume if len(relative_volume) == len(candles) else None
    phase3 = analyze_phase3(candles, relative_volume=relative_volume_for_phase3)
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


def _fetch_ticker_price(provider: MarketDataProvider, symbol: str) -> float | None:
    fetch_ticker = getattr(provider, "fetch_ticker", None)
    if not callable(fetch_ticker):
        return None
    try:
        snapshot = fetch_ticker(symbol)
    except Exception:
        return None
    if not isinstance(snapshot, TickerSnapshot):
        return None
    return snapshot.last_price


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


def _approved_payload(setup: RiskApprovedSetup) -> dict[str, Any]:
    max_risk_reward = max(target.risk_reward for target in setup.take_profits)
    return {
        "symbol": setup.symbol,
        "decision": setup.direction.value.upper(),
        "strategy": setup.strategy.value,
        "current_price": setup.entry.current_price,
        "entry_zone": {
            "low": setup.entry.lower,
            "high": setup.entry.upper,
            "preferred": setup.entry.preferred,
            "maximum_chase_price": setup.entry.maximum_chase_price,
            "current_price_inside_zone": setup.entry.current_price_inside_zone,
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
