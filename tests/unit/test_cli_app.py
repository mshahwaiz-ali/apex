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
