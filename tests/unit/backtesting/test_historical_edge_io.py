"""Tests for historical edge JSON and SQLite persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    SimulatedTrade,
    build_historical_edge_profile,
)
from apex.backtesting.historical_edge_io import (
    HISTORICAL_EDGE_REPORT_SCHEMA_VERSION,
    build_historical_edge_report,
    list_historical_edge_report_metadata_sqlite,
    load_historical_edge_report,
    load_historical_edge_report_sqlite,
    write_historical_edge_report,
    write_historical_edge_report_sqlite,
)
from apex.strategies import StrategyType, TradeDirection


def _trade(index: int, realized_r: float) -> SimulatedTrade:
    generated_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5)
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=75.0,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET if realized_r > 0.0 else BacktestOutcome.STOP,
        exit_time=generated_at + timedelta(minutes=15),
        exit_price=102.0 if realized_r > 0.0 else 99.0,
        gross_pnl=realized_r + 0.05,
        fees=0.05,
        net_pnl=realized_r,
        realized_r_multiple=realized_r,
        holding_candles=3,
        metadata={"active_risk_mode": "STANDARD"},
    )


def _report() -> dict[str, object]:
    profile = build_historical_edge_profile(
        (_trade(0, 2.0), _trade(1, -1.0)),
        dimensions={"strategy": "trend_pullback", "risk_mode": "STANDARD"},
    )
    return build_historical_edge_report(
        (profile,),
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        source_type="backtest_campaign",
        source_id="campaign-fixture",
    )


def test_report_identity_is_deterministic_and_generation_time_is_audit_only() -> None:
    profile = build_historical_edge_profile((_trade(0, 1.0),))
    first = build_historical_edge_report(
        (profile,),
        generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        source_type="backtest",
        source_id="run-fixture",
    )
    second = build_historical_edge_report(
        (profile,),
        generated_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        source_type="backtest",
        source_id="run-fixture",
    )

    assert first["schema_version"] == HISTORICAL_EDGE_REPORT_SCHEMA_VERSION
    assert first["report_id"] == second["report_id"]
    assert first["generated_at"] != second["generated_at"]
    assert first["profile_count"] == 1


def test_json_report_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    path = tmp_path / "reports" / "historical-edge.json"
    payload = _report()

    write_historical_edge_report(path, payload)

    assert load_historical_edge_report(path) == payload
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_historical_edge_report(path, payload)

    replacement = dict(payload)
    replacement["generated_at"] = "2026-07-15T12:00:00+00:00"
    write_historical_edge_report(path, replacement, force=True)
    assert load_historical_edge_report(path)["generated_at"] == replacement["generated_at"]


def test_sqlite_round_trip_upsert_and_metadata_listing(tmp_path: Path) -> None:
    path = tmp_path / "historical-edge.sqlite3"
    payload = _report()
    report_id = str(payload["report_id"])

    write_historical_edge_report_sqlite(path, payload)
    assert load_historical_edge_report_sqlite(path, report_id) == payload

    replacement = dict(payload)
    replacement["generated_at"] = "2026-07-15T12:00:00+00:00"
    write_historical_edge_report_sqlite(path, replacement)

    loaded = load_historical_edge_report_sqlite(path, report_id)
    assert loaded is not None
    assert loaded["generated_at"] == replacement["generated_at"]
    assert list_historical_edge_report_metadata_sqlite(path) == (
        {
            "report_id": report_id,
            "schema_version": 1,
            "generated_at": replacement["generated_at"],
            "source_type": "backtest_campaign",
            "source_id": "campaign-fixture",
            "profile_count": 1,
        },
    )


def test_missing_storage_and_invalid_limits_are_handled(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"

    assert load_historical_edge_report_sqlite(path, "missing-report") is None
    assert list_historical_edge_report_metadata_sqlite(path) == ()
    with pytest.raises(ValueError, match="cannot be empty"):
        load_historical_edge_report_sqlite(path, "")
    with pytest.raises(ValueError, match="must be positive"):
        list_historical_edge_report_metadata_sqlite(path, limit=0)


def test_report_validation_rejects_inconsistent_profile_count(tmp_path: Path) -> None:
    payload = _report()
    payload["profile_count"] = 2

    with pytest.raises(ValueError, match="profile count must match"):
        write_historical_edge_report(tmp_path / "bad.json", payload)
    with pytest.raises(ValueError, match="profile count must match"):
        write_historical_edge_report_sqlite(tmp_path / "bad.sqlite3", payload)


def test_report_builder_requires_aware_time_and_source_identity() -> None:
    profile = build_historical_edge_profile((_trade(0, 1.0),))

    with pytest.raises(ValueError, match="timezone-aware"):
        build_historical_edge_report(
            (profile,),
            generated_at=datetime(2026, 7, 14, 12, 0),
            source_type="backtest",
            source_id="run-fixture",
        )
    with pytest.raises(ValueError, match="source type and source id"):
        build_historical_edge_report(
            (profile,),
            generated_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            source_type="",
            source_id="run-fixture",
        )
