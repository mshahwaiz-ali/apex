from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from apex.application.spot_historical_backtest import (
    SpotHistoricalBacktestManifest,
    SpotHistoricalBacktestResult,
)
from apex.cli_app import app
from apex.cli_commands import spot_historical_backtest as command_module


def _hash_payload(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _non_zero_result() -> SpotHistoricalBacktestResult:
    payload: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": "s9-cli-fixture",
        "source_dataset_sha256": "a" * 64,
        "replay_records_sha256": "b" * 64,
        "replay_configuration_sha256": "c" * 64,
        "backtest_configuration_sha256": "d" * 64,
        "execution_timeframes": {"BTCUSDT": "1h"},
        "configuration": {"starting_cash": 10_000.0},
        "metrics": {
            "signal_count": 1,
            "eligible_count": 1,
            "plan_count": 1,
            "fill_count": 1,
            "trade_count": 1,
            "ending_equity": 10_100.0,
        },
        "events": [
            {
                "time": "2026-01-01T01:00:00+00:00",
                "symbol": "BTCUSDT",
                "event": "ENTRY_FILLED",
                "order_id": "BTCUSDT:fixture",
                "detail": "ENTRY_1",
            }
        ],
        "trades": [
            {
                "symbol": "BTCUSDT",
                "realized_pnl": 100.0,
                "exit_reason": "FINAL_TARGET",
            }
        ],
        "equity_curve": [
            {
                "time": "2026-01-01T02:00:00+00:00",
                "cash": 10_100.0,
                "market_value": 0.0,
                "equity": 10_100.0,
                "exposure_utilization": 0.0,
                "open_position_count": 0,
            }
        ],
    }
    result_hash = _hash_payload(payload)
    payload["result_sha256"] = result_hash
    manifest = SpotHistoricalBacktestManifest(
        campaign_id="s9-cli-fixture",
        source_dataset_sha256="a" * 64,
        replay_records_sha256="b" * 64,
        replay_configuration_sha256="c" * 64,
        backtest_configuration_sha256="d" * 64,
        result_sha256=result_hash,
        signal_count=1,
        eligible_count=1,
        plan_count=1,
        fill_count=1,
        trade_count=1,
        ending_equity=10_100.0,
    )
    return SpotHistoricalBacktestResult(manifest=manifest, payload=payload)


def test_spot_history_backtest_cli_persists_and_reloads_non_zero_result(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    inputs = [tmp_path / name for name in ("history.jsonl", "history.json", "replay.jsonl", "replay.json")]
    for path in inputs:
        path.write_text("{}\n", encoding="utf-8")
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    expected = _non_zero_result()

    monkeypatch.setattr(
        command_module,
        "run_spot_historical_backtest",
        lambda **_: expected,
    )

    result = CliRunner().invoke(
        app,
        [
            "dataset",
            "spot-history-backtest",
            "--campaign-id",
            "s9-cli-fixture",
            "--dataset-records",
            str(inputs[0]),
            "--dataset-manifest",
            str(inputs[1]),
            "--replay-records",
            str(inputs[2]),
            "--replay-manifest",
            str(inputs[3]),
            "--result-output",
            str(result_path),
            "--execution-manifest-output",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "SPOT_HISTORICAL_BACKTEST_COMPLETED" in result.output
    assert "plans=1" in result.output
    assert "fills=1" in result.output
    assert "trades=1" in result.output
    assert json.loads(result_path.read_text(encoding="utf-8")) == expected.payload
    persisted_manifest = SpotHistoricalBacktestManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    assert persisted_manifest == expected.manifest
