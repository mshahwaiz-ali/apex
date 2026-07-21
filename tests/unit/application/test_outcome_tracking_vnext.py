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
        "methodology_version": "test-methodology",
        "setup": {
            "candidate_id": "candidate-1",
            "direction": "long",
            "setup_expiry_seconds": 3600,
            "entry": {"lower": 99.5, "upper": 100.5, "preferred": 100.0},
            "stop_loss": {"price": 98.0},
            "take_profits": [{"price": 104.0, "target_basis": "local_structure"}],
            "layered_state": {
                "execution_state": "clean",
                "setup_state": "breakout_retest",
                "context_state": "trending_up",
                "structural_bias": "bullish",
                "risk_condition": "normal",
                "timeframe_relationship": "with_trend",
                "relationship_severity": "none",
                "holding_horizon": "intraday",
                "continuation_state": "fresh_continuation",
            },
            "methodology_scores": {
                "pattern_confidence": 80.0,
                "directional_alignment": 82.0,
                "setup_quality": 84.0,
                "execution_quality": 86.0,
                "reward_quality": 88.0,
                "timing_quality": 90.0,
                "data_confidence": 92.0,
                "overall_trade_quality": 85.0,
                "rank_score": 87.0,
            },
            "runner_qualified": False,
            "runner_qualification_reason": "runner denied by fixture",
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
        row = connection.execute(
            "SELECT status, outcome, mfe_r, mae_r, methodology_version, "
            "opportunity_lane, layered_state_json, score_components_json, "
            "continuation_state, target_basis_json, runner_qualified, "
            "runner_qualification_reason FROM opportunity_outcomes"
        ).fetchone()
    (
        status,
        outcome,
        mfe_r,
        mae_r,
        methodology_version,
        opportunity_lane,
        layered_state_json,
        score_components_json,
        continuation_state,
        target_basis_json,
        runner_qualified,
        runner_reason,
    ) = row
    assert updated == 1
    assert (status, outcome) == ("resolved", "stop")
    assert mfe_r > 0
    assert mae_r < 0
    assert methodology_version == "test-methodology"
    assert opportunity_lane is None
    assert '"continuation_state": "fresh_continuation"' in layered_state_json
    assert '"execution_quality": 86.0' in score_components_json
    assert continuation_state == "fresh_continuation"
    assert target_basis_json == '["local_structure"]'
    assert runner_qualified == 0
    assert runner_reason == "runner denied by fixture"
