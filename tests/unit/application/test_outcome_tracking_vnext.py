from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.application.analysis_records import (
    build_analysis_record,
    reconcile_pending_opportunities_sqlite,
    write_analysis_record_sqlite,
)
from apex.domain.models import Candle

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _payload() -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "generated_at": NOW.isoformat(),
        "configuration_id": "fixture",
        "setup": {
            "candidate_id": "candidate-1",
            "direction": "long",
            "setup_expiry_seconds": 3600,
            "entry": {"lower": 99.5, "upper": 100.5, "preferred": 100.0},
            "stop_loss": {"price": 98.0},
            "take_profits": [{"price": 104.0}],
        },
        "developing_setup": None,
    }


def _candle(index: int, *, high: float, low: float) -> Candle:
    opened = NOW + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=100,
        high=high,
        low=low,
        close=100,
        volume=1000,
        is_closed=True,
        source="fixture",
    )


def test_opportunity_is_registered_and_reconciled_conservatively(tmp_path: Path) -> None:
    database = tmp_path / "analysis.db"
    write_analysis_record_sqlite(database, build_analysis_record(_payload(), recorded_at=NOW))

    # One bar touches entry, target and stop. Without tick order Apex assumes stop first.
    updated = reconcile_pending_opportunities_sqlite(
        database,
        "BTCUSDT",
        (_candle(1, high=105, low=97),),
    )

    with sqlite3.connect(database) as connection:
        status, outcome, mfe_r, mae_r = connection.execute(
            "SELECT status, outcome, mfe_r, mae_r FROM opportunity_outcomes"
        ).fetchone()
    assert updated == 1
    assert (status, outcome) == ("resolved", "stop")
    assert mfe_r > 0
    assert mae_r < 0
