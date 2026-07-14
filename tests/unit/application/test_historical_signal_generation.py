"""Tests for chronological historical signal generation."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.historical_signal_generation import (
    HistoricalSignalGenerationResult,
    build_historical_signal_record,
)
from apex.backtesting.historical_signal_replay import (
    HistoricalSignalSplit,
)


def _quality_payload() -> dict[str, object]:
    return {
        "1m": {
            "last_closed_at": ("2026-06-01T00:00:59.999000+00:00"),
            "ticker_price": None,
            "spread_percentage": None,
            "order_book_spread_percentage": None,
            "order_book_depth_imbalance": None,
            "exchange_tick_size": None,
            "exchange_step_size": None,
            "exchange_min_notional": None,
            "nearest_long_liquidation_distance_pct": None,
            "nearest_short_liquidation_distance_pct": None,
        }
    }


def test_builds_accepted_historical_signal_record() -> None:
    decision_time = datetime(
        2026,
        6,
        1,
        0,
        0,
        59,
        999000,
        tzinfo=UTC,
    )
    record = build_historical_signal_record(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=decision_time,
        split=HistoricalSignalSplit.TRAIN,
        payload={
            "symbol": "BTC/USDT",
            "decision": "LONG",
            "strategy": "trend_pullback",
            "configuration_id": "risk-config-1",
            "timeframe_data_quality": _quality_payload(),
        },
        source_dataset_hashes=("a" * 64,),
    )

    assert record.accepted is True
    assert record.configuration_id == "risk-config-1"
    assert record.feature_snapshot_references == {
        "1m": ("BTC/USDT:1m:2026-06-01T00:00:59.999000+00:00")
    }
    assert "ticker" in record.unavailable_optional_data
    assert "order_book" in record.unavailable_optional_data
    assert "funding_rate" in record.unavailable_optional_data


def test_builds_rejected_historical_signal_record() -> None:
    record = build_historical_signal_record(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(
            2026,
            6,
            1,
            0,
            1,
            tzinfo=UTC,
        ),
        split=HistoricalSignalSplit.VALIDATION,
        payload={
            "symbol": "BTC/USDT",
            "decision": "NO_TRADE",
            "rejection_codes": ["minimum_score"],
            "reasons": ["candidate score is too low"],
            "configuration_id": "risk-config-1",
            "timeframe_data_quality": _quality_payload(),
        },
        source_dataset_hashes=("b" * 64,),
    )

    assert record.accepted is False
    assert record.payload["rejection_codes"] == ["minimum_score"]


def test_generation_result_requires_chronological_records() -> None:
    later = build_historical_signal_record(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(
            2026,
            6,
            1,
            0,
            2,
            tzinfo=UTC,
        ),
        split=HistoricalSignalSplit.TRAIN,
        payload={
            "decision": "NO_TRADE",
            "timeframe_data_quality": {},
        },
        source_dataset_hashes=("a" * 64,),
    )
    earlier = build_historical_signal_record(
        campaign_id="pilot",
        symbol="BTC/USDT",
        decision_time=datetime(
            2026,
            6,
            1,
            0,
            1,
            tzinfo=UTC,
        ),
        split=HistoricalSignalSplit.TRAIN,
        payload={
            "decision": "NO_TRADE",
            "timeframe_data_quality": {},
        },
        source_dataset_hashes=("a" * 64,),
    )

    try:
        HistoricalSignalGenerationResult(
            campaign_id="pilot",
            records=(later, earlier),
        )
    except ValueError as exc:
        assert "chronological" in str(exc)
    else:
        raise AssertionError("out-of-order records must be rejected")


def test_record_payload_is_deterministic() -> None:
    arguments = {
        "campaign_id": "pilot",
        "symbol": "BTC/USDT",
        "decision_time": datetime(
            2026,
            6,
            1,
            0,
            1,
            tzinfo=UTC,
        ),
        "split": HistoricalSignalSplit.FINAL_TEST,
        "payload": {
            "decision": "NO_TRADE",
            "configuration_id": "config-1",
            "timeframe_data_quality": _quality_payload(),
        },
        "source_dataset_hashes": ("c" * 64,),
    }

    first = build_historical_signal_record(**arguments)
    second = build_historical_signal_record(**arguments)

    assert first == second
    assert first.to_payload() == second.to_payload()
