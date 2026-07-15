"""Provider-independent live spot eligibility metadata construction."""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from apex.domain.models import Candle, TickerSnapshot
from apex.domain.spot_market import SpotMarketMetadata


def build_spot_market_metadata(
    *,
    symbol: str,
    quote_asset: str,
    ticker: TickerSnapshot,
    candles: Sequence[Candle],
    terminal_extension_atr_multiple: float,
    market_age_days: int | None = None,
) -> SpotMarketMetadata:
    """Build measurable eligibility metadata without provider-specific fields."""

    normalized_symbol = symbol.strip().upper()
    normalized_quote = quote_asset.strip().upper()
    if not normalized_symbol or not normalized_quote:
        raise ValueError("spot eligibility symbol and quote asset cannot be blank")
    if not normalized_symbol.endswith(normalized_quote):
        raise ValueError(f"spot symbol {normalized_symbol} does not end with {normalized_quote}")
    base_asset = normalized_symbol[: -len(normalized_quote)]
    if not base_asset:
        raise ValueError("spot eligibility base asset cannot be blank")

    closed = tuple(candle for candle in candles if candle.is_closed)
    atr = _atr(closed, 14) if len(closed) >= 15 else None
    last_close = closed[-1].close if closed else None
    atr_percentage = (
        atr / last_close * 100 if atr is not None and last_close is not None else None
    )
    downside = _downside_volatility_percentage(closed[-21:])
    terminal_extension = False
    if atr is not None and len(closed) >= 20:
        ema_fast = _ema([candle.close for candle in closed], 20)
        terminal_extension = (
            closed[-1].close - ema_fast
        ) / atr >= terminal_extension_atr_multiple

    return SpotMarketMetadata(
        symbol=normalized_symbol,
        base_asset=base_asset,
        quote_asset=normalized_quote,
        quote_volume_24h=ticker.quote_volume_24h,
        spread_percentage=ticker.spread_percentage,
        market_age_days=market_age_days,
        available_candle_count=len(closed),
        has_data_gaps=_has_candle_gaps(closed),
        atr_percentage=atr_percentage,
        downside_volatility_percentage=downside,
        terminal_extension=terminal_extension,
    )


def _has_candle_gaps(candles: Sequence[Candle]) -> bool:
    if len(candles) < 2:
        return False
    expected = candles[0].close_time - candles[0].open_time
    return any(
        current.open_time != previous.close_time
        or current.close_time - current.open_time != expected
        for previous, current in zip(candles, candles[1:], strict=True)
    )


def _downside_volatility_percentage(candles: Sequence[Candle]) -> float | None:
    if len(candles) < 2:
        return None
    downside_returns = [
        min((current.close - previous.close) / previous.close * 100, 0.0)
        for previous, current in zip(candles, candles[1:], strict=True)
    ]
    return sqrt(sum(value * value for value in downside_returns) / len(downside_returns))


def _ema(values: Sequence[float], period: int) -> float:
    if len(values) < period:
        raise ValueError("spot eligibility EMA requires sufficient values")
    seed = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    value = seed
    for item in values[period:]:
        value = ((item - value) * multiplier) + value
    return value


def _atr(candles: Sequence[Candle], period: int) -> float:
    ranges = [
        max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        for previous, current in zip(candles[-period - 1 : -1], candles[-period:], strict=True)
    ]
    if not ranges:
        raise ValueError("spot eligibility ATR requires sufficient candles")
    return sum(ranges) / len(ranges)
