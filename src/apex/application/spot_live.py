"""Live public-data adapter for canonical spot orchestration."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_analysis import SpotAnalysisResult
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    SpotSetupEvidence,
    analyze_spot_orchestration,
)
from apex.application.spot_structure import analyze_spot_structure, classify_spot_market_regime
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import Candle
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_market import SpotMarketBreadthSnapshot
from apex.domain.spot_structure import SpotRegimeInput, SpotTimeframeSnapshot

DEFAULT_SPOT_LIVE_TIMEFRAMES = ("1d", "4h")


class SpotLiveAccountInput(BaseModel):
    """Strict cash-account file input for live public-data analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account: SpotAccountInput
    current_sector_exposure_percentage: float = Field(default=0.0, ge=0)


def load_spot_live_account(path: str | Path) -> SpotLiveAccountInput:
    loaded: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("spot live account input must contain a JSON object")
    return SpotLiveAccountInput.model_validate(cast(dict[str, Any], loaded))


def analyze_live_spot(
    *,
    symbol: str,
    account_input: SpotLiveAccountInput,
    candle_provider: MarketDataProvider,
    ticker_provider: MarketDataProvider,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
    candle_limit: int = 200,
    timeframes: tuple[str, ...] = DEFAULT_SPOT_LIVE_TIMEFRAMES,
    now: datetime | None = None,
) -> SpotAnalysisResult:
    """Fetch public data, build canonical inputs, and reuse S5 orchestration."""

    if candle_limit < 60:
        raise ValueError("spot live analysis requires at least 60 candles per timeframe")
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("spot live symbol cannot be blank")
    observed_at = now or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("spot live analysis time must be timezone-aware")

    current_price = ticker_provider.fetch_ticker(normalized_symbol).last_price
    symbol_candles = _fetch_timeframes(
        candle_provider, normalized_symbol, timeframes, candle_limit, observed_at
    )
    symbol_snapshots = tuple(
        _snapshot(timeframe, candles) for timeframe, candles in symbol_candles.items()
    )
    structure = analyze_spot_structure(symbol_snapshots)

    btc_symbol = "BTCUSDT"
    btc_candles = (
        symbol_candles
        if normalized_symbol == btc_symbol
        else _fetch_timeframes(candle_provider, btc_symbol, timeframes, candle_limit, observed_at)
    )
    btc_structure = analyze_spot_structure(
        tuple(_snapshot(timeframe, candles) for timeframe, candles in btc_candles.items())
    )
    regime = classify_spot_market_regime(
        SpotRegimeInput(
            btc_trend=btc_structure.trend,
            btc_extension=btc_structure.extension,
            breadth=SpotMarketBreadthSnapshot(
                advancing_assets=0,
                declining_assets=0,
                unchanged_assets=0,
                percentage_above_trend=None,
            ),
        )
    )

    thesis_timeframe = max(timeframes, key=_timeframe_seconds)
    thesis_candles = symbol_candles[thesis_timeframe]
    thesis_snapshot = _snapshot(thesis_timeframe, thesis_candles)
    support = max(thesis_snapshot.swing_low - thesis_snapshot.atr * 0.35, 0.00000001)
    recovery = min(current_price, thesis_snapshot.ema_fast)
    deeper_support = max(support - thesis_snapshot.atr, 0.00000001)
    if recovery <= deeper_support:
        recovery = min(current_price, support)

    return analyze_spot_orchestration(
        SpotOrchestrationInput(
            symbol=normalized_symbol,
            current_price=current_price,
            structure=structure,
            regime=regime,
            account=account_input.account,
            evidence=_evidence(thesis_candles),
            deeper_support_price=deeper_support,
            recovery_entry_price=recovery,
            current_sector_exposure_percentage=(
                account_input.current_sector_exposure_percentage
            ),
        ),
        product_config=product_config,
        strategy_config=strategy_config,
    )


def _fetch_timeframes(
    provider: MarketDataProvider,
    symbol: str,
    timeframes: tuple[str, ...],
    candle_limit: int,
    now: datetime,
) -> dict[str, tuple[Candle, ...]]:
    if not timeframes or len(set(timeframes)) != len(timeframes):
        raise ValueError("spot live timeframes must be non-empty and unique")
    result: dict[str, tuple[Candle, ...]] = {}
    for timeframe in timeframes:
        candles = tuple(
            candle
            for candle in provider.fetch_candles(symbol, timeframe, limit=candle_limit)
            if candle.is_closed
        )
        if len(candles) < 60:
            raise ValueError(f"insufficient closed spot candles for {symbol} {timeframe}")
        if candles[-1].close_time < now - timedelta(seconds=_timeframe_seconds(timeframe) * 2):
            raise ValueError(f"stale spot candles for {symbol} {timeframe}")
        result[timeframe] = candles
    return result


def _snapshot(timeframe: str, candles: Sequence[Candle]) -> SpotTimeframeSnapshot:
    closes = [candle.close for candle in candles]
    fast = _ema(closes, 20)
    slow = _ema(closes, 50)
    atr = _atr(candles, 14)
    recent = candles[-20:]
    prior = candles[-40:-20]
    recent_high = max(candle.high for candle in recent)
    recent_low = min(candle.low for candle in recent)
    prior_high = max(candle.high for candle in prior)
    prior_low = min(candle.low for candle in prior)
    return SpotTimeframeSnapshot(
        timeframe=timeframe,
        close=closes[-1],
        ema_fast=fast,
        ema_slow=slow,
        swing_high=recent_high,
        swing_low=recent_low,
        atr=atr,
        higher_high=recent_high > prior_high,
        higher_low=recent_low > prior_low,
        lower_high=recent_high < prior_high,
        lower_low=recent_low < prior_low,
    )


def _evidence(candles: Sequence[Candle]) -> SpotSetupEvidence:
    volumes = [candle.volume for candle in candles[-21:]]
    average = sum(volumes[:-1]) / len(volumes[:-1]) if volumes[:-1] else 0.0
    volume_ratio = volumes[-1] / average if average > 0 else None
    recent_high = max(candle.high for candle in candles[-20:])
    pullback = max((recent_high - candles[-1].close) / recent_high * 100, 0.0)
    return SpotSetupEvidence(
        volume_ratio=volume_ratio,
        pullback_depth_percentage=pullback,
    )


def _ema(values: Sequence[float], period: int) -> float:
    seed = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    value = seed
    for item in values[period:]:
        value = ((item - value) * multiplier) + value
    return value


def _atr(candles: Sequence[Candle], period: int) -> float:
    ranges = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:], strict=True):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    value = sum(ranges) / len(ranges)
    if value <= 0:
        raise ValueError("spot live ATR must be positive")
    return value


def _timeframe_seconds(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    factors = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    try:
        return value * factors[unit]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unsupported spot live timeframe: {timeframe}") from exc
