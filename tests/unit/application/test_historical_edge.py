from datetime import UTC, datetime, timedelta

import pytest

from apex.application.historical_edge import (
    DatasetPartition,
    DatasetSplit,
    EvidenceQuality,
    EvidenceThresholds,
    HistoricalOutcome,
    MarketType,
    aggregate_by_setup,
    aggregate_historical_edge,
    build_dataset_metadata,
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


def _outcome(
    index: int,
    *,
    market_type: MarketType = MarketType.FUTURES,
    split: DatasetSplit = DatasetSplit.TRAIN,
    strategy: str = "trend_pullback",
    symbol: str = "BTCUSDT",
    won: bool = True,
    r_multiple: float | None = None,
) -> HistoricalOutcome:
    opened_at = BASE_TIME + timedelta(hours=index * 2)
    resolved_r = r_multiple if r_multiple is not None else (2.0 if won else -1.0)
    return HistoricalOutcome(
        setup_id=f"setup-{index}",
        dataset_id=f"{market_type.value.lower()}-dataset",
        split=split,
        market_type=market_type,
        strategy=strategy,
        symbol=symbol,
        regime="TREND",
        score_band="75-84",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        net_return=resolved_r / 100,
        r_multiple=resolved_r,
        maximum_favorable_excursion_r=max(resolved_r, 0.25),
        maximum_adverse_excursion_r=-0.5,
        won=won,
    )


def test_dataset_metadata_is_canonical_and_hash_is_reproducible() -> None:
    first = build_dataset_metadata(
        dataset_id="futures-v1",
        market_type=MarketType.FUTURES,
        symbols=("ETHUSDT", "BTCUSDT", "BTCUSDT"),
        timeframes=("4h", "1h", "4h"),
        source="fixture",
        first_observation_at=BASE_TIME,
        last_observation_at=BASE_TIME + timedelta(days=60),
        observation_count=100,
        partitions=tuple(reversed(_partitions())),
        content_payload={"candles": [1, 2, 3]},
    )
    second = build_dataset_metadata(
        dataset_id="futures-v1",
        market_type=MarketType.FUTURES,
        symbols=("BTCUSDT", "ETHUSDT"),
        timeframes=("1h", "4h"),
        source="fixture",
        first_observation_at=BASE_TIME,
        last_observation_at=BASE_TIME + timedelta(days=60),
        observation_count=100,
        partitions=_partitions(),
        content_payload={"candles": [1, 2, 3]},
    )

    assert first.symbols == ("BTCUSDT", "ETHUSDT")
    assert first.timeframes == ("1h", "4h")
    assert tuple(item.split for item in first.partitions) == tuple(DatasetSplit)
    assert first.content_hash == second.content_hash


def test_dataset_partitions_must_not_overlap() -> None:
    overlapping = (
        _partitions()[0],
        DatasetPartition(
            split=DatasetSplit.VALIDATION,
            start_at=BASE_TIME + timedelta(days=29),
            end_at=BASE_TIME + timedelta(days=45),
        ),
        _partitions()[2],
    )

    with pytest.raises(ValueError, match="must not overlap"):
        build_dataset_metadata(
            dataset_id="invalid",
            market_type=MarketType.SPOT,
            symbols=("BTCUSDT",),
            timeframes=("1d",),
            source="fixture",
            first_observation_at=BASE_TIME,
            last_observation_at=BASE_TIME + timedelta(days=60),
            observation_count=10,
            partitions=overlapping,
            content_payload=[],
        )


def test_low_sample_segment_is_explicitly_insufficient() -> None:
    outcomes = tuple(_outcome(index) for index in range(3))

    metrics = aggregate_historical_edge(
        outcomes,
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=5, established_samples=10),
    )

    assert metrics.sample_count == 3
    assert metrics.evidence_quality is EvidenceQuality.INSUFFICIENT
    assert metrics.insufficient_reason == "requires at least 5 completed samples; found 3"


def test_aggregation_calculates_setup_specific_metrics() -> None:
    outcomes = (
        _outcome(0, won=True, r_multiple=2.0),
        _outcome(1, won=False, r_multiple=-1.0),
        _outcome(2, won=True, r_multiple=1.0),
        _outcome(3, strategy="breakout_retest", won=True),
        _outcome(4, split=DatasetSplit.TEST, won=False),
        _outcome(5, market_type=MarketType.SPOT, won=True),
    )

    metrics = aggregate_historical_edge(
        outcomes,
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=2, established_samples=3),
    )

    assert metrics.sample_count == 3
    assert metrics.wins == 2
    assert metrics.losses == 1
    assert metrics.win_rate == pytest.approx(2 / 3)
    assert metrics.expectancy_r == pytest.approx(2 / 3)
    assert metrics.average_win_r == pytest.approx(1.5)
    assert metrics.average_loss_r == pytest.approx(-1.0)
    assert metrics.profit_factor == pytest.approx(3.0)
    assert metrics.evidence_quality is EvidenceQuality.ESTABLISHED
    assert metrics.dataset_ids == ("futures-dataset",)


def test_test_split_is_not_leaked_into_training_metrics() -> None:
    outcomes = (
        _outcome(0, split=DatasetSplit.TRAIN, won=False),
        _outcome(1, split=DatasetSplit.TEST, won=True, r_multiple=10.0),
    )

    metrics = aggregate_historical_edge(
        outcomes,
        market_type=MarketType.FUTURES,
        strategy="trend_pullback",
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=1, established_samples=2),
    )

    assert metrics.sample_count == 1
    assert metrics.expectancy_r == pytest.approx(-1.0)
    assert metrics.losses == 1


def test_futures_and_spot_are_segmented_by_setup() -> None:
    outcomes = (
        _outcome(0, market_type=MarketType.FUTURES),
        _outcome(1, market_type=MarketType.SPOT),
    )

    result = aggregate_by_setup(
        outcomes,
        split=DatasetSplit.TRAIN,
        thresholds=EvidenceThresholds(preliminary_samples=1, established_samples=2),
    )

    assert tuple(result) == (
        (MarketType.FUTURES, "trend_pullback"),
        (MarketType.SPOT, "trend_pullback"),
    )
    assert result[(MarketType.FUTURES, "trend_pullback")].dataset_ids == (
        "futures-dataset",
    )
    assert result[(MarketType.SPOT, "trend_pullback")].dataset_ids == ("spot-dataset",)
