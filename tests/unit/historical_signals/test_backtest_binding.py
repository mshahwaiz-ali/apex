"""Tests for schema-v2 historical signal backtest input binding."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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
from apex.historical_signals import (
    HistoricalSignalCampaignManifest,
    HistoricalSignalCampaignRecord,
    derive_historical_signal_campaign_id,
    hash_file_sha256,
    verify_historical_backtest_signal_inputs,
)
from apex.historical_signals.generation import _convert_record

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_ASSUMPTIONS_HASH = "d" * 64


def _candle(timeframe: str) -> Candle:
    opened = datetime(2026, 6, 1, tzinfo=UTC)
    return Candle(
        symbol="BTC/USDT",
        timeframe=timeframe,
        open_time=opened,
        close_time=opened + timedelta(minutes=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=10.0,
        is_closed=True,
        source="fixture",
    )


def _inputs() -> HistoricalSignalCampaignInputs:
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
        store=HistoricalCandleStore(
            (
                HistoricalCandleSeries(
                    symbol="BTC/USDT",
                    timeframe="1m",
                    candles=(_candle("1m"),),
                ),
                HistoricalCandleSeries(
                    symbol="BTC/USDT",
                    timeframe="5m",
                    candles=(_candle("5m"),),
                ),
            )
        ),
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


def _artifacts(tmp_path: Path) -> tuple[Path, Path, Path, str, str]:
    plan = tmp_path / "plan.json"
    execution = tmp_path / "execution.json"
    records = tmp_path / "signals.jsonl"
    plan.write_text('{"plan":1}\n', encoding="utf-8")
    execution.write_text('{"execution":1}\n', encoding="utf-8")
    return plan, execution, records, hash_file_sha256(plan), hash_file_sha256(execution)


def _record(*, plan_hash: str, execution_hash: str) -> HistoricalSignalCampaignRecord:
    replay = HistoricalSignalRecord(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(2026, 6, 1, 0, 1, tzinfo=UTC),
        split=HistoricalSignalSplit.TRAIN,
        accepted=False,
        payload={"decision": "NO_TRADE", "rejection_codes": ["minimum_score"]},
        source_dataset_hashes=(_HASH_A, _HASH_B),
        configuration_id=None,
        feature_snapshot_references={},
        unavailable_optional_data=(),
    )
    return _convert_record(
        record=replay,
        inputs=_inputs(),
        dataset_campaign_plan_id=f"aligned-plan-{plan_hash}",
        dataset_campaign_execution_id=f"aligned-execution-{execution_hash}",
        parent_dataset_hash=plan_hash,
        assumptions_hash=_ASSUMPTIONS_HASH,
        required_context_candles=40,
    )


def _manifest(
    *,
    records: Path,
    plan_hash: str,
    execution_hash: str,
    assumptions_hash: str = _ASSUMPTIONS_HASH,
) -> HistoricalSignalCampaignManifest:
    records_hash = "c" * 64
    signal_campaign_id = derive_historical_signal_campaign_id(
        campaign_id="pilot",
        dataset_campaign_plan_id=f"aligned-plan-{plan_hash}",
        dataset_campaign_execution_id=f"aligned-execution-{execution_hash}",
        assumptions_hash=assumptions_hash,
        records_content_hash=records_hash,
    )
    return HistoricalSignalCampaignManifest(
        signal_campaign_id=signal_campaign_id,
        campaign_id="pilot",
        dataset_campaign_plan_id=f"aligned-plan-{plan_hash}",
        dataset_campaign_execution_id=f"aligned-execution-{execution_hash}",
        assumptions_hash=assumptions_hash,
        records_path=records.as_posix(),
        records_content_hash=records_hash,
        record_count=1,
        symbol_order=("BTC/USDT",),
        split_order=(
            HistoricalSignalSplit.TRAIN,
            HistoricalSignalSplit.VALIDATION,
            HistoricalSignalSplit.FINAL_TEST,
        ),
        counts_by_symbol=(("BTC/USDT", 1),),
        counts_by_split=(
            (HistoricalSignalSplit.TRAIN, 1),
            (HistoricalSignalSplit.VALIDATION, 0),
            (HistoricalSignalSplit.FINAL_TEST, 0),
        ),
    )


def test_verified_schema_v2_backtest_binding_accepts_exact_artifacts(tmp_path: Path) -> None:
    plan, execution, records, plan_hash, execution_hash = _artifacts(tmp_path)
    record = _record(plan_hash=plan_hash, execution_hash=execution_hash)

    verify_historical_backtest_signal_inputs(
        campaign_inputs=_inputs(),
        manifest=_manifest(records=records, plan_hash=plan_hash, execution_hash=execution_hash),
        records=(record,),
        plan_path=plan,
        execution_manifest_path=execution,
        records_path=records,
    )


def test_schema_v2_backtest_binding_rejects_assumptions_drift(tmp_path: Path) -> None:
    plan, execution, records, plan_hash, execution_hash = _artifacts(tmp_path)
    record = _record(plan_hash=plan_hash, execution_hash=execution_hash)

    with pytest.raises(ValueError, match="assumptions drift"):
        verify_historical_backtest_signal_inputs(
            campaign_inputs=_inputs(),
            manifest=_manifest(
                records=records,
                plan_hash=plan_hash,
                execution_hash=execution_hash,
                assumptions_hash="e" * 64,
            ),
            records=(record,),
            plan_path=plan,
            execution_manifest_path=execution,
            records_path=records,
        )


def test_schema_v2_backtest_binding_rejects_execution_identity_drift(
    tmp_path: Path,
) -> None:
    plan, execution, records, plan_hash, execution_hash = _artifacts(tmp_path)
    manifest = _manifest(records=records, plan_hash=plan_hash, execution_hash=execution_hash)
    drifted_execution_id = f"aligned-execution-{'f' * 64}"

    with pytest.raises(ValueError, match="execution identity"):
        verify_historical_backtest_signal_inputs(
            campaign_inputs=_inputs(),
            manifest=replace(
                manifest,
                dataset_campaign_execution_id=drifted_execution_id,
                signal_campaign_id=derive_historical_signal_campaign_id(
                    campaign_id="pilot",
                    dataset_campaign_plan_id=manifest.dataset_campaign_plan_id,
                    dataset_campaign_execution_id=drifted_execution_id,
                    assumptions_hash=_ASSUMPTIONS_HASH,
                    records_content_hash=manifest.records_content_hash,
                ),
            ),
            records=(_record(plan_hash=plan_hash, execution_hash=execution_hash),),
            plan_path=plan,
            execution_manifest_path=execution,
            records_path=records,
        )
