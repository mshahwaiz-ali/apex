"""Verified provider-limit presets for funded-account readiness."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.funded.readiness import FundedProviderLimits

PROVIDER_LIMITS_REGISTRY_SCHEMA_VERSION = 1

__all__ = [
    "PROVIDER_LIMITS_REGISTRY_SCHEMA_VERSION",
    "DrawdownModel",
    "FundedProviderLimitPreset",
    "FundedProviderLimitsRegistry",
]


class DrawdownModel(StrEnum):
    """Supported externally imposed funded-account drawdown models."""

    STATIC = "STATIC"
    TRAILING = "TRAILING"
    END_OF_DAY_TRAILING = "END_OF_DAY_TRAILING"


class FundedProviderLimitPreset(BaseModel):
    """Date-stamped provider limits copied from a verified external source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    challenge_phase: str = Field(min_length=1)
    verified_on: date
    source_reference: str = Field(min_length=1)
    drawdown_model: DrawdownModel
    external_daily_drawdown_limit_pct: float = Field(gt=0, le=100)
    external_total_drawdown_limit_pct: float = Field(gt=0, le=100)
    maximum_trades_per_day: int = Field(gt=0)
    weekend_trading_allowed: bool
    overnight_holding_allowed: bool
    news_trading_allowed: bool
    limits_verified: bool = True
    preset_sha256: str | None = None

    @model_validator(mode="after")
    def validate_identity_and_hash(self) -> Self:
        normalized_id = self.provider_id.strip().upper()
        if normalized_id != self.provider_id:
            raise ValueError("provider_id must be normalized uppercase text")
        if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in normalized_id):
            raise ValueError("provider_id contains unsupported characters")
        if not self.provider_name.strip():
            raise ValueError("provider_name cannot be empty")
        if not self.challenge_phase.strip():
            raise ValueError("challenge_phase cannot be empty")
        if not self.source_reference.strip():
            raise ValueError("source_reference cannot be empty")
        if self.external_daily_drawdown_limit_pct > self.external_total_drawdown_limit_pct:
            raise ValueError("daily drawdown limit cannot exceed total drawdown limit")
        expected_hash = self.content_sha256
        if self.preset_sha256 is not None and self.preset_sha256 != expected_hash:
            raise ValueError("funded provider preset hash does not match its content")
        return self

    @property
    def content_sha256(self) -> str:
        """Return the deterministic hash excluding the stored hash field."""

        payload = self.model_dump(mode="json", exclude={"preset_sha256"})
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def with_verified_hash(self) -> FundedProviderLimitPreset:
        """Return an equivalent immutable preset containing its content hash."""

        return self.model_copy(update={"preset_sha256": self.content_sha256})

    def is_fresh(self, *, as_of: date, maximum_age_days: int) -> bool:
        """Return whether the external verification is not stale at ``as_of``."""

        if maximum_age_days < 0:
            raise ValueError("maximum provider-limit age cannot be negative")
        age_days = (as_of - self.verified_on).days
        return 0 <= age_days <= maximum_age_days

    def to_readiness_limits(self) -> FundedProviderLimits:
        """Convert this preset into the canonical funded-readiness contract."""

        return FundedProviderLimits(
            provider_name=self.provider_name,
            verified_on=self.verified_on,
            external_daily_drawdown_limit_pct=self.external_daily_drawdown_limit_pct,
            external_total_drawdown_limit_pct=self.external_total_drawdown_limit_pct,
            maximum_trades_per_day=self.maximum_trades_per_day,
            limits_verified=self.limits_verified,
        )


class FundedProviderLimitsRegistry(BaseModel):
    """Schema-versioned collection of verified provider-limit presets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = PROVIDER_LIMITS_REGISTRY_SCHEMA_VERSION
    maximum_verification_age_days: int = Field(default=30, ge=0)
    presets: tuple[FundedProviderLimitPreset, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        if self.schema_version != PROVIDER_LIMITS_REGISTRY_SCHEMA_VERSION:
            raise ValueError("unsupported funded provider-limits registry schema version")
        if not self.presets:
            raise ValueError("funded provider-limits registry cannot be empty")
        identities = tuple(
            (preset.provider_id, preset.challenge_phase.strip().upper()) for preset in self.presets
        )
        if len(identities) != len(set(identities)):
            raise ValueError("funded provider presets must have unique provider and phase identities")
        names = tuple(preset.provider_name.strip().casefold() for preset in self.presets)
        provider_ids_by_name: dict[str, set[str]] = {}
        for name, preset in zip(names, self.presets, strict=True):
            provider_ids_by_name.setdefault(name, set()).add(preset.provider_id)
        if any(len(provider_ids) > 1 for provider_ids in provider_ids_by_name.values()):
            raise ValueError("one provider name cannot map to multiple provider identifiers")
        return self

    def preset_for(
        self,
        provider_id: str,
        challenge_phase: str,
        *,
        as_of: date,
        require_fresh: bool = True,
    ) -> FundedProviderLimitPreset:
        """Resolve one verified provider/phase preset with optional freshness enforcement."""

        normalized_provider = provider_id.strip().upper()
        normalized_phase = challenge_phase.strip().upper()
        for preset in self.presets:
            if (
                preset.provider_id == normalized_provider
                and preset.challenge_phase.strip().upper() == normalized_phase
            ):
                if not preset.limits_verified:
                    raise ValueError("funded provider limits are not verified")
                if require_fresh and not preset.is_fresh(
                    as_of=as_of,
                    maximum_age_days=self.maximum_verification_age_days,
                ):
                    raise ValueError("funded provider limits are stale or future-dated")
                return preset
        raise ValueError(
            f"unknown funded provider preset: {normalized_provider}/{normalized_phase}"
        )
