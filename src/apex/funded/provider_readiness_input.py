"""Prepare funded-readiness input from a verified provider preset."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from apex.domain import AccountPolicy
from apex.funded.provider_limits_persistence import (
    validate_provider_preset_against_policy,
)
from apex.funded.provider_limits_registry import FundedProviderLimitPreset

__all__ = [
    "prepare_funded_readiness_input",
    "write_funded_readiness_input",
]


def prepare_funded_readiness_input(
    template: Mapping[str, Any],
    *,
    preset: FundedProviderLimitPreset,
    policy: AccountPolicy,
) -> dict[str, Any]:
    """Return a JSON-ready R1 input with exact verified provider limits."""

    validate_provider_preset_against_policy(preset, policy)
    payload = _json_object(template)
    payload["provider_limits"] = {
        "provider_name": preset.provider_name,
        "verified_on": preset.verified_on.isoformat(),
        "external_daily_drawdown_limit_pct": preset.external_daily_drawdown_limit_pct,
        "external_total_drawdown_limit_pct": preset.external_total_drawdown_limit_pct,
        "maximum_trades_per_day": preset.maximum_trades_per_day,
        "limits_verified": preset.limits_verified,
    }
    payload["provider_verification"] = {
        "provider_id": preset.provider_id,
        "challenge_phase": preset.challenge_phase,
        "source_reference": preset.source_reference,
        "drawdown_model": preset.drawdown_model.value,
        "preset_sha256": preset.preset_sha256 or preset.content_sha256,
        "weekend_trading_allowed": preset.weekend_trading_allowed,
        "overnight_holding_allowed": preset.overnight_holding_allowed,
        "news_trading_allowed": preset.news_trading_allowed,
    }
    payload["account_policy_type"] = policy.type.value
    payload["execution_authorized"] = False
    return payload


def write_funded_readiness_input(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Persist a prepared R1 input atomically and verify exact JSON reload."""

    normalized = _json_object(payload)
    if normalized.get("execution_authorized") is not False:
        raise ValueError("prepared funded-readiness input cannot authorize execution")
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite funded-readiness input: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if loaded != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("prepared funded-readiness input changed after reload")


def _json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    loaded: object = json.loads(json.dumps(value))
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise TypeError("funded-readiness input template must be a JSON object")
    return cast(dict[str, Any], loaded)
