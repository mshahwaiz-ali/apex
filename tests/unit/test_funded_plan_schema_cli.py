"""Tests for funded futures-plan schema export."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_plan_schema import (
    FUNDED_PLAN_SCHEMA_VERSION,
    build_funded_plan_schema_bundle,
    register_funded_plan_schema_commands,
)

runner = CliRunner()
_EXPECTED_SCHEMAS = {
    "setup",
    "account",
    "policy",
    "state",
    "provider_binding",
    "funded_eligibility",
    "funded_plan_evidence_manifest",
    "funded_plan_evidence_package",
    "funded_plan_reproduction_report",
}


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_plan_schema_commands(app)
    return app


def test_schema_bundle_contains_all_funded_plan_contracts() -> None:
    payload = build_funded_plan_schema_bundle()

    assert payload["schema_version"] == FUNDED_PLAN_SCHEMA_VERSION
    assert payload["execution_authorized"] is False
    schemas = payload["schemas"]
    assert isinstance(schemas, dict)
    assert set(schemas) == _EXPECTED_SCHEMAS
    for schema in schemas.values():
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"

    for schema_name in (
        "funded_plan_evidence_manifest",
        "funded_plan_evidence_package",
        "funded_plan_reproduction_report",
    ):
        schema = schemas[schema_name]
        assert schema["properties"]["execution_authorized"]["const"] is False


def test_schema_command_writes_non_authorizing_bundle(tmp_path: Path) -> None:
    output = tmp_path / "schemas" / "funded-plan.json"

    result = runner.invoke(_app(), ["--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "FUNDED_PLAN_SCHEMA_WRITTEN" in result.output
    assert "schemas=9" in result.output
    assert "execution_authorized=false" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == FUNDED_PLAN_SCHEMA_VERSION
    assert payload["execution_authorized"] is False
    assert set(payload["schemas"]) == _EXPECTED_SCHEMAS


def test_schema_command_requires_force_to_replace_output(tmp_path: Path) -> None:
    output = tmp_path / "funded-plan.json"
    output.write_text("existing\n", encoding="utf-8")

    result = runner.invoke(_app(), ["--output", str(output)])

    assert result.exit_code != 0
    assert "output already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing\n"


def test_schema_command_force_replaces_output(tmp_path: Path) -> None:
    output = tmp_path / "funded-plan.json"
    output.write_text("existing\n", encoding="utf-8")

    result = runner.invoke(_app(), ["--output", str(output), "--force"])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["execution_authorized"] is False
    assert set(payload["schemas"]) == _EXPECTED_SCHEMAS
