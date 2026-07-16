"""Tests for deterministic funded-plan evidence packages."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from apex.funded.plan_evidence_package import (
    build_funded_plan_evidence_package,
    canonical_sha256,
    load_and_verify_funded_plan_evidence_package,
    verify_funded_plan_evidence_package,
    write_funded_plan_evidence_package,
)
from apex.funded.provider_limits_registry import DrawdownModel
from apex.funded.provider_policy_binding import ProviderPolicyBinding


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
    plan = {
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
    }
    return build_funded_plan_evidence_package(
        setup={"symbol": "BTCUSDT", "score": 88},
        account={"equity": 10000},
        account_policy={"type": "FUNDED"},
        account_state={"daily_loss_pct": 0.0},
        provider_binding=binding,
        futures_config={"margin_mode": "ISOLATED"},
        strategy_approval_config={"minimum_score": 75},
        funded_plan=plan,
        generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )


def test_canonical_hash_is_order_independent() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_identical_inputs_produce_identical_package_hashes() -> None:
    assert _package().manifest.package_sha256 == _package().manifest.package_sha256


def test_one_field_tampering_is_detected() -> None:
    payload = _package().model_dump(mode="json")
    payload["account"]["equity"] = 9999

    with pytest.raises(ValueError, match="account_input_sha256"):
        verify_funded_plan_evidence_package(payload)


def test_provider_mismatch_is_rejected() -> None:
    payload = _package().model_dump(mode="json")
    payload["manifest"]["provider_name"] = "Other Provider"

    with pytest.raises(ValueError, match="provider"):
        verify_funded_plan_evidence_package(payload)


def test_authorization_claim_is_rejected() -> None:
    payload = _package().model_dump(mode="json")
    payload["funded_plan"]["execution_authorized"] = True

    with pytest.raises(ValueError):
        verify_funded_plan_evidence_package(payload)


def test_write_load_and_overwrite_protection(tmp_path: Path) -> None:
    output = tmp_path / "package.json"
    package = _package()
    write_funded_plan_evidence_package(package, output)

    assert output.read_bytes().endswith(b"\n")
    assert load_and_verify_funded_plan_evidence_package(output) == package
    with pytest.raises(FileExistsError, match="output already exists"):
        write_funded_plan_evidence_package(package, output)


def test_tampered_persisted_package_fails_verification(tmp_path: Path) -> None:
    output = tmp_path / "package.json"
    write_funded_plan_evidence_package(_package(), output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["setup"]["score"] = 1
    output.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="setup_sha256"):
        load_and_verify_funded_plan_evidence_package(output)
