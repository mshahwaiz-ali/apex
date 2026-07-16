"""Persistence and policy-compatibility checks for funded provider limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

from apex.domain import AccountPolicy, AccountPolicyType
from apex.funded.provider_limits_registry import (
    FundedProviderLimitPreset,
    FundedProviderLimitsRegistry,
)

__all__ = [
    "load_funded_provider_limits_registry",
    "validate_provider_preset_against_policy",
    "write_funded_provider_limits_registry",
]


def load_funded_provider_limits_registry(path: Path) -> FundedProviderLimitsRegistry:
    """Load and fully validate a provider registry from YAML or JSON."""

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        value: object = yaml.safe_load(text)
    elif suffix == ".json":
        value = json.loads(text)
    else:
        raise ValueError("funded provider registry must be YAML or JSON")
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("funded provider registry must contain an object")
    return FundedProviderLimitsRegistry.model_validate(cast(dict[str, Any], value))


def write_funded_provider_limits_registry(
    path: Path,
    registry: FundedProviderLimitsRegistry,
    *,
    force: bool = False,
) -> None:
    """Persist a normalized JSON registry atomically and verify the complete reload."""

    if path.suffix.lower() != ".json":
        raise ValueError("funded provider registry output must be JSON")
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite funded provider registry: {path}")
    normalized = FundedProviderLimitsRegistry.model_validate(
        registry.model_dump(mode="json")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    if load_funded_provider_limits_registry(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("funded provider registry changed after reload")


def validate_provider_preset_against_policy(
    preset: FundedProviderLimitPreset,
    policy: AccountPolicy,
) -> None:
    """Reject a funded policy whose external limits contradict its provider preset."""

    if policy.type is not AccountPolicyType.FUNDED:
        raise ValueError("provider presets require a FUNDED account policy")
    if policy.provider_name is not None and (
        policy.provider_name.strip().casefold() != preset.provider_name.strip().casefold()
    ):
        raise ValueError("account policy provider does not match funded provider preset")
    if policy.challenge_phase is not None and (
        policy.challenge_phase.strip().casefold() != preset.challenge_phase.strip().casefold()
    ):
        raise ValueError("account policy challenge phase does not match provider preset")
    if (
        policy.external_daily_drawdown_limit_pct
        != preset.external_daily_drawdown_limit_pct
    ):
        raise ValueError("account policy daily drawdown limit differs from provider preset")
    if (
        policy.external_total_drawdown_limit_pct
        != preset.external_total_drawdown_limit_pct
    ):
        raise ValueError("account policy total drawdown limit differs from provider preset")
    if policy.maximum_trades_per_day > preset.maximum_trades_per_day:
        raise ValueError("account policy permits more daily trades than provider preset")
    if policy.weekend_trading_allowed and not preset.weekend_trading_allowed:
        raise ValueError("account policy permits weekend trading forbidden by provider preset")
