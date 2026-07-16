"""Execution tests for the provider-independent spot-orchestrate command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from apex.cli_app import app

FIXTURES = Path("tests/fixtures/spot_orchestration")
RUNNER = CliRunner()


def _invoke(fixture: str, *extra: str):
    return RUNNER.invoke(
        app,
        [
            "spot-orchestrate",
            "--input",
            str(FIXTURES / fixture),
            "--format",
            "json",
            *extra,
        ],
    )


def test_spot_orchestrate_approved_input_succeeds() -> None:
    result = _invoke("approved_trend_pullback.json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["selected_strategy"]["strategy"] == "higher_timeframe_trend_pullback"
    assert payload["selected_strategy"]["decision"] == "APPROVE"
    assert payload["planning"] is not None


def test_spot_orchestrate_blocked_input_succeeds_without_plan() -> None:
    result = _invoke("blocked_risk_off.json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["selected_strategy"] is None
    assert payload["planning"] is None


def test_spot_orchestrate_missing_evidence_remains_explicit() -> None:
    result = _invoke("missing_evidence.json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["selected_strategy"] is None
    assert payload["planning"] is None
    assert len(payload["candidates"]) == 6
    assert all(candidate["decision"] != "APPROVE" for candidate in payload["candidates"])


def test_spot_orchestrate_output_file_equals_stdout(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    result = _invoke("approved_trend_pullback.json", "--output", str(output))

    assert result.exit_code == 0, result.output
    assert output.read_text(encoding="utf-8") == result.stdout


def test_spot_orchestrate_malformed_input_exits_non_zero() -> None:
    result = _invoke("malformed_geometry.json")

    assert result.exit_code != 0
    assert "canonical spot support must be below resistance" in result.output


def test_spot_orchestrate_uses_default_config_paths() -> None:
    result = _invoke("approved_trend_pullback.json")

    assert result.exit_code == 0, result.output
    assert "config/spot.yaml" not in result.output
    assert "config/spot_strategies.yaml" not in result.output


def test_spot_orchestrate_stdout_is_byte_stable() -> None:
    first = _invoke("approved_trend_pullback.json")
    second = _invoke("approved_trend_pullback.json")

    assert first.exit_code == second.exit_code == 0
    assert first.stdout == second.stdout


def test_spot_orchestrate_is_registered_on_installed_cli_app() -> None:
    result = RUNNER.invoke(app, ["spot-orchestrate", "--help"])

    assert result.exit_code == 0, result.output
    assert "--input" in result.output
    assert "--strategy-config" in result.output
