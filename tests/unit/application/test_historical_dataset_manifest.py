from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.historical_dataset_manifest import (
    DatasetIssueCode,
    DatasetValidationState,
    build_curated_dataset_manifest,
    canonical_candle_content_hash,
    validate_curated_candles,
)
from apex.application.historical_edge import DatasetPartition, DatasetSplit, MarketType

_START = datetime(2026, 1, 1, tzinfo=UTC)


def _row(index: int, **updates: object) -> dict[str, object]:
    open_time = _START + timedelta(minutes=5 * index)
    row: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "open_time": open_time,
        "close_time": open_time + timedelta(minutes=5),
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 10.0,
    }
    row.update(updates)
    return row


def _partitions() -> tuple[DatasetPartition, ...]:
    return (
        DatasetPartition(DatasetSplit.TRAIN, _START, _START + timedelta(minutes=10)),
        DatasetPartition(
            DatasetSplit.VALIDATION,
            _START + timedelta(minutes=10),
            _START + timedelta(minutes=15),
        ),
        DatasetPartition(
            DatasetSplit.TEST,
            _START + timedelta(minutes=15),
            _START + timedelta(minutes=20),
        ),
    )


def test_canonical_hash_ignores_record_and_key_order() -> None:
    rows = [_row(0), _row(1)]
    reversed_rows = [dict(reversed(tuple(row.items()))) for row in reversed(rows)]

    assert canonical_candle_content_hash(rows) == canonical_candle_content_hash(reversed_rows)


def test_duplicate_timestamp_is_invalid_and_counted() -> None:
    result = validate_curated_candles([_row(0), _row(0)], expected_interval="5m")

    assert result.state is DatasetValidationState.INVALID
    assert result.duplicate_count == 1
    assert DatasetIssueCode.DUPLICATE_TIMESTAMP in {issue.code for issue in result.issues}


def test_malformed_ohlc_is_rejected() -> None:
    result = validate_curated_candles(
        [_row(0, high=100.0, close=101.0)],
        expected_interval="5m",
    )

    assert result.state is DatasetValidationState.INVALID
    assert DatasetIssueCode.IMPOSSIBLE_OHLC in {issue.code for issue in result.issues}


def test_negative_volume_is_rejected() -> None:
    result = validate_curated_candles([_row(0, volume=-1.0)], expected_interval="5m")

    assert result.state is DatasetValidationState.INVALID
    assert DatasetIssueCode.NEGATIVE_VOLUME in {issue.code for issue in result.issues}


def test_missing_interval_is_warning() -> None:
    result = validate_curated_candles([_row(0), _row(2)], expected_interval="5m")

    assert result.state is DatasetValidationState.VALID_WITH_WARNINGS
    assert result.missing_interval_count == 1
    assert DatasetIssueCode.MISSING_INTERVAL in {issue.code for issue in result.issues}


def test_out_of_range_partition_rejects_manifest() -> None:
    partitions = (
        DatasetPartition(
            DatasetSplit.TRAIN,
            _START - timedelta(minutes=5),
            _START + timedelta(minutes=5),
        ),
    )
    result = build_curated_dataset_manifest(
        dataset_id="btc-5m-v1",
        market_type=MarketType.FUTURES,
        source_type="file",
        source_identifier="fixtures/btc.json",
        exchange_provider="binance",
        records=[_row(0), _row(1)],
        expected_interval="5m",
        partitions=partitions,
        created_at=_START,
    )

    assert result.manifest is None
    assert result.validation.state is DatasetValidationState.INVALID
    assert DatasetIssueCode.PARTITION_OUT_OF_RANGE in {
        issue.code for issue in result.validation.issues
    }


def test_valid_manifest_contains_canonical_identity_and_quality_counts() -> None:
    rows = [_row(index) for index in range(4)]
    result = build_curated_dataset_manifest(
        dataset_id="btc-5m-v1",
        market_type=MarketType.FUTURES,
        source_type="file",
        source_identifier="fixtures/btc.json",
        exchange_provider="binance",
        records=rows,
        expected_interval="5m",
        partitions=_partitions(),
        created_at=_START,
        expected_symbols=("BTCUSDT",),
        expected_timeframes=("5m",),
    )

    assert result.validation.state is DatasetValidationState.VALID
    assert result.manifest is not None
    assert result.manifest.content_hash == canonical_candle_content_hash(rows)
    assert result.manifest.symbols == ("BTCUSDT",)
    assert result.manifest.timeframes == ("5m",)
    assert result.manifest.duplicate_count == 0
    assert result.manifest.missing_interval_count == 0
