"""Focused tests for the N4.8 historical futures backtest CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from apex.backtesting import HistoricalFuturesExecutionManifest
from apex.cli_app import app
from apex.cli_commands.historical_futures_backtest import _echo_completion

runner = CliRunner()


def test_historical_futures_backtest_command_is_registered() -> None:
    result = runner.invoke(app, ["dataset", "--help"])

    assert result.exit_code == 0
    assert "historical-futures-backtest" in result.stdout


def test_historical_futures_backtest_help_exposes_required_artifacts() -> None:
    result = runner.invoke(app, ["dataset", "historical-futures-backtest", "--help"])

    assert result.exit_code == 0
    assert "--signal-records" in result.stdout
    assert "--signal-execution-manifest" in result.stdout
    assert "--result-output" in result.stdout
    assert "--execution-manifest-output" in result.stdout
    assert "--starting-equity" in result.stdout


def test_echo_completion_reports_deterministic_manifest_fields(capsys: object) -> None:
    manifest = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash="a" * 64,
        signal_configuration_hash="b" * 64,
        result_path="result.json",
        result_hash="c" * 64,
        total_decisions=12,
        trade_count=4,
        split_counts=(("final_test", 4), ("train", 4), ("validation", 4)),
    )

    _echo_completion(manifest=manifest, result_output=Path("result.json"))

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "campaign_id=campaign-1" in captured.out
    assert "decisions=12" in captured.out
    assert "trades=4" in captured.out
    assert f"result_hash={'c' * 64}" in captured.out
