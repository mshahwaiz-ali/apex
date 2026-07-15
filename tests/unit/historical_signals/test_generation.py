"""Tests for aligned replay conversion into persisted campaign records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.historical_signal_generation import HistoricalSignalRecord
from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    HistoricalSourceDataset,
)
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayBoundaries,
    HistoricalSignalSplit,
)
from apex.domain.models import Candle
from apex.historical_signals.generation import (
    _convert_record,
    derive_historical_signal_assumptions_hash,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _candle(timeframe: str, minutes: int) -> Candle:
    open_time = datetime(2026, 6, 1, 0, minutes, tzinfo=UTC)
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def _inputs() -> HistoricalSignalCampaignInputs:
    series_1m = HistoricalCandleSeries(
        symbol="BTC/USDT",
        timeframe="1m",
        candles=(_candle("1m", 0),),
    )
    series_5m = HistoricalCandleSeries(
        symbol="BTC/USDT",
        timeframe="5m",
        candles=(_candle("5m", 0),),
    )
    return HistoricalSignalCampaignInputs(
        campaign_id="pilot",
        provider="fixture",
        plan_path="plan.json",
        execution_manifest_path="execution.json",
        symbols=("BTC/USDT",),
        timeframes=("1m", "5m"),
        boundaries=HistoricalReplayBoundaries(
            analysis_start=datetime(2026, 6, 1, tzinfo=UTC),
            train_end=datetime(2026, 6, 2, tzinfo=UTC),
            validation_end=datetime(2026, 6, 3, tzinfo=UTC),
            analysis_end=datetime(2026, 6, 4, tzinfo=UTC),
        ),
        store=HistoricalCandleStore((series_1m, series_5m)),
        source_datasets=(
            HistoricalSourceDataset(
                acquisition_order=1,
                symbol="BTC/USDT",
                timeframe="1m",
                dataset_id="pilot-btc-1m",
                dataset_path="btc-1m.json",
                content_hash=_HASH_A,
                candle_count=1,
            ),
            HistoricalSourceDataset(
                acquisition_order=2,
                symbol="BTC/USDT",
                timeframe="5m",
                dataset_id="pilot-btc-5m",
                dataset_path="btc-5m.json",
                content_hash=_HASH_B,
                candle_count=1,
            ),
        ),
    )


def _replay_record(split: HistoricalSignalSplit) -> HistoricalSignalRecord:
    return HistoricalSignalRecord(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(2026, 6, 1, 0, 1, tzinfo=UTC),
        split=split,
        accepted=False,
        payload={"decision": "NO_TRADE", "rejection_codes": ["minimum_score"]},
        source_dataset_hashes=(_HASH_A, _HASH_B),
        configuration_id=None,
        feature_snapshot_references={},
        unavailable_optional_data=("funding_rate", "open_interest"),
    )


def test_assumptions_hash_is_mapping_order_independent() -> None:
    first = derive_historical_signal_assumptions_hash(
        {"candle_limit": 200, "routing": {"b": 2, "a": 1}}
    )
    second = derive_historical_signal_assumptions_hash(
        {"routing": {"a": 1, "b": 2}, "candle_limit": 200}
    )

    assert first == second


def test_conversion_preserves_exact_multitimeframe_bindings() -> None:
    record = _convert_record(
        record=_replay_record(HistoricalSignalSplit.TRAIN),
        inputs=_inputs(),
        dataset_campaign_plan_id="aligned-plan-id",
        dataset_campaign_execution_id="aligned-execution-id",
        parent_dataset_hash="c" * 64,
        assumptions_hash="d" * 64,
        required_context_candles=40,
    )

    assert record.timeframe == "1m"
    assert tuple(item.timeframe for item in record.source_datasets) == ("1m", "5m")
    assert tuple(item.content_hash for item in record.source_datasets) == (_HASH_A, _HASH_B)
    assert record.analysis["rejection_codes"] == ["minimum_score"]


def test_final_test_split_does_not_change_train_record_identity() -> None:
    inputs = _inputs()
    arguments = {
        "inputs": inputs,
        "dataset_campaign_plan_id": "aligned-plan-id",
        "dataset_campaign_execution_id": "aligned-execution-id",
        "parent_dataset_hash": "c" * 64,
        "assumptions_hash": "d" * 64,
        "required_context_candles": 40,
    }
    first = _convert_record(
        record=_replay_record(HistoricalSignalSplit.TRAIN),
        **arguments,
    )
    _convert_record(
        record=_replay_record(HistoricalSignalSplit.FINAL_TEST),
        **arguments,
    )
    second = _convert_record(
        record=_replay_record(HistoricalSignalSplit.TRAIN),
        **arguments,
    )

    assert first.signal_record_id == second.signal_record_id
