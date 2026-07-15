"""Tests for N4.9 futures out-of-sample edge validation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from apex.backtesting.historical_edge_validation import HistoricalEdgeValidationPolicy
from apex.backtesting.historical_futures_edge_validation import (
    build_historical_futures_edge_validation_report,
    load_historical_futures_edge_validation_report,
    write_historical_futures_edge_validation_report,
)


def _profile(*, split: str, sample_size: int, expectancy: float) -> dict[str, object]:
    return {
        "dimensions": {
            "split": split,
            "market_type": "futures",
            "strategy": "trend_pullback",
            "direction": "long",
            "symbol": "BTC/USDT",
            "market_regime": "trend",
            "score_band": "70_79",
            "entry_state": "READY_NOW",
            "risk_mode": "STANDARD",
        },
        "sample_size": sample_size,
        "win_rate": 0.60,
        "loss_rate": 0.40,
        "breakeven_rate": 0.0,
        "average_r": expectancy,
        "median_r": expectancy,
        "expectancy": expectancy,
        "profit_factor": 1.5,
        "maximum_drawdown_r": 3.0,
        "maximum_losing_streak": 3,
        "average_holding_candles": 6.0,
        "average_execution_cost_r": 0.05,
        "evidence_quality": "PROMISING" if sample_size >= 100 else "RESEARCH_ONLY",
        "out_of_sample_validated": False,
        "forward_paper_validated": False,
        "warnings": [],
    }


def _write_edge_report(tmp_path: Path, *, final_expectancy: float = 0.35) -> Path:
    path = tmp_path / "edge.json"
    payload = {
        "schema_version": 1,
        "report_id": "historical-edge-example",
        "generated_at": "2026-07-15T00:00:00+00:00",
        "source_type": "historical_futures_campaign",
        "source_id": "campaign",
        "campaign_id": "campaign",
        "source_result_hash": "a" * 64,
        "profile_count": 3,
        "profiles": [
            _profile(split="train", sample_size=100, expectancy=0.50),
            _profile(split="validation", sample_size=50, expectancy=0.40),
            _profile(split="final_test", sample_size=50, expectancy=final_expectancy),
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_promotes_stable_matching_segment_and_round_trips(tmp_path: Path) -> None:
    edge_path = _write_edge_report(tmp_path)
    policy = HistoricalEdgeValidationPolicy(
        minimum_validation_trades=50,
        minimum_test_trades=50,
        minimum_out_of_sample_trades=100,
    )

    report = build_historical_futures_edge_validation_report(
        edge_report_path=edge_path,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        policy=policy,
    )

    assert report["validated_out_of_sample_count"] == 1
    assert report["status_counts"] == {"PASSED_VALIDATION": 1}
    result = report["results"][0]
    assert result["promoted_evidence_quality"] == "VALIDATED_OUT_OF_SAMPLE"
    assert result["dimensions"]["strategy"] == "trend_pullback"
    assert "split" not in result["dimensions"]

    output = tmp_path / "validation.json"
    write_historical_futures_edge_validation_report(output, report)
    assert load_historical_futures_edge_validation_report(output) == report


def test_rejects_unstable_final_test_and_keeps_report_id_deterministic(tmp_path: Path) -> None:
    edge_path = _write_edge_report(tmp_path, final_expectancy=-0.10)
    policy = HistoricalEdgeValidationPolicy(
        minimum_validation_trades=50,
        minimum_test_trades=50,
        minimum_out_of_sample_trades=100,
    )

    first = build_historical_futures_edge_validation_report(
        edge_report_path=edge_path,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        policy=policy,
    )
    second = build_historical_futures_edge_validation_report(
        edge_report_path=edge_path,
        generated_at=datetime(2026, 7, 16, tzinfo=UTC),
        policy=policy,
    )

    assert first["report_id"] == second["report_id"]
    assert first["validated_out_of_sample_count"] == 0
    result = first["results"][0]
    assert result["status"] == "FAILED_VALIDATION"
    assert "TEST_EXPECTANCY_NOT_POSITIVE" in result["rejection_reasons"]
