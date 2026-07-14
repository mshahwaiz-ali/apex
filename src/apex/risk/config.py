"""Validated configuration for the deterministic Phase 6 risk engine.

``RiskConfig`` remains the compatibility contract consumed by the existing
Phase-6 setup engine. Runtime account and futures limits are resolved from the
canonical futures risk-mode and account-policy configuration files instead of
being duplicated in ``config/risk.yaml``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml

from apex.config.account_policies import load_account_policies_config
from apex.config.futures import load_futures_product_config
from apex.domain.futures import RiskMode

DEFAULT_FUTURES_CONFIG_PATH = Path("config/futures.yaml")
DEFAULT_ACCOUNT_POLICIES_PATH = Path("config/account_policies.yaml")


class RiskProfile(StrEnum):
    CONTROLLED = "controlled"
    AGGRESSIVE = "aggressive"
    EXTREME = "extreme"

    @property
    def risk_mode(self) -> RiskMode:
        if self is RiskProfile.CONTROLLED:
            return RiskMode.STANDARD
        return RiskMode(self.value.upper())


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Compatibility view combining setup geometry with canonical risk limits."""

    identifier: str = "phase6-standard-v2"
    profile: RiskProfile = RiskProfile.CONTROLLED
    account_equity: float = 10_000.0
    risk_per_trade_pct: float = 0.25
    minimum_risk_reward: float = 1.5
    minimum_stop_distance_pct: float = 0.15
    maximum_stop_distance_pct: float = 3.0
    structural_stop_buffer_pct: float = 0.05
    maximum_entry_chase_pct: float = 0.25
    maximum_leverage: float = 5.0
    maintenance_margin_pct: float = 0.5
    liquidation_buffer_ratio: float = 0.35
    maximum_concurrent_trades: int = 3
    maximum_open_risk_pct: float = 0.75
    maximum_directional_risk_pct: float = 0.30
    maximum_correlated_risk_pct: float = 0.25
    maximum_daily_loss_pct: float = 1.0
    maximum_consecutive_losses: int = 2

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> Self:
        """Build validated risk configuration from fully resolved values."""

        values = dict(values)
        if "profile" in values:
            values["profile"] = RiskProfile(values["profile"])
        allowed = {field.name for field in fields(cls)}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown risk configuration fields: {sorted(unknown)}")
        return cls(**values)

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("risk configuration identifier cannot be empty")
        if not isinstance(self.profile, RiskProfile):
            raise ValueError("risk profile must be a valid RiskProfile")
        for name in (
            "account_equity",
            "risk_per_trade_pct",
            "minimum_risk_reward",
            "minimum_stop_distance_pct",
            "maximum_stop_distance_pct",
            "structural_stop_buffer_pct",
            "maximum_entry_chase_pct",
            "maximum_leverage",
            "maintenance_margin_pct",
            "liquidation_buffer_ratio",
            "maximum_open_risk_pct",
            "maximum_directional_risk_pct",
            "maximum_correlated_risk_pct",
            "maximum_daily_loss_pct",
        ):
            _positive(name.replace("_", " "), getattr(self, name))
        if self.minimum_stop_distance_pct >= self.maximum_stop_distance_pct:
            raise ValueError("minimum stop distance must be below maximum stop distance")
        if self.maximum_leverage < 1.0:
            raise ValueError("maximum leverage cannot be below one")
        if self.maximum_concurrent_trades < 1:
            raise ValueError("maximum concurrent trades must be positive")
        if self.maximum_consecutive_losses < 1:
            raise ValueError("maximum consecutive losses must be positive")
        if self.risk_per_trade_pct > self.maximum_open_risk_pct:
            raise ValueError("per-trade risk cannot exceed maximum open risk")
        if self.risk_per_trade_pct > self.maximum_directional_risk_pct:
            raise ValueError("per-trade risk cannot exceed maximum directional risk")
        if self.risk_per_trade_pct > self.maximum_correlated_risk_pct:
            raise ValueError("per-trade risk cannot exceed maximum correlated risk")


@dataclass(frozen=True, slots=True)
class ExposureState:
    open_trades: int = 0
    open_risk_amount: float = 0.0
    same_direction_risk_amount: float = 0.0
    correlated_risk_amount: float = 0.0
    daily_realized_loss: float = 0.0
    consecutive_losses: int = 0

    def __post_init__(self) -> None:
        if self.open_trades < 0 or self.consecutive_losses < 0:
            raise ValueError("exposure counters cannot be negative")
        for name in (
            "open_risk_amount",
            "same_direction_risk_amount",
            "correlated_risk_amount",
            "daily_realized_loss",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        if self.same_direction_risk_amount > self.open_risk_amount:
            raise ValueError("same-direction risk cannot exceed total open risk")
        if self.correlated_risk_amount > self.open_risk_amount:
            raise ValueError("correlated risk cannot exceed total open risk")


def _load_mapping(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("risk configuration file must contain a mapping")
    return dict(raw)


def load_risk_config(
    path: str | Path,
    *,
    futures_config_path: str | Path = DEFAULT_FUTURES_CONFIG_PATH,
    account_policies_path: str | Path = DEFAULT_ACCOUNT_POLICIES_PATH,
    account_policy_name: str | None = None,
) -> RiskConfig:
    """Load setup geometry and inject canonical mode and account-policy limits."""

    raw = _load_mapping(path)
    profile = RiskProfile(raw.get("profile", RiskProfile.CONTROLLED.value))
    futures = load_futures_product_config(futures_config_path)
    mode_defaults = futures.defaults_for(profile.risk_mode)
    policies = load_account_policies_config(account_policies_path)
    policy = policies.policy_for(account_policy_name)

    canonical_values: dict[str, Any] = {
        "profile": profile,
        "risk_per_trade_pct": mode_defaults.account_loss_percentage,
        "maximum_leverage": mode_defaults.maximum_leverage,
        "maintenance_margin_pct": futures.execution_costs.maintenance_margin_percentage,
        "maximum_concurrent_trades": policy.maximum_trades_per_day,
        "maximum_open_risk_pct": min(
            mode_defaults.maximum_open_risk_percentage,
            policy.maximum_total_open_risk_pct,
        ),
        "maximum_directional_risk_pct": policy.maximum_directional_exposure_pct,
        "maximum_correlated_risk_pct": policy.maximum_correlated_exposure_pct,
        "maximum_daily_loss_pct": min(
            mode_defaults.maximum_daily_loss_percentage,
            policy.internal_daily_stop_pct,
        ),
        "maximum_consecutive_losses": min(
            mode_defaults.maximum_consecutive_losses,
            policy.maximum_consecutive_losses,
        ),
    }
    conflicting = set(raw).intersection(canonical_values) - {"profile"}
    if conflicting:
        labels = ", ".join(sorted(conflicting))
        raise ValueError(
            "risk configuration duplicates canonical futures/account-policy fields: " + labels
        )
    return RiskConfig.from_mapping({**raw, **canonical_values})


DEFAULT_RISK_CONFIG = RiskConfig()
