"""Historical futures dataset acquisition tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    MAXIMUM_DATASET_CANDLES,
    acquire_futures_dataset,
    build_dataset_id,
)
from apex.domain.models import Candle


class StubCandleProvider:
    """Minimal provider fixture for acquisition tests."""

    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles
        self.requests: list[tuple[str, str, int]] = []

    @property
    def name(self) -> str:
        return "stub"

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        self.requests.append((symbol, timeframe, limit))
        return list(self._candles)


def test_acquisition_drops_active_candle_and_builds_manifest() -> None:
    candles = _candles(include_active=True)
    provider = StubCandleProvider(candles)
    extracted_at = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

    dataset = acquire_futures_dataset(
        provider=provider,
        symbol="BTC/USDT",
        timeframe="5m",
        candle_limit=4,
        extracted_at=extracted_at,
        dataset_id="btc-train",
    )

    assert provider.requests == [("BTC/USDT", "5m", 4)]
    assert dataset.manifest.dataset_id == "btc-train"
    assert dataset.manifest.candle_count == 3
    assert all(candle.is_closed for candle in dataset.candles)


def test_acquisition_generates_deterministic_default_id() -> None:
    extracted_at = datetime(2026, 7, 15, 12, 34, 56, tzinfo=UTC)
    provider = StubCandleProvider(_candles())

    dataset = acquire_futures_dataset(
        provider=provider,
        symbol="BTC/USDT",
        timeframe="5m",
        candle_limit=3,
        extracted_at=extracted_at,
    )

    assert dataset.manifest.dataset_id == "btcusdt-5m-20260715T123456Z"


def test_dataset_id_removes_filesystem_separators() -> None:
    assert (
        build_dataset_id(
            symbol="BTC/USDT",
            timeframe="15m",
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
        == "btcusdt-15m-20260715T000000Z"
    )


@pytest.mark.parametrize("candle_limit", [0, MAXIMUM_DATASET_CANDLES + 1])
def test_acquisition_rejects_out_of_range_limit(candle_limit: int) -> None:
    with pytest.raises(ValueError, match="candle limit"):
        acquire_futures_dataset(
            provider=StubCandleProvider(_candles()),
            symbol="BTCUSDT",
            timeframe="5m",
            candle_limit=candle_limit,
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )


def test_acquisition_rejects_provider_result_without_closed_candles() -> None:
    active = tuple(candle.model_copy(update={"is_closed": False}) for candle in _candles())

    with pytest.raises(ValueError, match="no closed candles"):
        acquire_futures_dataset(
            provider=StubCandleProvider(active),
            symbol="BTCUSDT",
            timeframe="5m",
            candle_limit=3,
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )


def test_acquisition_rejects_naive_extraction_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        acquire_futures_dataset(
            provider=StubCandleProvider(_candles()),
            symbol="BTCUSDT",
            timeframe="5m",
            candle_limit=3,
            extracted_at=datetime(2026, 7, 15),
        )


def _candles(*, include_active: bool = False) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    count = 4 if include_active else 3

    return tuple(
        Candle(
            symbol="BTCUSDT",
            timeframe="5m",
            open_time=start + timedelta(minutes=index * 5),
            close_time=start + timedelta(minutes=(index + 1) * 5),
            open=100.0 + index,
            high=102.0 + index,
            low=99.0 + index,
            close=101.0 + index,
            volume=1_000.0 + index,
            is_closed=not include_active or index < count - 1,
            source="stub",
        )
        for index in range(count)
    )
