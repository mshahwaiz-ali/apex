"""Tests for live public-data spot orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_live import analyze_live_spot, load_spot_live_account
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain.models import Candle, TickerSnapshot

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)
ACCOUNT = Path("tests/fixtures/spot_live/account.json")


class FakeProvider:
    name = "fake"

    def __init__(self, *, stale: bool = False, missing: str | None = None) -> None:
        self.stale = stale
        self.missing = missing
        self.requested_timeframes: list[str] = []

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        self.requested_timeframes.append(timeframe)
        if timeframe == self.missing:
            return []
        seconds = {"12h": 43200, "4h": 14400}[timeframe]
        end = NOW - (timedelta(days=10) if self.stale else timedelta())
        candles: list[Candle] = []
        for index in range(limit):
            open_time = end - timedelta(seconds=seconds * (limit - index))
            base = 80.0 + index * 0.3
            close = base + 0.2
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=open_time + timedelta(seconds=seconds),
                    open=base,
                    high=close + 0.4,
                    low=base - 0.4,
                    close=close,
                    volume=1000.0 + index,
                    is_closed=True,
                    source="fake",
                )
            )
        return candles

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=symbol,
            last_price=140.0,
            bid_price=139.9,
            ask_price=140.1,
            quote_volume_24h=1_000_000.0,
            captured_at=NOW,
            source="fake",
        )


def _analyze(provider: FakeProvider):
    return analyze_live_spot(
        symbol="ETHUSDT",
        account_input=load_spot_live_account(ACCOUNT),
        candle_provider=provider,
        ticker_provider=provider,
        product_config=load_spot_product_config("config/spot.yaml"),
        strategy_config=load_spot_strategy_config("config/spot_strategies.yaml"),
        candle_limit=80,
        now=NOW,
    )


def test_live_spot_builds_all_strategy_candidates() -> None:
    provider = FakeProvider()
    payload = spot_analysis_result_to_payload(_analyze(provider))

    assert len(payload["candidates"]) == 6
    assert payload["schema_version"]
    assert provider.requested_timeframes == ["12h", "4h", "12h", "4h"]


def test_live_spot_repeated_execution_is_deterministic() -> None:
    first = spot_analysis_result_to_payload(_analyze(FakeProvider()))
    second = spot_analysis_result_to_payload(_analyze(FakeProvider()))

    assert first == second


def test_live_spot_rejects_missing_timeframe() -> None:
    with pytest.raises(ValueError, match="insufficient closed spot candles"):
        _analyze(FakeProvider(missing="4h"))


def test_live_spot_rejects_stale_candles() -> None:
    with pytest.raises(ValueError, match="stale spot candles"):
        _analyze(FakeProvider(stale=True))


def test_live_account_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "account.json"
    path.write_text('{"account": {}, "unexpected": true}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_spot_live_account(path)
