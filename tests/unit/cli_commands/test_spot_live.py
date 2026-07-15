"""Installed CLI coverage for live spot analysis."""

from typer.testing import CliRunner

from apex.cli_app import app


def test_spot_live_is_registered_on_installed_cli_app() -> None:
    result = CliRunner().invoke(app, ["spot-live", "--help"])

    assert result.exit_code == 0, result.output
    assert "--account" in result.output
    assert "--strategy-config" in result.output
    assert "--candles" in result.output
