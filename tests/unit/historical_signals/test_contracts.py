"""Tests for immutable historical signal campaign contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.historical_signals import (
    HistoricalSignalCampaignRecord,
    derive_historical_signal_record_id,
    validate_historical_signal_record_sequence,
)

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _record(
    *,
    symbol: str = "BTC/USDT",
    split: HistoricalSignalSplit = HistoricalSignalSplit.TRAIN,
    second: int = 1,
) -> HistoricalSignalCampaignRecord:
    decision_time = datetime(2026, 6, 1, 0, 0, second, tzinfo=UTC)
    record_id = derive_historical_signal_record_id(
        campaign_id="pilot",
        symbol=symbol,
        split=split,
        decision_time=decision_time,
        source_dataset_hash=_HASH_A,
        assumptions_hash=_HASH_B,
    )
    return HistoricalSignalCampaignRecord(
        signal_record_id=record_id,
        campaign_id="pilot",
        dataset_campaign_plan_id="pilot-plan",
        dataset_campaign_execution_id="pilot-execution",
        symbol=symbol,
        timeframe="1m",
        split=split,
        decision_time=decision_time,
        parent_dataset_id="pilot-parent",
        parent_dataset_hash=_HASH_A,
        source_dataset_id=f"pilot-{split.value}",
        source_dataset_hash=_HASH_A,
        assumptions_hash=_HASH_B,
        required_context_candles=40,
        accepted=False,
        analysis={"decision": "NO_TRADE", "nested": {"b": 2, "a": 1}},
        unavailable_optional_data=("funding_rate", "open_interest"),
    )


def test_record_id_is_deterministic() -> None:
    first = _record()
    second = _record()

    assert first.signal_record_id == second.signal_record_id
    assert first.to_payload() == second.to_payload()


def test_analysis_mapping_order_does_not_change_payload() -> None:
    first = _record()
    second = replace(
        first,
        analysis={"nested": {"a": 1, "b": 2}, "decision": "NO_TRADE"},
    )

    assert first.to_payload() == second.to_payload()


def test_sequence_uses_symbol_then_split_then_timestamp() -> None:
    records = (
        _record(split=HistoricalSignalSplit.TRAIN, second=1),
        _record(split=HistoricalSignalSplit.VALIDATION, second=1),
        _record(split=HistoricalSignalSplit.FINAL_TEST, second=1),
        _record(symbol="ETH/USDT", split=HistoricalSignalSplit.TRAIN, second=1),
    )

    validate_historical_signal_record_sequence(
        records,
        symbol_order=("BTC/USDT", "ETH/USDT"),
    )


def test_duplicate_signal_identity_is_rejected() -> None:
    record = _record()

    with pytest.raises(ValueError, match="duplicate signal identities"):
        validate_historical_signal_record_sequence(
            (record, record),
            symbol_order=("BTC/USDT",),
        )


def test_future_split_before_train_is_rejected() -> None:
    with pytest.raises(ValueError, match="frozen symbol, split"):
        validate_historical_signal_record_sequence(
            (
                _record(split=HistoricalSignalSplit.FINAL_TEST),
                _record(split=HistoricalSignalSplit.TRAIN),
            ),
            symbol_order=("BTC/USDT",),
        )
