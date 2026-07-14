"""Reproducible futures candle dataset tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting import (
    FuturesCandleDataset,
    build_futures_dataset,
    hash_candles,
    load_futures_dataset,
    write_futures_dataset,
)
from apex.domain.models import Candle


def test_build_dataset_creates_deterministic_manifest() -> None:
    candles = _candles()

    first = build_futures_dataset(
        dataset_id="btc-5m-train",
        candles=candles,
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    second = build_futures_dataset(
        dataset_id="btc-5m-train",
        candles=candles,
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    assert first == second
    assert first.manifest.symbol == "BTCUSDT"
    assert first.manifest.timeframe == "5m"
    assert first.manifest.candle_count == 3
    assert first.manifest.content_hash == hash_candles(candles)
    assert len(first.manifest.content_hash) == 64


def test_dataset_round_trip_revalidates_content(tmp_path: Path) -> None:
    dataset = build_futures_dataset(
        dataset_id="btc-5m-validation",
        candles=_candles(),
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    path = tmp_path / "dataset.json"

    write_futures_dataset(path, dataset)

    assert load_futures_dataset(path) == dataset


def test_dataset_rejects_active_candle() -> None:
    candles = list(_candles())
    candles[-1] = candles[-1].model_copy(update={"is_closed": False})

    with pytest.raises(ValueError, match="active candles"):
        build_futures_dataset(
            dataset_id="invalid-active",
            candles=tuple(candles),
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )


def test_dataset_rejects_duplicate_open_time() -> None:
    candles = list(_candles())
    candles[-1] = candles[-1].model_copy(
        update={
            "open_time": candles[-2].open_time,
            "close_time": candles[-2].close_time,
        }
    )

    with pytest.raises(ValueError, match="duplicate candle times"):
        build_futures_dataset(
            dataset_id="invalid-duplicate",
            candles=tuple(candles),
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )


def test_dataset_rejects_mixed_symbol() -> None:
    candles = list(_candles())
    candles[-1] = candles[-1].model_copy(update={"symbol": "ETHUSDT"})

    with pytest.raises(ValueError, match="mix symbols"):
        build_futures_dataset(
            dataset_id="invalid-symbol",
            candles=tuple(candles),
            extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
        )


def test_load_rejects_tampered_candle_content(tmp_path: Path) -> None:
    dataset = build_futures_dataset(
        dataset_id="btc-5m-test",
        candles=_candles(),
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    path = tmp_path / "dataset.json"
    write_futures_dataset(path, dataset)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candles"][0]["close"] = 999.0
    payload["candles"][0]["high"] = 999.0
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash"):
        load_futures_dataset(path)


def test_manifest_mismatch_is_rejected() -> None:
    dataset = build_futures_dataset(
        dataset_id="btc-5m-test",
        candles=_candles(),
        extracted_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    mismatched = dataset.manifest.__class__(
        dataset_id=dataset.manifest.dataset_id,
        symbol="ETHUSDT",
        timeframe=dataset.manifest.timeframe,
        source=dataset.manifest.source,
        extracted_at=dataset.manifest.extracted_at,
        start_time=dataset.manifest.start_time,
        end_time=dataset.manifest.end_time,
        candle_count=dataset.manifest.candle_count,
        content_hash=dataset.manifest.content_hash,
    )

    with pytest.raises(ValueError, match="manifest symbol"):
        FuturesCandleDataset(
            manifest=mismatched,
            candles=dataset.candles,
        )


def _candles() -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
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
            is_closed=True,
            source="binance",
        )
        for index in range(3)
    )
