from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    EvidenceQuality,
    EvidenceThresholds,
    HistoricalOutcome,
    MarketType,
    build_dataset_metadata,
)
from apex.application.historical_edge_io import (
    load_historical_edge_report_sqlite,
    write_historical_dataset_sqlite,
    write_historical_outcomes_sqlite,
)
from apex.application.historical_edge_query import (
    HistoricalEdgeQueryRequest,
    load_historical_datasets_sqlite,
    query_historical_outcomes_sqlite,
    run_historical_edge_query,
)

BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def _partitions() -> tuple[DatasetPartition, ...]:
    return (
        DatasetPartition(
            split=DatasetSplit.TRAIN,
            start_at=BASE_TIME,
            end_at=BASE_TIME + timedelta(days=30),
        ),
        DatasetPartition(
            split=DatasetSplit.VALIDATION,
            start_at=BASE_TIME + timedelta(days=30),
            end_at=BASE_TIME + timedelta(days=45),
        ),
        DatasetPartition(
            split=DatasetSplit.TEST,
            start_at=BASE_TIME + timedelta(days=45),
            end_at=BASE_TIME + timedelta(days=60),
        ),
    )


def _metadata(
    dataset_id: str = "futures-v1",
    *,
    market_type: MarketType = MarketType.FUTURES,
):
    return build_dataset_metadata(
        dataset_id=dataset_id,
        market_type=market_type,
        symbols=("BTCUSDT",),
        timeframes=("1h", "4h"),
        source="fixture",
        first_observation_at=BASE_TIME,
        last_observation_at=BASE_TIME + timedelta(days=60),
        observation_count=100,
        partitions=_partitions(),
        content_payload={"dataset": dataset_id},
    )


def _outcome(
    index: int,
    *,
    dataset_id: str = "futures-v1",
    split: DatasetSplit = DatasetSplit.TRAIN,
    strategy: str = "trend_pullback",
    symbol: str = "BTCUSDT",
    regime: str = "TREND",
    market_type: MarketType = MarketType.FUTURES,
    won: bool = True,
) -> HistoricalOutcome:
    opened_at = BASE_TIME + timedelta(hours=index * 2)
    r_multiple = 2.0 if won else -1.0
    return HistoricalOutcome(
        setup_id=f"setup-{market_type.value.lower()}-{split.value.lower()}-{index}",
        dataset_id=dataset_id,
        split=split,
        market_type=market_type,
        strategy=strategy,
        symbol=symbol,
        regime=regime,
        score_band="75-84",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        net_return=r_multiple / 100,
        r_multiple=r_multiple,
        maximum_favorable_excursion_r=max(r_multiple, 0.25),
        maximum_adverse_excursion_r=-0.5,
        won=won,
    )


def test_final_test_split_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="allow_final_test=True"):
        HistoricalEdgeQueryRequest(
            market_type=MarketType.FUTURES,
            strategy="trend_pullback",
            split=DatasetSplit.TEST,
        )


def test_query_filters_exact_segment_and_orders_chronologically(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    write_historical_outcomes_sqlite(
        database,
        (
            _outcome(3),
            _outcome(1),
            _outcome(2, strategy="breakout_retest"),
            _outcome(0, split=DatasetSplit.VALIDATION),
            _outcome(4, market_type=MarketType.SPOT, dataset_id="spot-v1"),
        ),
    )
    request = HistoricalEdgeQueryRequest(
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
    )

    outcomes = query_historical_outcomes_sqlite(database, request)

    assert tuple(item.setup_id for item in outcomes) == (
        "setup-futures-train-1",
        "setup-futures-train-3",
    )


def test_dataset_loader_preserves_market_segmentation(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    write_historical_dataset_sqlite(database, _metadata())
    write_historical_dataset_sqlite(
        database,
        _metadata("spot-v1", market_type=MarketType.SPOT),
    )

    futures = load_historical_datasets_sqlite(
        database,
        market_type=MarketType.FUTURES,
    )

    assert tuple(item.dataset_id for item in futures) == ("futures-v1",)


def test_query_builds_and_persists_reproducible_report(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    metadata = _metadata()
    write_historical_dataset_sqlite(database, metadata)
    write_historical_outcomes_sqlite(
        database,
        (_outcome(0, won=True), _outcome(1, won=False)),
    )
    request = HistoricalEdgeQueryRequest(
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=2, established_samples=3),
    )

    first = run_historical_edge_query(database, request, persist_report=True)
    second = run_historical_edge_query(database, request)
    stored = load_historical_edge_report_sqlite(database, first.metrics.result_hash)

    assert first.metrics.sample_count == 2
    assert first.metrics.evidence_quality is EvidenceQuality.PRELIMINARY
    assert first.metrics.result_hash == second.metrics.result_hash
    assert first.report_payload == second.report_payload
    assert stored == first.report_payload


def test_missing_dataset_metadata_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    write_historical_outcomes_sqlite(database, (_outcome(0),))
    request = HistoricalEdgeQueryRequest(
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=1, established_samples=2),
    )

    with pytest.raises(ValueError, match="missing persisted dataset metadata"):
        run_historical_edge_query(database, request)


def test_zero_sample_query_remains_explicitly_insufficient(tmp_path: Path) -> None:
    request = HistoricalEdgeQueryRequest(
        market_type=MarketType.SPOT,
        strategy="breakout_retest",
        split=DatasetSplit.VALIDATION,
    )

    result = run_historical_edge_query(tmp_path / "missing.sqlite3", request)

    assert result.outcomes == ()
    assert result.datasets == ()
    assert result.metrics.sample_count == 0
    assert result.metrics.evidence_quality is EvidenceQuality.INSUFFICIENT
    assert result.metrics.insufficient_reason == (
        "requires at least 20 completed samples; found 0"
    )


def test_final_test_query_is_allowed_only_with_explicit_flag(tmp_path: Path) -> None:
    database = tmp_path / "historical-edge.sqlite3"
    write_historical_dataset_sqlite(database, _metadata())
    write_historical_outcomes_sqlite(
        database,
        (_outcome(0, split=DatasetSplit.TEST),),
    )
    request = HistoricalEdgeQueryRequest(
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TEST,
        thresholds=EvidenceThresholds(preliminary_samples=1, established_samples=2),
        allow_final_test=True,
    )

    result = run_historical_edge_query(database, request)

    assert result.metrics.sample_count == 1
    assert result.metrics.split is DatasetSplit.TEST
