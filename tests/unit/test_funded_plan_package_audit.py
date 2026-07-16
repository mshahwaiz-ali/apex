"""Tests for funded-plan package inspection and deterministic indexing."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_plan_audit import register_funded_plan_audit_commands
from apex.funded import (
    DrawdownModel,
    ProviderPolicyBinding,
    build_funded_plan_audit_summary,
    build_funded_plan_evidence_package,
    build_funded_plan_package_index,
    load_and_verify_funded_plan_package_index,
    write_funded_plan_evidence_package,
    write_funded_plan_package_index,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_plan_audit_commands(app)
    return app


def _binding() -> ProviderPolicyBinding:
    return ProviderPolicyBinding(
        provider_id="APEX_TEST",
        provider_name="Apex Test Funding",
        challenge_phase="PHASE_1",
        preset_sha256="a" * 64,
        verification_date=date(2026, 7, 16),
        drawdown_model=DrawdownModel.STATIC,
        weekend_trading_allowed=False,
        overnight_holding_allowed=False,
        news_trading_allowed=False,
        compatible=True,
    )


def _package(*, generated_at: datetime, status: str = "APPROVED"):
    binding = _binding()
    return build_funded_plan_evidence_package(
        setup={"symbol": "BTCUSDT", "score": 88, "secret": "not-indexed"},
        account={"equity": 10000, "account_id": "private"},
        account_policy={"type": "FUNDED"},
        account_state={"daily_loss_pct": 0.0},
        provider_binding=binding,
        futures_config={"margin_mode": "ISOLATED"},
        strategy_approval_config={"minimum_score": 75},
        funded_plan={
            "status": status,
            "funded_eligibility": {
                "state": "ELIGIBLE_FOR_FUNDED_REVIEW",
                "reasons": [],
                "provider_name": binding.provider_name,
                "challenge_phase": binding.challenge_phase,
                "provider_preset_sha256": binding.preset_sha256,
                "execution_authorized": False,
            },
            "execution_authorized": False,
        },
        generated_at=generated_at,
    )


def test_audit_summary_is_redacted_and_non_authorizing() -> None:
    summary = build_funded_plan_audit_summary(
        _package(generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
    )
    payload = summary.model_dump(mode="json")

    assert summary.provider_name == "Apex Test Funding"
    assert summary.execution_authorized is False
    assert "setup" not in payload
    assert "account" not in payload
    assert "secret" not in json.dumps(payload)
    assert "private" not in json.dumps(payload)


def test_package_index_is_stable_and_chronological(tmp_path: Path) -> None:
    later = tmp_path / "later.json"
    earlier = tmp_path / "earlier.json"
    write_funded_plan_evidence_package(
        _package(generated_at=datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc)), later
    )
    write_funded_plan_evidence_package(
        _package(
            generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
            status="REJECTED",
        ),
        earlier,
    )

    generated_at = datetime(2026, 7, 16, 14, 0, tzinfo=timezone.utc)
    first = build_funded_plan_package_index([later, earlier], generated_at=generated_at)
    second = build_funded_plan_package_index([earlier, later], generated_at=generated_at)

    assert first.index_sha256 == second.index_sha256
    assert first.package_count == 2
    assert [entry.plan_status for entry in first.entries] == ["REJECTED", "APPROVED"]
    assert all(entry.execution_authorized is False for entry in first.entries)


def test_index_write_load_and_tamper_detection(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    index_path = tmp_path / "index.json"
    write_funded_plan_evidence_package(
        _package(generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)),
        package_path,
    )
    index = build_funded_plan_package_index(
        [package_path],
        generated_at=datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc),
    )
    write_funded_plan_package_index(index, index_path)

    assert load_and_verify_funded_plan_package_index(index_path) == index
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["entries"][0]["plan_status"] = "TAMPERED"
    index_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    try:
        load_and_verify_funded_plan_package_index(index_path)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered funded-plan package index was accepted")


def test_inspect_cli_writes_redacted_summary(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    output_path = tmp_path / "summary.json"
    write_funded_plan_evidence_package(
        _package(generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)),
        package_path,
    )

    result = runner.invoke(
        _app(),
        [
            "funded-plan-package-inspect",
            "--input",
            str(package_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "FUNDED_PLAN_PACKAGE_INSPECTED" in result.output
    assert "execution_authorized=false" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["execution_authorized"] is False
    assert "account" not in payload


def test_index_cli_builds_and_verifies_index(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    index_path = tmp_path / "index.json"
    write_funded_plan_evidence_package(
        _package(generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)),
        package_path,
    )

    created = runner.invoke(
        _app(),
        [
            "funded-plan-package-index",
            "--package",
            str(package_path),
            "--output",
            str(index_path),
        ],
    )
    verified = runner.invoke(
        _app(),
        ["funded-plan-package-index-verify", "--input", str(index_path)],
    )

    assert created.exit_code == 0, created.output
    assert verified.exit_code == 0, verified.output
    assert "packages=1" in created.output
    assert "execution_authorized=false" in verified.output
