"""Tests for funded-plan evidence package CLI creation and verification."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from apex.cli_commands import funded_plan_package
from apex.funded import (
    DrawdownModel,
    ProviderPolicyBinding,
    build_funded_plan_evidence_package,
    write_funded_plan_evidence_package,
)

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    funded_plan_package.register_funded_plan_package_commands(app)
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


def _package():
    binding = _binding()
    return build_funded_plan_evidence_package(
        setup={"symbol": "BTCUSDT", "score": 88},
        account={"equity": 10000},
        account_policy={"type": "FUNDED"},
        account_state={"daily_loss_pct": 0.0},
        provider_binding=binding,
        futures_config={"margin_mode": "ISOLATED"},
        strategy_approval_config={"minimum_score": 75},
        funded_plan={
            "status": "APPROVED",
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
        generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )


def _creation_args(tmp_path: Path, output: Path) -> list[str]:
    args = ["funded-plan-package"]
    for option, name, content in (
        ("--setup", "setup.json", "{}\n"),
        ("--account", "account.json", "{}\n"),
        ("--policy", "policy.json", "{}\n"),
        ("--state", "state.json", "{}\n"),
        ("--provider-binding", "binding.json", "{}\n"),
        ("--futures-config", "futures.yaml", "{}\n"),
        ("--strategy-config", "strategy.yaml", "{}\n"),
    ):
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        args.extend((option, str(path)))
    args.extend(("--output", str(output)))
    return args


def _stub_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(funded_plan_package, "_load_model", lambda *args: object())
    monkeypatch.setattr(
        funded_plan_package,
        "load_futures_product_config",
        lambda *args: object(),
    )
    monkeypatch.setattr(
        funded_plan_package,
        "load_strategy_approval_config",
        lambda *args: object(),
    )
    monkeypatch.setattr(funded_plan_package, "_load_yaml_mapping", lambda *args: {})
    monkeypatch.setattr(
        funded_plan_package,
        "build_funded_futures_plan_result",
        lambda *args, **kwargs: {"execution_authorized": False},
    )
    monkeypatch.setattr(
        funded_plan_package,
        "build_funded_plan_evidence_package",
        lambda **kwargs: _package(),
    )


def test_package_command_creates_and_reloads_verified_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_creation(monkeypatch)
    output = tmp_path / "reports" / "package.json"

    result = runner.invoke(_app(), _creation_args(tmp_path, output))

    assert result.exit_code == 0, result.output
    assert "FUNDED_PLAN_PACKAGE_WRITTEN" in result.output
    assert "provider=Apex Test Funding" in result.output
    assert "phase=PHASE_1" in result.output
    assert "status=APPROVED" in result.output
    assert "eligibility=ELIGIBLE_FOR_FUNDED_REVIEW" in result.output
    assert "execution_authorized=false" in result.output
    assert output.read_bytes().endswith(b"\n")


def test_package_command_requires_force_to_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_creation(monkeypatch)
    output = tmp_path / "package.json"
    output.write_text("existing\n", encoding="utf-8")

    result = runner.invoke(_app(), _creation_args(tmp_path, output))

    assert result.exit_code != 0
    assert "output already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing\n"


def test_package_verify_command_accepts_valid_package(tmp_path: Path) -> None:
    input_path = tmp_path / "package.json"
    write_funded_plan_evidence_package(_package(), input_path)

    result = runner.invoke(
        _app(),
        ["funded-plan-package-verify", "--input", str(input_path)],
    )

    assert result.exit_code == 0, result.output
    assert "FUNDED_PLAN_PACKAGE_VERIFIED" in result.output
    assert "package_sha256=" in result.output
    assert "execution_authorized=false" in result.output


def test_package_verify_command_rejects_tampering(tmp_path: Path) -> None:
    input_path = tmp_path / "package.json"
    write_funded_plan_evidence_package(_package(), input_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload["account"]["equity"] = 1
    input_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = runner.invoke(
        _app(),
        ["funded-plan-package-verify", "--input", str(input_path)],
    )

    assert result.exit_code != 0
    assert "account_input_sha256" in result.output


def test_package_verify_command_rejects_malformed_package(tmp_path: Path) -> None:
    input_path = tmp_path / "package.json"
    input_path.write_text('{"schema_version": "1.0"}\n', encoding="utf-8")

    result = runner.invoke(
        _app(),
        ["funded-plan-package-verify", "--input", str(input_path)],
    )

    assert result.exit_code != 0
