"""Tests for read-only funded futures-plan reporting."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_plan_reporting import register_funded_plan_reporting_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_plan_reporting_commands(app)
    return app


def _payload(*, execution_authorized: bool = False) -> dict[str, object]:
    return {
        "status": "APPROVED",
        "symbol": "BTC/USDT",
        "funded_eligibility": {
            "state": "ELIGIBLE_FOR_FUNDED_REVIEW",
            "reasons": [],
            "provider_name": "Example Funded",
            "challenge_phase": "PHASE_1",
            "provider_preset_sha256": "a" * 64,
            "execution_authorized": False,
        },
        "execution_authorized": execution_authorized,
    }


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_command_is_registered() -> None:
    result = runner.invoke(_app(), ["--help"])

    assert result.exit_code == 0
    assert "funded-plan-report" in result.output


def test_json_output_preserves_non_authorizing_metadata(tmp_path: Path) -> None:
    source = tmp_path / "plan.json"
    _write_payload(source, _payload())

    result = runner.invoke(
        _app(),
        ["funded-plan-report", "--input", str(source), "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["symbol"] == "BTC/USDT"
    assert payload["funded_eligibility"]["state"] == "ELIGIBLE_FOR_FUNDED_REVIEW"
    assert payload["funded_eligibility"]["execution_authorized"] is False
    assert payload["execution_authorized"] is False


def test_text_output_and_report_are_consistent(tmp_path: Path) -> None:
    source = tmp_path / "plan.json"
    report = tmp_path / "reports" / "funded-plan.json"
    payload = _payload()
    eligibility = payload["funded_eligibility"]
    assert isinstance(eligibility, dict)
    eligibility["state"] = "EVIDENCE_INCOMPLETE"
    eligibility["reasons"] = ["PROVIDER_POLICY_BINDING_REQUIRED"]
    eligibility["provider_name"] = None
    eligibility["challenge_phase"] = None
    eligibility["provider_preset_sha256"] = None
    _write_payload(source, payload)

    result = runner.invoke(
        _app(),
        [
            "funded-plan-report",
            "--input",
            str(source),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "funded_state=EVIDENCE_INCOMPLETE" in result.output
    assert "blockers=1" in result.output
    assert "execution_authorized=false" in result.output
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["funded_eligibility"]["reasons"] == [
        "PROVIDER_POLICY_BINDING_REQUIRED"
    ]
    assert written["execution_authorized"] is False


def test_authorizing_payload_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "plan.json"
    _write_payload(source, _payload(execution_authorized=True))

    result = runner.invoke(
        _app(),
        ["funded-plan-report", "--input", str(source)],
    )

    assert result.exit_code != 0
    assert "must declare execution_authorized=false" in result.output


def test_nested_authorization_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "plan.json"
    payload = _payload()
    eligibility = payload["funded_eligibility"]
    assert isinstance(eligibility, dict)
    eligibility["execution_authorized"] = True
    _write_payload(source, payload)

    result = runner.invoke(
        _app(),
        ["funded-plan-report", "--input", str(source)],
    )

    assert result.exit_code != 0
    assert "invalid funded eligibility metadata" in result.output
