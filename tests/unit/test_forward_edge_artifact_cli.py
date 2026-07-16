from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.forward_edge_artifact import register_forward_edge_artifact_commands
from apex.cli_commands.forward_edge_artifact_verify import (
    register_forward_edge_artifact_verify_commands,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_forward_edge_artifact_commands(app)
    register_forward_edge_artifact_verify_commands(app)
    return app


def _write_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "report_id": "forward-edge-example",
                "generated_at": "2026-07-16T12:00:00+00:00",
                "campaign_id": "campaign-1",
                "source_validation_report_id": "historical-validation-1",
                "policy": {
                    "minimum_closed_trades": 30,
                    "minimum_expectancy": 0.0,
                    "minimum_profit_factor": 1.0,
                    "maximum_expectancy_degradation": 0.5,
                },
                "segment_count": 0,
                "validated_forward_paper_count": 0,
                "results": [],
                "warnings": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_historical(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "report_id": "historical-validation-1",
                "campaign_id": "campaign-1",
                "results": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_forward_edge_seal_is_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "forward-edge-seal" in result.output


def test_forward_edge_seal_writes_verified_artifact(tmp_path: Path) -> None:
    report = tmp_path / "forward.json"
    historical = tmp_path / "historical.json"
    output = tmp_path / "sealed.json"
    _write_report(report)
    _write_historical(historical)

    result = runner.invoke(
        _app(),
        [
            "forward-edge-seal",
            "--report",
            str(report),
            "--historical-validation",
            str(historical),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "FORWARD_EDGE_ARTIFACT_SEALED" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"]["historical_validation_name"] == "historical.json"
    assert len(payload["source"]["historical_validation_sha256"]) == 64
    assert len(payload["artifact_sha256"]) == 64
    assert payload["execution_authorized"] is False


def test_forward_edge_seal_requires_force_for_existing_output(tmp_path: Path) -> None:
    report = tmp_path / "forward.json"
    historical = tmp_path / "historical.json"
    output = tmp_path / "sealed.json"
    _write_report(report)
    _write_historical(historical)
    output.write_text("existing\n", encoding="utf-8")

    blocked = runner.invoke(
        _app(),
        [
            "forward-edge-seal",
            "--report",
            str(report),
            "--historical-validation",
            str(historical),
            "--output",
            str(output),
        ],
    )

    assert blocked.exit_code != 0
    assert "refusing to overwrite forward edge artifact" in blocked.output

    replaced = runner.invoke(
        _app(),
        [
            "forward-edge-seal",
            "--report",
            str(report),
            "--historical-validation",
            str(historical),
            "--output",
            str(output),
            "--force",
        ],
    )

    assert replaced.exit_code == 0, replaced.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["forward_edge_report"]["report_id"] == "forward-edge-example"
