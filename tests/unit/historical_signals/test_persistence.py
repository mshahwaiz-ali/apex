"""Tests for atomic historical signal campaign persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.historical_signals import (
    HistoricalSignalCampaignRecord,
    HistoricalSignalSourceDataset,
    derive_historical_signal_record_id,
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,
    persist_completed_historical_signal_campaign,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _record() -> HistoricalSignalCampaignRecord:
    decision_time = datetime(2026, 6, 1, 0, 0, 1, tzinfo=UTC)
    return HistoricalSignalCampaignRecord(
        signal_record_id=derive_historical_signal_record_id(
            campaign_id="pilot",
            symbol="BTC/USDT",
            split=HistoricalSignalSplit.TRAIN,
            decision_time=decision_time,
            source_dataset_hash=_HASH_A,
            assumptions_hash=_HASH_B,
        ),
        campaign_id="pilot",
        dataset_campaign_plan_id="pilot-plan",
        dataset_campaign_execution_id="pilot-execution",
        symbol="BTC/USDT",
        timeframe="1m",
        split=HistoricalSignalSplit.TRAIN,
        decision_time=decision_time,
        parent_dataset_id="pilot-parent",
        parent_dataset_hash=_HASH_A,
        source_dataset_id="pilot-train",
        source_dataset_hash=_HASH_A,
        source_datasets=(
            HistoricalSignalSourceDataset(
                timeframe="1m",
                dataset_id="pilot-train",
                content_hash=_HASH_A,
            ),
        ),
        assumptions_hash=_HASH_B,
        required_context_candles=40,
        accepted=False,
        analysis={"decision": "NO_TRADE"},
        unavailable_optional_data=("funding_rate",),
    )


def test_completed_campaign_round_trip(tmp_path: Path) -> None:
    records_path = tmp_path / "signals.jsonl"
    manifest_path = tmp_path / "signals.manifest.json"

    manifest = persist_completed_historical_signal_campaign(
        records_path=records_path,
        manifest_path=manifest_path,
        records=(_record(),),
        campaign_id="pilot",
        dataset_campaign_plan_id="pilot-plan",
        dataset_campaign_execution_id="pilot-execution",
        assumptions_hash=_HASH_B,
        symbol_order=("BTC/USDT",),
    )

    assert load_historical_signal_campaign_manifest(manifest_path) == manifest
    assert load_historical_signal_records(
        records_path,
        symbol_order=("BTC/USDT",),
        expected_content_hash=manifest.records_content_hash,
    ) == (_record(),)


def test_records_tampering_is_detected(tmp_path: Path) -> None:
    records_path = tmp_path / "signals.jsonl"
    manifest_path = tmp_path / "signals.manifest.json"
    manifest = persist_completed_historical_signal_campaign(
        records_path=records_path,
        manifest_path=manifest_path,
        records=(_record(),),
        campaign_id="pilot",
        dataset_campaign_plan_id="pilot-plan",
        dataset_campaign_execution_id="pilot-execution",
        assumptions_hash=_HASH_B,
        symbol_order=("BTC/USDT",),
    )
    records_path.write_text(
        records_path.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="content hash"):
        load_historical_signal_records(
            records_path,
            symbol_order=("BTC/USDT",),
            expected_content_hash=manifest.records_content_hash,
        )


def test_preexisting_artifact_is_rejected(tmp_path: Path) -> None:
    records_path = tmp_path / "signals.jsonl"
    records_path.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        persist_completed_historical_signal_campaign(
            records_path=records_path,
            manifest_path=tmp_path / "signals.manifest.json",
            records=(_record(),),
            campaign_id="pilot",
            dataset_campaign_plan_id="pilot-plan",
            dataset_campaign_execution_id="pilot-execution",
            assumptions_hash=_HASH_B,
            symbol_order=("BTC/USDT",),
        )


def test_manifest_tampering_is_detected(tmp_path: Path) -> None:
    records_path = tmp_path / "signals.jsonl"
    manifest_path = tmp_path / "signals.manifest.json"
    persist_completed_historical_signal_campaign(
        records_path=records_path,
        manifest_path=manifest_path,
        records=(_record(),),
        campaign_id="pilot",
        dataset_campaign_plan_id="pilot-plan",
        dataset_campaign_execution_id="pilot-execution",
        assumptions_hash=_HASH_B,
        symbol_order=("BTC/USDT",),
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["record_count"] = 2
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="counts do not match"):
        load_historical_signal_campaign_manifest(manifest_path)
