"""Focused tests for the N4.8 historical futures backtest CLI."""

from __future__ import annotations

from pathlib import Path

import click
from typer.main import get_command
from typer.testing import CliRunner

from apex.backtesting import HistoricalFuturesExecutionManifest
from apex.backtesting.historical_futures_shared_campaign import (
    SharedHistoricalFuturesExecutionManifest,
)
from apex.cli_app import app
from apex.cli_commands.historical_futures_backtest import _echo_completion

runner = CliRunner()


def _historical_futures_command() -> click.Command:
    root = get_command(app)
    assert isinstance(root, click.Group)
    dataset = root.commands["dataset"]
    assert isinstance(dataset, click.Group)
    return dataset.commands["historical-futures-backtest"]


def test_historical_futures_backtest_command_is_registered() -> None:
    result = runner.invoke(app, ["dataset", "--help"], terminal_width=240)

    assert result.exit_code == 0
    assert "historical-futures-backtest" in result.stdout


def test_historical_futures_backtest_exposes_required_options() -> None:
    command = _historical_futures_command()
    exposed_options = {
        option
        for parameter in command.params
        if isinstance(parameter, click.Option)
        for option in parameter.opts + parameter.secondary_opts
    }

    assert {
        "--signal-records",
        "--signal-execution-manifest",
        "--result-output",
        "--execution-manifest-output",
        "--starting-equity",
        "--maximum-concurrent-positions",
        "--maximum-wallet-exposure-pct",
        "--daily-loss-limit-pct",
        "--consecutive-loss-limit",
    } <= exposed_options


def test_echo_completion_reports_deterministic_manifest_fields(capsys: object) -> None:
    base = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash="a" * 64,
        signal_configuration_hash="b" * 64,
        result_path="result.json",
        result_hash="c" * 64,
        total_decisions=12,
        trade_count=4,
        split_counts=(("final_test", 4), ("train", 4), ("validation", 4)),
    )
    manifest = SharedHistoricalFuturesExecutionManifest(
        base=base,
        wallet_configuration_hash="d" * 64,
        wallet_rejection_counts=(("maximum_wallet_exposure", 2),),
    )

    _echo_completion(manifest=manifest, result_output=Path("result.json"))

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "campaign_id=campaign-1" in captured.out
    assert "decisions=12" in captured.out
    assert "trades=4" in captured.out
    assert f"wallet_config_hash={'d' * 64}" in captured.out
    assert f"result_hash={'c' * 64}" in captured.out
