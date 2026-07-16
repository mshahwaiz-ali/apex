from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from typer.testing import CliRunner

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics
from apex.cli_commands import paper_lifecycle_health as lifecycle_cli

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    paper_app = typer.Typer(no_args_is_help=True)
    lifecycle_cli.register_paper_lifecycle_health_command(paper_app)
    app.add_typer(paper_app, name="paper")
    return app


def _analytics() -> PaperLifecycleAnalytics:
    values: dict[str, object] = {
        "intake_candidates_observed": 20,
        "intake_accepted": 20,
        "intake_rejected": 0,
        "duplicates_skipped": 0,
        "persistence_failures": 0,
        "intake_reason_counts": {},
        "loaded_trades": 20,
        "eligible_trades": 20,
        "advanced_trades": 20,
        "unchanged_trades": 0,
        "missing_candle_trades": 0,
        "requested_symbols": 20,
        "successful_symbols": 20,
        "provider_failure_count": 0,
        "provider_failures_by_symbol": {},
        "state_counts": {"target_hit": 12, "stopped": 8},
        "entry_state_counts": {},
        "waiting_for_entry": 0,
        "entered_trades": 20,
        "unfilled_terminal_trades": 0,
        "partial_target_fills": 6,
        "full_target_completions": 12,
        "stop_loss_exits": 8,
        "expired_trades": 0,
        "invalidations": 0,
        "cancelled_trades": 0,
        "transition_counts": {},
        "transition_reason_counts": {},
        "realized_net_pnl": 10.0,
        "average_realized_r_multiple": 0.5,
        "risk_multiple_distribution": {},
        "leverage_distribution": {},
        "holding_time_distribution": {},
        "average_margin": 10.0,
        "average_wallet_exposure_pct": 8.0,
        "total_fees": 1.0,
        "total_slippage": 0.5,
        "trades": (),
    }
    assert values.keys() == {field.name for field in fields(PaperLifecycleAnalytics)}
    return PaperLifecycleAnalytics(**values)  # type: ignore[arg-type]


def _write_pipeline_log(tmp_path: Path) -> Path:
    path = (
        tmp_path
        / "paper_trading"
        / "scheduler"
        / "logs"
        / "pipeline-futures.jsonl"
    )
    path.parent.mkdir(parents=True)
    record = {
        "schema_version": 3,
        "run_id": "run-1",
        "outcome": "success",
        "market_type": "futures",
        "completed_at": "2026-07-16T12:00:00+00:00",
        "lifecycle_analytics": asdict(_analytics()),
    }
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _patch_bootstrap(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(
        lifecycle_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )


def test_lifecycle_health_command_is_registered() -> None:
    result = runner.invoke(_app(), ["paper", "--help"])

    assert result.exit_code == 0
    assert "lifecycle-health" in result.output


def test_lifecycle_health_json_report_contains_source_hashes(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _patch_bootstrap(monkeypatch, tmp_path)
    _write_pipeline_log(tmp_path)
    report_path = tmp_path / "reports" / "health.json"

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health",
            "--output",
            "json",
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["source"]["log_name"] == "pipeline-futures.jsonl"
    assert len(payload["source"]["source_record_sha256"]) == 64
    assert len(payload["source"]["source_log_sha256"]) == 64
    assert len(payload["source"]["analytics_sha256"]) == 64
    assert payload["execution_authorized"] is False


def test_invalid_output_does_not_create_report(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _patch_bootstrap(monkeypatch, tmp_path)
    _write_pipeline_log(tmp_path)
    report_path = tmp_path / "health.json"

    result = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health",
            "--output",
            "invalid",
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "output must be text or json" in result.output
    assert not report_path.exists()


def test_report_overwrite_requires_force(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _patch_bootstrap(monkeypatch, tmp_path)
    _write_pipeline_log(tmp_path)
    report_path = tmp_path / "health.json"

    first = runner.invoke(
        _app(),
        ["paper", "lifecycle-health", "--report", str(report_path)],
    )
    rejected = runner.invoke(
        _app(),
        ["paper", "lifecycle-health", "--report", str(report_path)],
    )
    forced = runner.invoke(
        _app(),
        [
            "paper",
            "lifecycle-health",
            "--report",
            str(report_path),
            "--force-report",
        ],
    )

    assert first.exit_code == 0, first.output
    assert rejected.exit_code != 0
    assert "refusing to overwrite" in rejected.output
    assert forced.exit_code == 0, forced.output
