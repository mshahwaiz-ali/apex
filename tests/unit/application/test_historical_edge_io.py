from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    EvidenceThresholds,
    HistoricalOutcome,
    MarketType,
    aggregate_historical_edge,
    build_dataset_metadata,
)
from apex.application.historical_edge_io import (
    dumps_historical_edge_report,
    historical_edge_report_payload,
    list_historical_edge_report_metadata_sqlite,
    load_historical_edge_report_sqlite,
    write_historical_dataset_sqlite,
    write_historical_edge_report,
    write_historical_edge_report_sqlite,
    write_historical_outcomes_sqlite,
)

BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def _metadata(market_type: MarketType = MarketType.FUTURES):
    dataset_id = f"{market_type.value.lower()}-dataset"
    return build_dataset_metadata(
        dataset_id=dataset_id,
        market_type=market_type,
        symbols=("BTCUSDT",),
        timeframes=("1h",),
        source="fixture",
        first_observation_at=BASE_TIME,
        last_observation_at=BASE_TIME + timedelta(days=60),
        observation_count=100,
        partitions=(
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
        ),
        content_payload={"market_type": market_type.value, "rows": [1, 2, 3]},
    )


def _outcome(index: int, *, market_type: MarketType = MarketType.FUTURES) -> HistoricalOutcome:
    opened_at = BASE_TIME + timedelta(hours=index * 2)
    won = index % 2 == 0
    return HistoricalOutcome(
        setup_id=f"{market_type.value.lower()}-{index}",
        dataset_id=f"{market_type.value.lower()}-dataset",
        split=DatasetSplit.TRAIN,
        market_type=market_type,
        strategy="trend_pullback",
        symbol="BTCUSDT",
        regime="TREND",
        score_band="75-84",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        net_return=0.02 if won else -0.01,
        r_multiple=2.0 if won else -1.0,
        maximum_favorable_excursion_r=2.5 if won else 0.25,
        maximum_adverse_excursion_r=-0.5,
        won=won,
    )


def _metrics():
    return aggregate_historical_edge(
        tuple(_outcome(index) for index in range(3)),
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=2, established_samples=3),
    )


def test_report_serialization_is_deterministic() -> None:
    metrics = _metrics()
    metadata = _metadata()

    first = dumps_historical_edge_report(metrics, dataset_metadata=(metadata,))
    second = dumps_historical_edge_report(metrics, dataset_metadata=(metadata,))

    assert first == second
    assert '"quality": "ESTABLISHED"' in first
    assert metadata.content_hash in first


def test_report_requires_all_referenced_dataset_metadata() -> None:
    with pytest.raises(ValueError, match="missing dataset metadata"):
        historical_edge_report_payload(_metrics())


def test_json_report_refuses_overwrite_without_force(tmp_path: Path) -> None:
    path = tmp_path / "edge.json"
    metrics = _metrics()
    metadata = _metadata()

    write_historical_edge_report(path, metrics, dataset_metadata=(metadata,))

    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_historical_edge_report(path, metrics, dataset_metadata=(metadata,))

    write_historical_edge_report(
        path,
        metrics,
        dataset_metadata=(metadata,),
        force=True,
    )


def test_sqlite_round_trip_and_idempotent_upserts(tmp_path: Path) -> None:
    path = tmp_path / "historical-edge.sqlite3"
    metadata = _metadata()
    outcomes = tuple(_outcome(index) for index in range(3))
    metrics = _metrics()

    write_historical_dataset_sqlite(path, metadata)
    assert write_historical_outcomes_sqlite(path, outcomes) == 3
    assert write_historical_outcomes_sqlite(path, outcomes) == 3
    write_historical_edge_report_sqlite(
        path,
        metrics,
        dataset_metadata=(metadata,),
    )
    write_historical_edge_report_sqlite(
        path,
        metrics,
        dataset_metadata=(metadata,),
    )

    loaded = load_historical_edge_report_sqlite(path, metrics.result_hash)
    listed = list_historical_edge_report_metadata_sqlite(path)

    assert loaded is not None
    assert loaded["result_hash"] == metrics.result_hash
    assert loaded["evidence"]["sample_count"] == 3
    assert len(listed) == 1
    assert listed[0]["market_type"] == "FUTURES"
    assert listed[0]["evidence_quality"] == "ESTABLISHED"


def test_futures_and_spot_reports_remain_separate(tmp_path: Path) -> None:
    path = tmp_path / "historical-edge.sqlite3"
    futures_metadata = _metadata(MarketType.FUTURES)
    spot_metadata = _metadata(MarketType.SPOT)
    futures_metrics = _metrics()
    spot_outcomes = tuple(_outcome(index, market_type=MarketType.SPOT) for index in range(2))
    spot_metrics = aggregate_historical_edge(
        spot_outcomes,
        market_type=MarketType.SPOT,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=2, established_samples=3),
    )

    write_historical_edge_report_sqlite(
        path,
        futures_metrics,
        dataset_metadata=(futures_metadata,),
    )
    write_historical_edge_report_sqlite(
        path,
        spot_metrics,
        dataset_metadata=(spot_metadata,),
    )

    listed = list_historical_edge_report_metadata_sqlite(path)

    assert tuple(item["market_type"] for item in listed) == ("FUTURES", "SPOT")
    assert listed[0]["result_hash"] != listed[1]["result_hash"]
