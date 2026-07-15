from typer.testing import CliRunner

from apex.cli_app import app


def test_spot_scan_live_is_registered_on_installed_cli_app() -> None:
    result = CliRunner().invoke(app, ["spot-scan-live", "--help"])

    assert result.exit_code == 0, result.output
    assert "--symbols" in result.output
    assert "--account" in result.output
    assert "--candles" in result.output
