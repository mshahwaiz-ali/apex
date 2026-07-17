"""Tests for historical futures edge report integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.backtesting.historical_futures_edge import build_historical_futures_edge_report
from apex.backtesting.historical_futures_shared_io import hash_json


def _trade(*, split: str, decision_time: str, realized_r: float) -> dict[str, object]:
    return {
        "result_id": f"{split}-{decision_time}",
        "split": split,
        "symbol": "BTC/USDT",
        "strategy": "trend_pullback",
        "direction": "long",
        "decision_time": decision_time,
        "exit_time": "2026-06-01T00:05:00+00:00",
        "entry_price": 100.0,
        "exit_price": 102.0 if realized_r > 0.0 else 99.0,
        "stop_price": 98.0,
        "target_prices": [102.0],
        "quantity": 1.0,
        "risk_amount": 2.0,
        "gross_pnl": realized_r * 2.0,
        "fees": 0.1,
        "net_pnl": realized_r * 2.0 - 0.1,
        "realized_r_multiple": realized_r,
        "holding_candles": 4,
        "outcome": "target" if realized_r > 0.0 else "stop",
        "metadata": {
            "market_regime": "trend",
            "entry_state": "READY_NOW",
            "active_risk_mode": "STANDARD",
            "confidence_score": 78.0,
        },
    }


def _write_campaign(tmp_path: Path) -> tuple[Path, Path]:
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    result: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": "edge-campaign",
        "starting_equity": 10_000.0,
        "ending_equity": 10_001.8,
        "net_pnl": 1.8,
        "total_decisions": 2,
        "trade_count": 2,
        "observations": [],
        "trades": [
            _trade(
                split="train",
                decision_time="2026-06-01T00:01:00+00:00",
                realized_r=1.0,
            ),
            _trade(
                split="final_test",
                decision_time="2026-06-01T00:02:00+00:00",
                realized_r=-1.0,
            ),
        ],
        "split_metrics": {},
        "rejection_counts": {},
        "warnings": [],
        "shared_wallet": {},
    }
    manifest = {
        "schema_version": 1,
        "campaign_id": "edge-campaign",
        "status": "completed",
        "signal_records_hash": "a" * 64,
        "signal_configuration_hash": "b" * 64,
        "wallet_configuration_hash": "c" * 64,
        "result_path": result_path.as_posix(),
        "result_hash": hash_json(result),
        "total_decisions": 2,
        "trade_count": 2,
        "split_counts": {"train": 1, "final_test": 1},
        "wallet_rejection_counts": {},
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return result_path, manifest_path


def test_builds_split_isolated_edge_profiles(tmp_path: Path) -> None:
    result_path, manifest_path = _write_campaign(tmp_path)

    report = build_historical_futures_edge_report(
        result_path=result_path,
        execution_manifest_path=manifest_path,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    assert report["campaign_id"] == "edge-campaign"
    assert report["trade_count"] == 2
    assert report["split_trade_counts"] == {"final_test": 1, "train": 1}
    profiles = report["profiles"]
    assert isinstance(profiles, list)
    assert {profile["dimensions"]["split"] for profile in profiles} == {
        "train",
        "final_test",
    }
    assert any("must not drive calibration" in warning for warning in report["warnings"])


def test_rejects_tampered_campaign_result(tmp_path: Path) -> None:
    result_path, manifest_path = _write_campaign(tmp_path)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["ending_equity"] = 99_999.0
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="result hash"):
        build_historical_futures_edge_report(
            result_path=result_path,
            execution_manifest_path=manifest_path,
            generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
