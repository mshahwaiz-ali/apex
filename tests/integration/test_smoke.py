from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from apex.cli import app

runner = CliRunner()


def test_smoke_command_bootstraps_application(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        "environment: test\n"
        "log_level: INFO\n"
        f"data_dir: {tmp_path / 'data'}\n"
        f"log_dir: {tmp_path / 'logs'}\n"
        "cache_enabled: true\n"
        "analysis_timeframes: [1m, 5m, 1h]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APEX_CONFIG_DIR", str(config_dir))
    result = runner.invoke(app, ["smoke", "--output", "json"])
    assert result.exit_code == 0
    assert '"status": "ok"' in result.stdout
