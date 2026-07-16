from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from apex.domain import AccountPolicy, AccountPolicyType
from apex.funded.provider_limits_persistence import (
    load_funded_provider_limits_registry,
    validate_provider_preset_against_policy,
    write_funded_provider_limits_registry,
)
from apex.funded.provider_limits_registry import (
    DrawdownModel,
    FundedProviderLimitPreset,
    FundedProviderLimitsRegistry,
)
from apex.funded.provider_readiness_input import (
    prepare_funded_readiness_input,
    write_funded_readiness_input,
)


def _preset() -> FundedProviderLimitPreset:
    return FundedProviderLimitPreset(
        provider_id="EXAMPLE",
        provider_name="Example Funded",
        challenge_phase="PHASE_1",
        verified_on=date(2026, 7, 1),
        source_reference="https://example.invalid/rules",
        drawdown_model=DrawdownModel.STATIC,
        external_daily_drawdown_limit_pct=5.0,
        external_total_drawdown_limit_pct=10.0,
        maximum_trades_per_day=3,
        weekend_trading_allowed=False,
        overnight_holding_allowed=True,
        news_trading_allowed=False,
        limits_verified=True,
    ).with_verified_hash()


def _registry() -> FundedProviderLimitsRegistry:
    return FundedProviderLimitsRegistry(
        maximum_verification_age_days=30,
        presets=(_preset(),),
    )


def _policy(**overrides: object) -> AccountPolicy:
    payload: dict[str, object] = {
        "type": AccountPolicyType.FUNDED,
        "provider_name": "Example Funded",
        "challenge_phase": "PHASE_1",
        "initial_balance": 50000.0,
        "external_daily_drawdown_limit_pct": 5.0,
        "external_total_drawdown_limit_pct": 10.0,
        "internal_daily_stop_pct": 1.0,
        "internal_total_drawdown_buffer_pct": 2.0,
        "maximum_risk_per_trade_pct": 0.25,
        "maximum_total_open_risk_pct": 0.75,
        "maximum_directional_exposure_pct": 20.0,
        "maximum_correlated_exposure_pct": 15.0,
        "maximum_trades_per_day": 3,
        "maximum_consecutive_losses": 2,
        "required_stop_loss": True,
        "weekend_trading_allowed": False,
        "allowed_sessions": (),
    }
    payload.update(overrides)
    return AccountPolicy.model_validate(payload)


def test_registry_json_round_trip_and_overwrite_protection(tmp_path: Path) -> None:
    output = tmp_path / "registry.json"
    registry = _registry()

    write_funded_provider_limits_registry(output, registry)
    assert load_funded_provider_limits_registry(output) == registry

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_funded_provider_limits_registry(output, registry)

    write_funded_provider_limits_registry(output, registry, force=True)
    assert load_funded_provider_limits_registry(output) == registry


def test_registry_loads_yaml_and_rejects_unknown_suffix(tmp_path: Path) -> None:
    registry = _registry()
    yaml_path = tmp_path / "registry.yaml"
    yaml_path.write_text(
        "schema_version: 1\n"
        "maximum_verification_age_days: 30\n"
        "presets:\n"
        f"  - provider_id: {registry.presets[0].provider_id}\n"
        f"    provider_name: {registry.presets[0].provider_name}\n"
        f"    challenge_phase: {registry.presets[0].challenge_phase}\n"
        f"    verified_on: '{registry.presets[0].verified_on.isoformat()}'\n"
        f"    source_reference: {registry.presets[0].source_reference}\n"
        f"    drawdown_model: {registry.presets[0].drawdown_model.value}\n"
        "    external_daily_drawdown_limit_pct: 5.0\n"
        "    external_total_drawdown_limit_pct: 10.0\n"
        "    maximum_trades_per_day: 3\n"
        "    weekend_trading_allowed: false\n"
        "    overnight_holding_allowed: true\n"
        "    news_trading_allowed: false\n"
        "    limits_verified: true\n"
        f"    preset_sha256: {registry.presets[0].preset_sha256}\n",
        encoding="utf-8",
    )
    assert load_funded_provider_limits_registry(yaml_path) == registry

    bad = tmp_path / "registry.txt"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="must be YAML or JSON"):
        load_funded_provider_limits_registry(bad)


def test_policy_compatibility_rejects_external_rule_conflicts() -> None:
    preset = _preset()
    validate_provider_preset_against_policy(preset, _policy())

    with pytest.raises(ValueError, match="provider does not match"):
        validate_provider_preset_against_policy(
            preset,
            _policy(provider_name="Other Provider"),
        )
    with pytest.raises(ValueError, match="daily drawdown limit differs"):
        validate_provider_preset_against_policy(
            preset,
            _policy(external_daily_drawdown_limit_pct=4.0),
        )
    with pytest.raises(ValueError, match="more daily trades"):
        validate_provider_preset_against_policy(
            preset,
            _policy(maximum_trades_per_day=4),
        )
    with pytest.raises(ValueError, match="weekend trading forbidden"):
        validate_provider_preset_against_policy(
            preset,
            _policy(weekend_trading_allowed=True),
        )


def test_prepared_readiness_input_contains_exact_provider_evidence(tmp_path: Path) -> None:
    preset = _preset()
    template = {
        "risk_mode": "STANDARD",
        "daily_lockout_verified": True,
        "total_buffer_verified": True,
    }
    payload = prepare_funded_readiness_input(
        template,
        preset=preset,
        policy=_policy(),
    )

    assert payload["provider_limits"]["provider_name"] == "Example Funded"
    assert payload["provider_limits"]["verified_on"] == "2026-07-01"
    assert payload["provider_verification"]["preset_sha256"] == preset.preset_sha256
    assert payload["account_policy_type"] == "FUNDED"
    assert payload["execution_authorized"] is False

    output = tmp_path / "readiness-input.json"
    write_funded_readiness_input(output, payload)
    assert json.loads(output.read_text(encoding="utf-8")) == payload

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_funded_readiness_input(output, payload)


def test_prepared_input_cannot_authorize_execution(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot authorize execution"):
        write_funded_readiness_input(
            tmp_path / "forbidden.json",
            {"execution_authorized": True},
        )
