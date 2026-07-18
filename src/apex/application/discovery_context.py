"""Discovery-neutral market context construction and data-quality reporting."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from apex.config import DEFAULT_TIMEFRAME_ROLES
from apex.config.settings import DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
from apex.data.providers.base import MarketDataProvider
from apex.domain.models import (
    Candle,
    ExchangeFilterSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)
from apex.features.registry import create_default_feature_registry
from apex.market_analysis import analyze_structure_and_liquidity
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    timeframe_role_sort_key,
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
    """Fetch market data and build deterministic strategy context."""

    role_config = timeframe_roles or DEFAULT_TIMEFRAME_ROLES
    staleness_config = timeframe_max_staleness_seconds or DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
    timestamp = received_at or datetime.now(UTC)
    ticker_snapshot = _fetch_ticker_snapshot(provider, symbol)
    ticker_price = ticker_snapshot.last_price if ticker_snapshot is not None else None
    spread_percentage = ticker_snapshot.spread_percentage if ticker_snapshot is not None else None
    order_book_snapshot = _fetch_order_book_snapshot(provider, symbol)
    exchange_filter_snapshot = _fetch_exchange_filter_snapshot(provider, symbol)
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


def frame_data_quality_payload(frame: TimeframeContext) -> dict[str, Any]:
    """Serialize market-data freshness and execution-quality observations."""

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
        "mark_price": frame.mark_price,
        "index_price": frame.index_price,
        "analysis_price": frame.analysis_price,
        "last_closed_at": (frame.last_closed_at.isoformat() if frame.last_closed_at else None),
        "last_received_at": (
            frame.last_received_at.isoformat() if frame.last_received_at else None
        ),
        "staleness_seconds": frame.staleness_seconds,
        "is_stale": frame.is_stale,
        "data_confidence": frame.data_confidence,
        "current_price_source": frame.current_price_source,
    }


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
) -> tuple[TimeframeContext, str]:
    if not candles:
        raise ValueError(f"{symbol} {timeframe} returned no candles")
    features_by_name = create_default_feature_registry().calculate_all(candles)
    relative_volume = features_by_name["relative_volume_20"][0].values
    relative_volume_for_market_analysis = (
        relative_volume if len(relative_volume) == len(candles) else None
    )
    market_analysis = analyze_structure_and_liquidity(
        candles,
        relative_volume=relative_volume_for_market_analysis,
    )
    latest_closed = candles[-2] if not candles[-1].is_closed and len(candles) > 1 else candles[-1]
    active_candle_price = candles[-1].close if not candles[-1].is_closed else None
    live_price, live_price_source = _select_current_price(
        ticker_price=ticker_price,
        active_candle_price=active_candle_price,
        latest_closed_price=latest_closed.close,
    )
    staleness_seconds = max(
        0.0,
        (received_at - latest_closed.close_time).total_seconds(),
    )
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
        trend_strength=market_analysis.structure.trend.strength,
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
            analysis_price=latest_closed.close,
            last_closed_at=latest_closed.close_time,
            last_received_at=received_at,
            staleness_seconds=staleness_seconds,
            is_stale=is_stale,
            data_confidence=0.5 if is_stale else 1.0,
            current_price_source=live_price_source,
            features=snapshot,
            structure=market_analysis.structure,
            liquidity=market_analysis.liquidity,
            active_candle=not candles[-1].is_closed,
            recent_candles=tuple(candles),
        ),
        market_analysis.regime.value,
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


def _fetch_ticker_snapshot(
    provider: MarketDataProvider,
    symbol: str,
) -> TickerSnapshot | None:
    fetch_ticker = getattr(provider, "fetch_ticker", None)
    if not callable(fetch_ticker):
        return None
    try:
        snapshot = fetch_ticker(symbol)
    except Exception:
        return None
    return snapshot if isinstance(snapshot, TickerSnapshot) else None


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
    return snapshot if isinstance(snapshot, OrderBookSnapshot) else None


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
    return snapshot if isinstance(snapshot, ExchangeFilterSnapshot) else None


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
