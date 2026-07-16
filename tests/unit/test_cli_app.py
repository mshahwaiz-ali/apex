from apex.cli_app import app
from apex.cli_overlay import command_name


def test_corrected_cli_exposes_explicit_simulation_and_backtest_commands() -> None:
    names = {command_name(command) for command in app.registered_commands}

    assert "analyze" in names
    assert "fetch" in names
    assert "ticker" in names
    assert "simulate-current-setup" in names
    assert "chronological-backtest" in names
    assert "backtest" not in names


def test_frozen_and_removed_workflows_are_not_registered() -> None:
    command_names = {
        command_name(command)
        for command in app.registered_commands
        if command_name(command) is not None
    }
    group_names = {
        group.name
        for group in app.registered_groups
        if group.name is not None and not group.hidden
    }

    assert {
        "spot-analyze",
        "spot-orchestrate",
        "spot-live",
        "spot-scan-live",
        "spot-plan",
    }.isdisjoint(command_names)

    assert {
        "spot",
        "optimize",
        "intelligence",
        "execute",
    }.isdisjoint(group_names)


def test_futures_scan_does_not_expose_gainer_mode_option() -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["futures", "scan", "--help"])

    assert result.exit_code == 0, result.output
    assert "--mode" not in result.output
    assert "gainers" not in result.output.lower()


def test_root_scan_does_not_expose_gainer_mode_option() -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["scan", "--help"])

    assert result.exit_code == 0, result.output
    assert "--mode" not in result.output
    assert "gainers" not in result.output.lower()
