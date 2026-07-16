from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_pipeline as pipeline_cli
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary
from apex.paper_trading.scheduler import ScheduledPaperCycleResult

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    pipeline_cli.register_paper_pipeline_commands(app)
    return app


def _summary(market_type: IntakeMarketType) -> IntakeSummary:
    return IntakeSummary(
        market_type=market_type,
        candidates_observed=2,
        accepted=1,
        rejected=1,
        duplicates_skipped=0,
        persistence_failures=0,
        reason_counts={"ACCEPTED": 1, "NO_APPROVED_SETUP": 1},
        created_trade_ids=("paper-1",),
        results=(),
    )


def _cycle(market_type: str, started_at: datetime) -> ScheduledPaperCycleResult:
    runtime = SimpleNamespace(
        cycle=SimpleNamespace(
            eligible_trade_count=1,
            advanced_trade_count=1,
            unchanged_trade_count=0,
        ),
        provider_failures=(),
    )
    return ScheduledPaperCycleResult(
        market_type=market_type,
        started_at=started_at,
        completed_at=started_at,
        runtime=runtime,  # type: ignore[arg-type]
        lock_path="cycle.lock",
        log_path="cycle.jsonl",
    )


def _pipeline_result(started_at: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        market_type=IntakeMarketType.FUTURES,
        started_at=started_at,
        completed_at=started_at,
        intake=_summary(IntakeMarketType.FUTURES),
        cycle=_cycle("futures", started_at),
        lock_path="pipeline.lock",
        log_path="pipeline.jsonl",
        lifecycle_analytics={},
    )


def test_combined_pipeline_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "scheduled-futures-pipeline" in result.stdout
    assert "scheduled-spot-pipeline" in result.stdout


def test_emit_pipeline_json_is_machine_readable(monkeypatch: Any, capsys: Any) -> None:
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    result = _pipeline_result(started_at)
    monkeypatch.setattr(
        pipeline_cli,
        "paper_pipeline_payload",
        lambda value: {
            "market_type": value.market_type.value,
            "intake": {"accepted": value.intake.accepted},
        },
    )

    pipeline_cli._emit_pipeline(
        result,  # type: ignore[arg-type]
        "json",
        diagnostics={
            "scan_analysis_count": 4,
            "scanner_failure_count": 1,
            "scanner_failures": {"normal:BAD/USDT": "provider failure"},
        },
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["market_type"] == "futures"
    assert payload["intake"]["accepted"] == 1
    assert payload["diagnostics"]["scan_analysis_count"] == 4
    assert payload["diagnostics"]["scanner_failure_count"] == 1


def test_emit_pipeline_text_surfaces_scanner_counts(monkeypatch: Any, capsys: Any) -> None:
    started_at = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    result = _pipeline_result(started_at)
    monkeypatch.setattr(pipeline_cli, "paper_pipeline_payload", lambda value: {})

    pipeline_cli._emit_pipeline(
        result,  # type: ignore[arg-type]
        "verbose",
        diagnostics={
            "scan_analysis_count": 4,
            "scanner_failure_count": 2,
            "scanner_failures": {},
        },
    )

    output = capsys.readouterr().out
    assert "Pipeline diagnostics" in output
    assert "Scan analyses" in output
    assert ": 4" in output
    assert "Scanner failures" in output
    assert ": 2" in output


def test_cycle_paths_are_market_separated(tmp_path: Path) -> None:
    assert pipeline_cli._cycle_lock(tmp_path, "futures") != pipeline_cli._cycle_lock(
        tmp_path, "spot"
    )
    assert pipeline_cli._cycle_log(tmp_path, "futures") != pipeline_cli._cycle_log(
        tmp_path, "spot"
    )
