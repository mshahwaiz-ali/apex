"""Parity tests for shared scan/analyze candlestick methodology evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.discovery_analysis import analyze_symbol, scan_symbols
from apex.application.enriched_public_output import serialize_symbol_analysis
from apex.domain.models import Candle


class FakeProvider:
    name = "fake"

    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        return [
            candle.model_copy(update={"symbol": symbol, "timeframe": timeframe})
            for candle in self._candles[-limit:]
        ]


def _candles() -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    price = 130.0
    for index in range(219):
        opened = start + timedelta(minutes=15 * index)
        close = price - 0.35
        candles.append(
            Candle(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time=opened,
                close_time=opened + timedelta(minutes=15),
                open=price,
                high=price + 0.15,
                low=close - 0.15,
                close=close,
                volume=1_000 + index,
                is_closed=True,
                source="test",
            )
        )
        price = close
    opened = start + timedelta(minutes=15 * 219)
    candles.append(
        Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time=opened,
            close_time=opened + timedelta(minutes=15),
            open=price - 0.1,
            high=price + 0.5,
            low=price - 3.0,
            close=price + 0.25,
            volume=2_000,
            is_closed=True,
            source="test",
        )
    )
    return tuple(candles)


def test_scan_and_analyze_share_candlestick_evidence() -> None:
    provider = FakeProvider(_candles())
    generated_at = datetime(2026, 1, 4, tzinfo=UTC)

    selected = analyze_symbol(
        "BTCUSDT",
        provider,
        timeframes=("15m",),
        candle_limit=220,
        generated_at=generated_at,
    )
    scanned = scan_symbols(
        ("BTCUSDT",),
        provider,
        timeframes=("15m",),
        candle_limit=220,
        generated_at=generated_at,
    ).analyses[0]

    selected_candles = selected.phase5_diagnostics["candlestick_evidence"]
    scanned_candles = scanned.phase5_diagnostics["candlestick_evidence"]
    assert selected_candles == scanned_candles
    assert any(item["pattern_id"] == "hammer" for item in selected_candles)


def test_scan_and_analyze_serialize_the_same_full_methodology() -> None:
    provider = FakeProvider(_candles())
    generated_at = datetime(2026, 1, 4, tzinfo=UTC)

    selected = analyze_symbol(
        "BTCUSDT",
        provider,
        timeframes=("15m",),
        candle_limit=220,
        generated_at=generated_at,
    )
    scanned = scan_symbols(
        ("BTCUSDT",),
        provider,
        timeframes=("15m",),
        candle_limit=220,
        generated_at=generated_at,
    ).analyses[0]

    selected_payload = serialize_symbol_analysis(selected)
    scanned_payload = serialize_symbol_analysis(scanned)

    assert selected_payload == scanned_payload
    assert selected_payload["snapshot_identity"]["snapshot_id"]
    assert (
        selected_payload["snapshot_identity"]["snapshot_id"]
        == scanned_payload["snapshot_identity"]["snapshot_id"]
    )
    assert selected_payload["opportunity_portfolio"] == scanned_payload["opportunity_portfolio"]
