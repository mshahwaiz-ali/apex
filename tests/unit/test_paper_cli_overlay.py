"""Focused CLI coverage for the corrected paper-command overlay."""

from __future__ import annotations

import json
from types import SimpleNamespace

import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_trading as paper_cli


runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    paper_cli.register_paper_trading_commands(app)
    return app


def test_corrected_overlay_registers_all_paper_commands() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "update" in result.stdout
    assert "report" in result.stdout
    assert "replay-report" in result.stdout


def test_paper_report_json_uses_guidance_schema(monkeypatch: object, tmp_path: object) -> None:
    data_dir = tmp_path
    monkeypatch.setattr(
        paper_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=data_dir)),
    )

    result = runner.invoke(_app(), ["report", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["performance"]["total_trades"] == 0
    assert payload["guidance"]["schema_version"] == 2
    assert payload["guidance"]["trade_count"] == 0


def test_paper_replay_report_json_attaches_guidance(monkeypatch: object, tmp_path: object) -> None:
    data_dir = tmp_path
    monkeypatch.setattr(
        paper_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=data_dir)),
    )

    result = runner.invoke(_app(), ["replay-report", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["replayed_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["guidance"]["schema_version"] == 2
    assert payload["guidance"]["trade_count"] == 0
