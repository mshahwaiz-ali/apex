"""Regression tests for the locked public Apex CLI command surface."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from apex.cli_app import app

runner = CliRunner()


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], "research"),
        (["scan", "--help"], "--symbols-file"),
        (["analyze", "--help"], "SYMBOL"),
        (["backtest", "--help"], "--report-file"),
        (["research", "--help"], "campaign"),
        (["research", "campaign", "--help"], "--dataset-dir"),
        (["config-check", "--help"], "config-check"),
        (["version", "--help"], "version"),
    ],
)
def test_public_command_help(arguments: list[str], expected: str) -> None:
    """Every locked public command remains visible and help-renderable."""

    result = runner.invoke(app, arguments or ["--help"])

    assert result.exit_code == 0, result.output
    assert expected in result.output


@pytest.mark.parametrize(
    "arguments",
    [
        ["scan", "--record", "test.jsonl"],
        ["scan", "--record-db", "test.db"],
        ["scan", "--report", "test.json"],
        ["analyze", "BTCUSDT", "--record", "test.jsonl"],
        ["analyze", "BTCUSDT", "--record-db", "test.db"],
    ],
)
def test_removed_scan_and_analyze_options_are_rejected(arguments: list[str]) -> None:
    """Removed manual persistence/report options must not silently return."""

    result = runner.invoke(app, arguments)

    assert result.exit_code != 0
    assert "No such option" in result.output


@pytest.mark.parametrize(
    "arguments",
    [
        ["backtest", "BTCUSDT", "--campaign"],
        ["backtest", "BTCUSDT", "--start", "2026-01"],
        ["backtest", "BTCUSDT", "--end", "2026-06"],
        ["backtest", "BTCUSDT", "--symbols-file", "symbols.json"],
        ["backtest", "BTCUSDT", "--dataset-dir", "data/research"],
        ["backtest", "BTCUSDT", "--download-missing"],
        ["backtest", "BTCUSDT", "--train-model"],
        ["backtest", "BTCUSDT", "--report", "result.json"],
    ],
)
def test_removed_backtest_campaign_options_are_rejected(arguments: list[str]) -> None:
    """Research-only options must remain outside the backtest command."""

    result = runner.invoke(app, arguments)

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_backtest_requires_symbol() -> None:
    """The focused backtest command always requires one symbol."""

    result = runner.invoke(app, ["backtest"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_research_campaign_owns_report_file_option() -> None:
    """Research campaign exposes the standardized report-file option."""

    result = runner.invoke(app, ["research", "campaign", "--help"])

    assert result.exit_code == 0, result.output
    assert "--report-file" in result.output
    assert "--download-missing" in result.output
    assert "--train-model" in result.output
