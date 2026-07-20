from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.application.analysis_records import (
    build_analysis_record,
    reconcile_pending_opportunities_sqlite,
    write_analysis_record_sqlite,
)


def _opportunity(
    identity: str,
    *,
    direction: str,
    preferred: float,
    stop: float,
    target: float,
) -> dict[str, object]:
    setup = {
        "candidate_id": f"candidate-{identity}",
        "direction": direction,
        "entry_status": "READY_NOW",
        "actionability_state": "EXECUTE_NOW",
        "setup_expiry_seconds": 3600,
        "entry": {
            "lower": preferred - 0.5,
            "upper": preferred + 0.5,
            "preferred": preferred,
        },
        "stop_loss": {"price": stop},
        "take_profits": [{"price": target}],
    }
    return {
        "opportunity_id": identity,
        "candidate_id": f"candidate-{identity}",
        "category": "current",
        "sequence_role": "primary",
        "direction": direction,
        "actionability_state": "EXECUTE_NOW",
        "methodology_verdict": {"status": "allowed"},
        "setup": setup,
    }


def _analysis(symbol: str, generated_at: str) -> dict[str, object]:
    opportunities = [
        _opportunity(
            "btc-long-current",
            direction="long",
            preferred=100.0,
            stop=95.0,
            target=110.0,
        ),
        _opportunity(
            "btc-short-follow-up",
            direction="short",
            preferred=120.0,
            stop=125.0,
            target=110.0,
        ),
    ]
    return {
        "symbol": symbol,
        "generated_at": generated_at,
        "configuration_id": "test-config",
        "opportunity_portfolio": {
            "opportunities": opportunities,
            "current_opportunities": opportunities[:1],
            "follow_up_opportunities": opportunities[1:],
        },
        # Legacy aliases must not create duplicate rows.
        "setup": opportunities[0]["setup"],
        "developing_setup": opportunities[1]["setup"],
    }


def _rows(path: Path) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            """
            SELECT opportunity_id, source_type, opportunity_category, sequence_role,
                   actionability_state, methodology_status, setup_expiry_seconds, status
            FROM opportunity_outcomes
            ORDER BY opportunity_id
            """
        ).fetchall()


def test_scan_registers_every_canonical_portfolio_opportunity(tmp_path: Path) -> None:
    generated_at = datetime(2026, 7, 20, 12, tzinfo=UTC).isoformat()
    analysis = _analysis("BTCUSDT", generated_at)
    payload = {
        "generated_at": generated_at,
        "configuration_id": "test-config",
        "results": [analysis],
    }
    path = tmp_path / "analysis.db"

    write_analysis_record_sqlite(path, build_analysis_record(payload))

    assert _rows(path) == [
        (
            "btc-long-current",
            "scan",
            "current",
            "primary",
            "EXECUTE_NOW",
            "allowed",
            3600,
            "waiting_entry",
        ),
        (
            "btc-short-follow-up",
            "scan",
            "current",
            "primary",
            "EXECUTE_NOW",
            "allowed",
            3600,
            "waiting_entry",
        ),
    ]


def test_scan_and_analysis_records_share_canonical_opportunity_ids(tmp_path: Path) -> None:
    generated_at = datetime(2026, 7, 20, 12, tzinfo=UTC).isoformat()
    analysis = _analysis("BTCUSDT", generated_at)
    path = tmp_path / "analysis.db"

    scan_payload = {
        "generated_at": generated_at,
        "configuration_id": "test-config",
        "results": [analysis],
    }
    write_analysis_record_sqlite(path, build_analysis_record(scan_payload))
    write_analysis_record_sqlite(path, build_analysis_record(analysis))

    assert len(_rows(path)) == 2


def test_each_canonical_opportunity_reconciles_independently(tmp_path: Path) -> None:
    generated = datetime(2026, 7, 20, 12, tzinfo=UTC)
    analysis = _analysis("BTCUSDT", generated.isoformat())
    path = tmp_path / "analysis.db"
    write_analysis_record_sqlite(path, build_analysis_record(analysis))

    class Candle:
        is_closed = True
        open_time = generated + timedelta(minutes=5)
        close_time = generated + timedelta(minutes=10)
        low = 99.0
        high = 111.0

    updated = reconcile_pending_opportunities_sqlite(path, "BTCUSDT", (Candle(),))

    assert updated == 2
    with sqlite3.connect(path) as connection:
        outcomes = dict(
            connection.execute(
                "SELECT opportunity_id, outcome FROM opportunity_outcomes"
            ).fetchall()
        )
    assert outcomes["btc-long-current"] == "target:110.0"
    assert outcomes["btc-short-follow-up"] is None
