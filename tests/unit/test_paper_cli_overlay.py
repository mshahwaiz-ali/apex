"""Focused CLI coverage for the corrected paper-command overlay."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_trading as paper_cli
from apex.paper_trading import PaperPerformance

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    paper_cli.register_paper_trading_commands(app)
    return app


def _patch_report_dependencies(
    monkeypatch: Any,
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    trade = SimpleNamespace()

    class FakeStore:
        def __init__(self, path: Path) -> None:
            self.path = path

        def load(self) -> tuple[object, ...]:
            return (trade,)

    performance = PaperPerformance(
        total_trades=1,
        open_trades=1,
        closed_trades=0,
        net_pnl=12.5,
        win_rate=1.0,
        average_r_multiple=0.75,
        by_state={"entered": 1},
    )
    guidance = {
        "schema_version": 2,
        "generated_at": "2026-07-14T12:00:00+00:00",
        "trade_count": 1,
        "trades": [
            {
                "trade_id": "paper-1",
                "symbol": "BTCUSDT",
                "paper_state": "entered",
                "current_action": "HOLD",
                "instruction": "hold under the active structural stop",
            }
        ],
    }
    replay = {
        "schema_version": 1,
        "replayed_count": 1,
        "failure_count": 0,
        "trades": [{"trade_id": "paper-1", "status": "replayed"}],
    }

    monkeypatch.setattr(
        paper_cli,
        "bootstrap",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(data_dir=tmp_path),
        ),
    )
    monkeypatch.setattr(paper_cli, "PaperTradeStore", FakeStore)
    monkeypatch.setattr(
        paper_cli,
        "summarize_paper_trades",
        lambda trades: performance,
    )
    monkeypatch.setattr(
        paper_cli,
        "build_paper_guidance_report",
        lambda trades: guidance,
    )
    monkeypatch.setattr(
        paper_cli,
        "build_paper_replay_report",
        lambda trades: replay.copy(),
    )

    expected_report: dict[str, object] = {
        "performance": {
            "total_trades": 1,
            "open_trades": 1,
            "closed_trades": 0,
            "net_pnl": 12.5,
            "win_rate": 1.0,
            "average_r_multiple": 0.75,
            "by_state": {"entered": 1},
        },
        "guidance": guidance,
    }
    expected_replay: dict[str, object] = replay | {"guidance": guidance}
    return expected_report, expected_replay


def test_paper_commands_are_registered() -> None:
    app = _app()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "report" in result.stdout
    assert "replay-report" in result.stdout


def test_report_json_output_and_export(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    expected_report, _ = _patch_report_dependencies(monkeypatch, tmp_path)
    report_path = tmp_path / "exports" / "paper-report.json"

    result = runner.invoke(
        _app(),
        [
            "report",
            "--output",
            "json",
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == expected_report
    assert json.loads(report_path.read_text(encoding="utf-8")) == expected_report
    assert report_path.read_text(encoding="utf-8").endswith("\n")


def test_replay_report_json_output_and_export(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _, expected_replay = _patch_report_dependencies(monkeypatch, tmp_path)
    report_path = tmp_path / "exports" / "paper-replay-report.json"

    result = runner.invoke(
        _app(),
        [
            "replay-report",
            "--output",
            "json",
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == expected_replay
    assert json.loads(report_path.read_text(encoding="utf-8")) == expected_replay
    assert report_path.read_text(encoding="utf-8").endswith("\n")
