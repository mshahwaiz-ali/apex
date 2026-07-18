"""Focused Stage 3 public CLI surface tests."""

from typer.main import get_command

from apex.cli_app import app


def test_public_cli_contains_only_stage3_commands() -> None:
    command = get_command(app)

    assert set(command.commands) == {
        "analyze",
        "backtest",
        "config-check",
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
