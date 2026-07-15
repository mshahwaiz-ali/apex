from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.spot_eligibility import build_spot_market_metadata
from apex.domain.models import Candle, TickerSnapshot


def _candles() -> tuple[Candle, ...]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index in range(20):
        open_time = start + timedelta(hours=4 * index)
        close = 100.0 + index
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="4h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000.0,
                is_closed=True,
                source="fixture",
            )
        )
    return tuple(candles)


def test_build_spot_market_metadata_handles_adjacent_candle_pairs() -> None:
    ticker = TickerSnapshot(
        symbol="BTCUSDT",
        last_price=119.0,
        bid_price=118.9,
        ask_price=119.1,
        quote_volume_24h=50_000_000.0,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
        source="fixture",
    )

    metadata = build_spot_market_metadata(
        symbol="BTCUSDT",
        quote_asset="USDT",
        ticker=ticker,
        candles=_candles(),
        terminal_extension_atr_multiple=4.0,
    )

    assert metadata.available_candle_count == 20
    assert metadata.has_data_gaps is False
    assert metadata.atr_percentage is not None
    assert metadata.downside_volatility_percentage == 0.0
