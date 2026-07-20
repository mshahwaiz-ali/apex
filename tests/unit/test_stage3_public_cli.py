"""Focused Stage 3 public CLI surface tests."""

from typer.main import get_command

from apex.cli_app import app
from apex.cli_commands.backtesting import _campaign_partition, _campaign_source_limit


def test_public_cli_contains_only_stage3_commands() -> None:
    command = get_command(app)

    assert set(command.commands) == {
        "analyze",
        "backtest",
        "config-check",
        "research",
        "scan",
        "version",
    }


def test_removed_command_groups_are_not_registered() -> None:
    command = get_command(app)

    assert {
        "paper",
        "funded",
        "execution",
        "validation",
        "readiness",
    }.isdisjoint(command.commands)


def test_scan_exposes_stage3_operator_controls() -> None:
    command = get_command(app)
    scan = command.commands["scan"]

    option_names = {name for parameter in scan.params for name in parameter.opts}

    assert {
        "--results",
        "--shortlist",
        "--direction",
        "--config-dir",
    }.issubset(option_names)


def test_analyze_and_backtest_accept_config_dir() -> None:
    command = get_command(app)

    for command_name in ("analyze", "backtest"):
        option_names = {
            name for parameter in command.commands[command_name].params for name in parameter.opts
        }
        assert "--config-dir" in option_names


def test_backtest_exposes_campaign_controls() -> None:
    command = get_command(app).commands["backtest"]
    option_names = {name for parameter in command.params for name in parameter.opts}

    assert {"--decision-points", "--funding-pct"}.issubset(option_names)


def test_backtest_campaign_partitions_are_chronological_and_frozen() -> None:
    assert [_campaign_partition(index, 5) for index in range(5)] == [
        "training",
        "training",
        "training",
        "validation",
        "final_test",
    ]
    assert _campaign_partition(0, 1) == "final_test"


def test_backtest_campaign_fetches_enough_history_for_shorter_frames() -> None:
    common = {
        "replay_timeframe": "5m",
        "candle_limit": 200,
        "replay_candles": 4,
        "decision_points": 2,
    }

    assert _campaign_source_limit(timeframe="5m", **common) == 212
    assert _campaign_source_limit(timeframe="1m", **common) == 244
