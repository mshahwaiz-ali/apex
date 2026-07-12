from datetime import UTC, datetime, timedelta

import pytest

from apex.application.analysis import (
    build_strategy_context,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
)
from apex.domain import Candle
from apex.domain.models import TickerSnapshot
from apex.strategies import TimeframeRole

NOW = datetime(2026, 7, 13, tzinfo=UTC)


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, int]] = []

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        if symbol == "BROKEN/USDT":
            raise RuntimeError("fixture failure")
        self.requests.append((symbol, timeframe, limit))
        candles: list[Candle] = []
        start = NOW - timedelta(minutes=limit)
        for index in range(limit):
            base = 100.0 + index * 0.05
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=start + timedelta(minutes=index),
                    close_time=start + timedelta(minutes=index + 1),
                    open=base,
                    high=base + 1.5,
                    low=base - 1.0,
                    close=base + 0.5,
                    volume=100.0 + index,
                    is_closed=True,
                    source="fixture",
                )
            )
        return candles


class ActiveFinalProvider(FakeProvider):
    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        candles = super().fetch_candles(symbol, timeframe, limit)
        final = candles[-1]
        candles[-1] = Candle(
            symbol=final.symbol,
            timeframe=final.timeframe,
            open_time=final.open_time,
            close_time=final.close_time,
            open=final.open,
            high=final.high + 1.0,
            low=final.low,
            close=final.close + 2.0,
            volume=final.volume,
            is_closed=False,
            source=final.source,
        )
        return candles


class TickerProvider(FakeProvider):
    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=symbol,
            last_price=123.45,
            bid_price=123.40,
            ask_price=123.50,
            quote_volume_24h=1_000_000.0,
            captured_at=NOW,
            source="fixture",
        )


def test_load_symbols_validates_config(tmp_path) -> None:
    path = tmp_path / "symbols.yaml"
    path.write_text("symbols:\n  - BTC/USDT\n  - ETH/USDT\n", encoding="utf-8")

    assert load_symbols(path) == ("BTC/USDT", "ETH/USDT")


def test_load_symbols_rejects_duplicates(tmp_path) -> None:
    path = tmp_path / "symbols.yaml"
    path.write_text("symbols:\n  - BTC/USDT\n  - BTC/USDT\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        load_symbols(path)


def test_scan_isolates_symbol_failures() -> None:
    result = scan_symbols(
        ("BTC/USDT", "BROKEN/USDT"),
        FakeProvider(),
        timeframes=("5m",),
        candle_limit=80,
        generated_at=NOW,
    )

    payload = serialize_scan_result(result)

    assert "BROKEN/USDT" in payload["failures"]
    assert payload["results"]
    assert payload["generated_at"] == NOW.isoformat()
    assert "timeframe_data_quality" in payload["results"][0]
    assert "5m" in payload["results"][0]["timeframe_data_quality"]
    assert "current_price_source" in payload["results"][0]["timeframe_data_quality"]["5m"]


def test_strategy_context_uses_configured_timeframe_roles() -> None:
    provider = FakeProvider()

    context, regimes = build_strategy_context(
        "BTC/USDT",
        provider,
        timeframes=("5m", "1D"),
        candle_limit=80,
        timeframe_roles={"1D": "long_term_macro", "5m": "entry"},
    )

    assert provider.requests == [("BTC/USDT", "5m", 80), ("BTC/USDT", "1D", 80)]
    assert [frame.timeframe for frame in context.frames] == ["1D", "5m"]
    assert [frame.role for frame in context.frames] == [
        TimeframeRole.LONG_TERM_MACRO,
        TimeframeRole.ENTRY,
    ]
    assert set(regimes) == {"1D", "5m"}


def test_strategy_context_exposes_closed_active_and_staleness_prices() -> None:
    context, _regimes = build_strategy_context(
        "BTC/USDT",
        ActiveFinalProvider(),
        timeframes=("5m",),
        candle_limit=80,
        timeframe_roles={"5m": "entry"},
        timeframe_max_staleness_seconds={"5m": 60},
        received_at=NOW + timedelta(minutes=10),
    )

    frame = context.frames[0]

    assert frame.current_price == frame.active_candle_price
    assert frame.current_price_source == "active_candle_price"
    assert frame.analysis_price == frame.latest_closed_price
    assert frame.active_candle_price is not None
    assert frame.active_candle_price > frame.latest_closed_price
    assert frame.last_closed_at is not None
    assert frame.last_received_at == NOW + timedelta(minutes=10)
    assert frame.staleness_seconds is not None
    assert frame.staleness_seconds > 60
    assert frame.is_stale is True
    assert frame.data_confidence == 0.5


def test_strategy_context_prefers_ticker_price_for_current_price() -> None:
    context, _regimes = build_strategy_context(
        "BTC/USDT",
        TickerProvider(),
        timeframes=("5m",),
        candle_limit=80,
        timeframe_roles={"5m": "entry"},
        received_at=NOW,
    )

    frame = context.frames[0]

    assert frame.current_price == 123.45
    assert frame.ticker_price == 123.45
    assert frame.current_price_source == "ticker_price"
    assert frame.analysis_price == frame.latest_closed_price
