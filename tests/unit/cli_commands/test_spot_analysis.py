"""Execution tests for the research-only spot-analyze CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from apex.cli_app import app

FIXTURES = Path("tests/fixtures/spot")
RUNNER = CliRunner()


def _invoke(fixture: str, *extra: str):
    return RUNNER.invoke(
        app,
        [
            "spot-analyze",
            "--input",
            str(FIXTURES / fixture),
            "--format",
            "json",
            *extra,
        ],
    )


def test_spot_analyze_approved_input_succeeds() -> None:
    result = _invoke("approved_trend_pullback.json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["selected_strategy"]["decision"] == "APPROVE"
    assert payload["planning"]["entry_plan"]["direction"] == "LONG"


def test_spot_analyze_blocked_input_returns_no_plan() -> None:
    result = _invoke("blocked_risk_off.json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["selected_strategy"] is None
    assert payload["planning"] is None
    assert len(payload["candidates"]) == 6


def test_spot_analyze_creates_output_file(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    result = _invoke("approved_trend_pullback.json", "--output", str(output))

    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(result.stdout)


def test_spot_analyze_malformed_input_exits_non_zero() -> None:
    result = _invoke("malformed_geometry.json")

    assert result.exit_code != 0
    assert "spot support must be below resistance" in result.output


def test_spot_analyze_uses_default_config_paths() -> None:
    result = _invoke("approved_trend_pullback.json")

    assert result.exit_code == 0, result.output
    assert "config/spot.yaml" not in result.output
    assert "config/spot_strategies.yaml" not in result.output


def test_spot_analyze_stdout_is_stable() -> None:
    first = _invoke("approved_trend_pullback.json")
    second = _invoke("approved_trend_pullback.json")

    assert first.exit_code == second.exit_code == 0
    assert first.stdout == second.stdout
