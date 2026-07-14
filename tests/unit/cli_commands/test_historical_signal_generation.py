"""Tests for the historical signal-generation CLI."""

from __future__ import annotations

import re
from pathlib import Path
from typer.testing import CliRunner

from apex.cli_app import app
from apex.cli_commands.historical_signal_generation import (
    _configuration_paths,
    _validate_output_paths,
)

runner = CliRunner()

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain_output(result: object) -> str:
    output = str(getattr(result, "output", ""))
    return _ANSI_ESCAPE.sub("", output)


def _compact_output(result: object) -> str:
    return re.sub(
        r"[^A-Za-z0-9_-]+",
        "",
        _plain_output(result),
    )


def test_historical_signal_command_is_registered() -> None:
    result = runner.invoke(
        app,
        [
            "dataset",
            "historical-signals-generate",
            "--help",
        ],
    )

    assert result.exit_code == 0
    output = _compact_output(result)
    assert "historical-signals-generate" in output
    assert "--plan" in output
    assert "--records-output" in output
    assert "--configuration-file" in output
    assert "--candle-limit" in output


def test_configuration_paths_preserve_order_and_deduplicate(
    tmp_path: Path,
) -> None:
    risk = tmp_path / "risk.yaml"
    futures = tmp_path / "futures.yaml"

    paths = _configuration_paths(
        risk_config=risk,
        additional=(
            futures,
            risk,
            futures,
        ),
    )

    assert paths == (
        risk,
        futures,
    )


def test_output_paths_must_be_distinct(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signals.json"

    try:
        _validate_output_paths(
            records_output=path,
            execution_manifest_output=path,
        )
    except ValueError as exc:
        assert "different paths" in str(exc)
    else:
        raise AssertionError("matching historical output paths must be rejected")


def test_cli_rejects_matching_output_paths(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.json"
    dataset_execution = tmp_path / "dataset-execution.json"
    risk = tmp_path / "risk.yaml"
    output = tmp_path / "signals.json"

    plan.write_text("{}\n", encoding="utf-8")
    dataset_execution.write_text("{}\n", encoding="utf-8")
    risk.write_text("{}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "dataset",
            "historical-signals-generate",
            "--plan",
            str(plan),
            "--dataset-execution-manifest",
            str(dataset_execution),
            "--records-output",
            str(output),
            "--execution-manifest-output",
            str(output),
            "--risk-config",
            str(risk),
        ],
    )

    assert result.exit_code != 0
    output = _compact_output(result)
    assert "mustusedifferentpaths" in output
