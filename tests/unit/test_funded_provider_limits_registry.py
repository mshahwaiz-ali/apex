from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from apex.funded.provider_limits_registry import (
    DrawdownModel,
    FundedProviderLimitPreset,
    FundedProviderLimitsRegistry,
)


def _preset(**overrides: object) -> FundedProviderLimitPreset:
    payload: dict[str, object] = {
        "provider_id": "EXAMPLE",
        "provider_name": "Example Funded",
        "challenge_phase": "PHASE_1",
        "verified_on": date(2026, 7, 1),
        "source_reference": "https://example.invalid/rules",
        "drawdown_model": DrawdownModel.STATIC,
        "external_daily_drawdown_limit_pct": 5.0,
        "external_total_drawdown_limit_pct": 10.0,
        "maximum_trades_per_day": 3,
        "weekend_trading_allowed": False,
        "overnight_holding_allowed": True,
        "news_trading_allowed": False,
        "limits_verified": True,
    }
    payload.update(overrides)
    return FundedProviderLimitPreset.model_validate(payload)


def test_preset_hash_is_deterministic_and_round_trips() -> None:
    preset = _preset()
    hashed = preset.with_verified_hash()

    assert len(preset.content_sha256) == 64
    assert hashed.preset_sha256 == preset.content_sha256
    assert FundedProviderLimitPreset.model_validate(hashed.model_dump()) == hashed


def test_preset_rejects_tampered_hash_and_invalid_geometry() -> None:
    with pytest.raises(ValidationError, match="hash does not match"):
        _preset(preset_sha256="0" * 64)

    with pytest.raises(ValidationError, match="daily drawdown limit cannot exceed"):
        _preset(
            external_daily_drawdown_limit_pct=11.0,
            external_total_drawdown_limit_pct=10.0,
        )


def test_registry_resolves_fresh_verified_preset_case_insensitively() -> None:
    preset = _preset().with_verified_hash()
    registry = FundedProviderLimitsRegistry(
        maximum_verification_age_days=30,
        presets=(preset,),
    )

    resolved = registry.preset_for(
        "example",
        "phase_1",
        as_of=date(2026, 7, 16),
    )

    assert resolved == preset
    assert resolved.to_readiness_limits().provider_name == "Example Funded"
    assert resolved.to_readiness_limits().limits_verified is True


def test_registry_rejects_stale_future_and_unverified_limits() -> None:
    stale_registry = FundedProviderLimitsRegistry(
        maximum_verification_age_days=10,
        presets=(_preset().with_verified_hash(),),
    )
    with pytest.raises(ValueError, match="stale or future-dated"):
        stale_registry.preset_for(
            "EXAMPLE",
            "PHASE_1",
            as_of=date(2026, 7, 16),
        )

    future_registry = FundedProviderLimitsRegistry(
        maximum_verification_age_days=30,
        presets=(_preset(verified_on=date(2026, 7, 20)).with_verified_hash(),),
    )
    with pytest.raises(ValueError, match="stale or future-dated"):
        future_registry.preset_for(
            "EXAMPLE",
            "PHASE_1",
            as_of=date(2026, 7, 16),
        )

    unverified_registry = FundedProviderLimitsRegistry(
        presets=(_preset(limits_verified=False).with_verified_hash(),),
    )
    with pytest.raises(ValueError, match="not verified"):
        unverified_registry.preset_for(
            "EXAMPLE",
            "PHASE_1",
            as_of=date(2026, 7, 16),
        )


def test_registry_rejects_duplicate_provider_phase_identity() -> None:
    with pytest.raises(ValidationError, match="unique provider and phase"):
        FundedProviderLimitsRegistry(
            presets=(
                _preset(),
                _preset(source_reference="https://example.invalid/rules-v2"),
            )
        )


def test_registry_can_resolve_stale_preset_for_offline_audit_only() -> None:
    preset = _preset().with_verified_hash()
    registry = FundedProviderLimitsRegistry(
        maximum_verification_age_days=1,
        presets=(preset,),
    )

    assert (
        registry.preset_for(
            "EXAMPLE",
            "PHASE_1",
            as_of=date(2026, 7, 16),
            require_fresh=False,
        )
        == preset
    )
