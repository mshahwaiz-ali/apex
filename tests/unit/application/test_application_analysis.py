from datetime import UTC, datetime, timedelta

import pytest

from apex.application.analysis import load_symbols, scan_symbols, serialize_scan_result
from apex.domain import Candle

NOW = datetime(2026, 7, 13, tzinfo=UTC)


class FakeProvider:
    name = "fake"

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        if symbol == "BROKEN/USDT":
            raise RuntimeError("fixture failure")
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
