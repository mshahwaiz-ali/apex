"""Integration coverage for persisted shared-wallet historical futures replay."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.historical_signal_io import HistoricalSignalExecutionManifest
from apex.backtesting import (
    BacktestConfig,
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalFuturesCampaignRequest,
    HistoricalReplayBoundaries,
    HistoricalSignalCampaignInputs,
    HistoricalSourceDataset,
    SharedWalletConfig,
    execute_shared_historical_futures_campaign,
    write_shared_historical_futures_campaign,
)
from apex.backtesting.historical_futures_shared_io import hash_json
from apex.domain.models import Candle


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _records() -> tuple[dict[str, object], ...]:
    def record(minute: int) -> dict[str, object]:
        decision = datetime(2026, 1, 1, 0, minute, tzinfo=UTC).isoformat()
        analysis: dict[str, object] = {
            "symbol": "BTCUSDT",
            "decision": "LONG",
            "strategy": "trend_pullback",
            "entry_zone": {"preferred": 100.0},
            "stop_loss": 90.0,
            "take_profits": [{"price": 120.0}],
            "position_size": {
                "quantity": 1.0,
                "risk_amount": 10.0,
                "required_margin": 100.0,
            },
            "confidence_score": 80.0,
        }
        return {
            "symbol": "BTCUSDT",
            "split": "train",
            "decision_time": decision,
            "accepted": True,
            "failure_reason": None,
            "analysis": analysis,
        }

    return (record(1), record(2))


def _write_signal_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    records = _records()
    records_path = tmp_path / "signals.jsonl"
    records_path.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "signals-manifest.json"
    manifest = HistoricalSignalExecutionManifest(
        campaign_id="campaign-1",
        records_path=records_path.as_posix(),
        records_hash=_canonical_hash(records),
        configuration_hash="a" * 64,
        total_records=2,
        accepted_records=2,
        rejected_records=0,
        failed_records=0,
        split_counts=(("train", 2),),
        source_datasets=({"content_hash": "b" * 64},),
    )
    manifest_path.write_text(
        json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records_path, manifest_path


def _inputs(tmp_path: Path) -> HistoricalSignalCampaignInputs:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            symbol="BTCUSDT",
            timeframe="1m",
            open_time=start + timedelta(minutes=index),
            close_time=start + timedelta(minutes=index + 1),
            open=100.0,
            high=121.0 if index == 4 else 105.0,
            low=99.0,
            close=120.0 if index == 4 else 101.0,
            volume=1000.0,
            is_closed=True,
            source="fixture",
        )
        for index in range(8)
    )
    source = HistoricalSourceDataset(
        acquisition_order=1,
        symbol="BTCUSDT",
        timeframe="1m",
        dataset_id="dataset-1",
        dataset_path=(tmp_path / "dataset.json").as_posix(),
        content_hash="b" * 64,
        candle_count=len(candles),
    )
    return HistoricalSignalCampaignInputs(
        campaign_id="campaign-1",
        provider="fixture",
        plan_path=(tmp_path / "plan.json").as_posix(),
        execution_manifest_path=(tmp_path / "dataset-execution.json").as_posix(),
        symbols=("BTCUSDT",),
        timeframes=("1m",),
        boundaries=HistoricalReplayBoundaries(
            analysis_start=start,
            train_end=start + timedelta(minutes=3),
            validation_end=start + timedelta(minutes=6),
            analysis_end=start + timedelta(minutes=8),
        ),
        store=HistoricalCandleStore(
            (HistoricalCandleSeries(symbol="BTCUSDT", timeframe="1m", candles=candles),)
        ),
        source_datasets=(source,),
    )


def _request(tmp_path: Path, suffix: str) -> HistoricalFuturesCampaignRequest:
    records_path, manifest_path = _write_signal_artifacts(tmp_path)
    return HistoricalFuturesCampaignRequest(
        campaign_id="campaign-1",
        records_path=records_path,
        signal_manifest_path=manifest_path,
        result_path=tmp_path / f"result-{suffix}.json",
        execution_manifest_path=tmp_path / f"execution-{suffix}.json",
        starting_equity=1000.0,
        backtest_config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )


def test_persisted_shared_campaign_is_deterministic_and_non_overwriting(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    config = SharedWalletConfig(maximum_concurrent_positions=2)
    first_request = _request(tmp_path, "one")
    first = execute_shared_historical_futures_campaign(
        request=first_request,
        inputs=inputs,
        wallet_config=config,
    )
    first_manifest = write_shared_historical_futures_campaign(
        request=first_request,
        result=first,
    )

    result_payload = json.loads(first_request.result_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(
        first_request.execution_manifest_path.read_text(encoding="utf-8")
    )
    rejected = [item for item in result_payload["observations"] if item["status"] == "wallet_rejected"]

    assert first_request.result_path.is_file()
    assert first_request.execution_manifest_path.is_file()
    assert manifest_payload["result_hash"] == hash_json(result_payload)
    assert manifest_payload["trade_count"] == 1
    assert rejected[0]["rejection_codes"] == ["overlapping_symbol_position"]
    assert result_payload["ending_equity"] == result_payload["shared_wallet"]["ending_equity"]
    assert manifest_payload["wallet_configuration_hash"] == first.configuration_hash

    second_request = _request(tmp_path, "two")
    second = execute_shared_historical_futures_campaign(
        request=second_request,
        inputs=inputs,
        wallet_config=config,
    )
    second_manifest = write_shared_historical_futures_campaign(
        request=second_request,
        result=second,
    )

    assert first.to_payload() == second.to_payload()
    assert first_manifest.result_hash == second_manifest.result_hash
    assert first_manifest.wallet_configuration_hash == second_manifest.wallet_configuration_hash
    with pytest.raises(FileExistsError, match="overwrite"):
        write_shared_historical_futures_campaign(request=first_request, result=first)
