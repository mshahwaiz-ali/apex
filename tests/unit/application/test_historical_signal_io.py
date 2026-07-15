"""Tests for historical signal persistence and execution manifests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.application.historical_signal_generation import (
    HistoricalSignalGenerationResult,
    HistoricalSignalRecord,
    build_historical_signal_record,
)
from apex.application.historical_signal_io import (
    hash_configuration_files,
    hash_historical_signal_records,
    load_historical_signal_execution_manifest,
    load_historical_signal_record_payloads,
    write_historical_signal_generation,
)
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


def _record(
    *,
    minute: int,
    decision: str,
    failure_reason: str | None = None,
) -> HistoricalSignalRecord:
    payload: dict[str, object] = {
        "symbol": "BTC/USDT",
        "decision": decision,
        "configuration_id": "config-1",
        "timeframe_data_quality": {},
    }
    record = build_historical_signal_record(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(
            2026,
            6,
            1,
            0,
            minute,
            tzinfo=UTC,
        ),
        split=HistoricalSignalSplit.TRAIN,
        payload=payload,
        source_dataset_hashes=("a" * 64,),
    )
    if failure_reason is None:
        return record
    return record.__class__(
        campaign_id=record.campaign_id,
        symbol=record.symbol,
        decision_time=record.decision_time,
        split=record.split,
        accepted=False,
        payload=record.payload,
        source_dataset_hashes=record.source_dataset_hashes,
        configuration_id=record.configuration_id,
        feature_snapshot_references=(record.feature_snapshot_references),
        unavailable_optional_data=(record.unavailable_optional_data),
        failure_reason=failure_reason,
    )


def _inputs(tmp_path: Path) -> HistoricalSignalCampaignInputs:
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=datetime(
            2026,
            6,
            1,
            tzinfo=UTC,
        ),
        close_time=datetime(
            2026,
            6,
            1,
            0,
            0,
            59,
            999000,
            tzinfo=UTC,
        ),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=10.0,
        is_closed=True,
        source="binance",
    )
    return HistoricalSignalCampaignInputs(
        campaign_id="pilot",
        provider="binance",
        plan_path=(tmp_path / "plan.json").as_posix(),
        execution_manifest_path=(tmp_path / "dataset-execution.json").as_posix(),
        symbols=("BTC/USDT",),
        timeframes=("1m",),
        boundaries=HistoricalReplayBoundaries(
            analysis_start=datetime(
                2026,
                6,
                1,
                tzinfo=UTC,
            ),
            train_end=datetime(
                2026,
                6,
                2,
                tzinfo=UTC,
            ),
            validation_end=datetime(
                2026,
                6,
                3,
                tzinfo=UTC,
            ),
            analysis_end=datetime(
                2026,
                6,
                4,
                tzinfo=UTC,
            ),
        ),
        store=HistoricalCandleStore(
            (
                HistoricalCandleSeries(
                    symbol="BTC/USDT",
                    timeframe="1m",
                    candles=(candle,),
                ),
            )
        ),
        source_datasets=(
            HistoricalSourceDataset(
                acquisition_order=1,
                symbol="BTC/USDT",
                timeframe="1m",
                dataset_id="btc-1m",
                dataset_path="btc.json",
                content_hash="a" * 64,
                candle_count=1,
            ),
        ),
    )


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "risk.yaml"
    path.write_text(
        "risk_per_trade_pct: 1.0\n",
        encoding="utf-8",
    )
    return path


def test_hashes_configuration_content_deterministically(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)

    first = hash_configuration_files((config,))
    second = hash_configuration_files((config,))

    assert first == second
    assert len(first) == 64


def test_record_hash_changes_with_record_content() -> None:
    first = (_record(minute=1, decision="LONG"),)
    second = (_record(minute=1, decision="NO_TRADE"),)

    assert hash_historical_signal_records(first) != hash_historical_signal_records(second)


def test_writes_and_reloads_records_and_manifest(
    tmp_path: Path,
) -> None:
    result = HistoricalSignalGenerationResult(
        campaign_id="pilot",
        records=(
            _record(minute=1, decision="LONG"),
            _record(minute=2, decision="NO_TRADE"),
        ),
    )
    records_path = tmp_path / "signals.jsonl"
    manifest_path = tmp_path / "execution.json"

    manifest = write_historical_signal_generation(
        inputs=_inputs(tmp_path),
        result=result,
        records_path=records_path,
        execution_manifest_path=manifest_path,
        configuration_paths=(_config(tmp_path),),
    )

    assert manifest.total_records == 2
    assert manifest.accepted_records == 1
    assert manifest.rejected_records == 1
    assert manifest.failed_records == 0
    assert manifest.split_counts == (("train", 2),)
    assert len(load_historical_signal_record_payloads(records_path)) == 2
    assert load_historical_signal_execution_manifest(manifest_path) == manifest


def test_refuses_to_overwrite_existing_artifacts(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "signals.jsonl"
    records_path.write_text(
        "existing\n",
        encoding="utf-8",
    )
    result = HistoricalSignalGenerationResult(
        campaign_id="pilot",
        records=(_record(minute=1, decision="NO_TRADE"),),
    )

    with pytest.raises(
        FileExistsError,
        match="refuses to overwrite",
    ):
        write_historical_signal_generation(
            inputs=_inputs(tmp_path),
            result=result,
            records_path=records_path,
            execution_manifest_path=(tmp_path / "execution.json"),
            configuration_paths=(_config(tmp_path),),
        )


def test_cleans_records_when_manifest_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = HistoricalSignalGenerationResult(
        campaign_id="pilot",
        records=(_record(minute=1, decision="NO_TRADE"),),
    )
    records_path = tmp_path / "signals.jsonl"
    manifest_path = tmp_path / "execution.json"

    original_write_text = Path.write_text

    def failing_write_text(
        self: Path,
        data: str,
        *,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self.name == "execution.json.tmp":
            raise OSError("simulated manifest failure")
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(
        Path,
        "write_text",
        failing_write_text,
    )

    with pytest.raises(
        OSError,
        match="simulated manifest failure",
    ):
        write_historical_signal_generation(
            inputs=_inputs(tmp_path),
            result=result,
            records_path=records_path,
            execution_manifest_path=manifest_path,
            configuration_paths=(_config(tmp_path),),
        )

    assert not records_path.exists()
    assert not manifest_path.exists()
    assert not (tmp_path / "execution.json.tmp").exists()


def test_rejects_tampered_reloaded_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signals.jsonl"
    path.write_text(
        json.dumps({"accepted": True}) + "\n",
        encoding="utf-8",
    )

    payloads = load_historical_signal_record_payloads(path)

    assert payloads == ({"accepted": True},)
