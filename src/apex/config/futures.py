"""Validated futures product configuration.

Risk modes own trade aggressiveness. Account-level restrictions are defined in
``apex.domain.account`` and loaded separately so funded-account rules do not
become another risk mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain import LeverageMode, MarginMode, RiskMode


class RiskModeDefaults(BaseModel):
    """Canonical trade-risk defaults for the supported futures mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_loss_percentage: float = Field(gt=0, le=100)
    minimum_leverage: float = Field(default=1.0, ge=1.0, le=1.0)
    preferred_leverage: float = Field(ge=1.0)
    maximum_leverage: float = Field(ge=1.0)
    maximum_wallet_exposure_percentage: float = Field(gt=0, le=100)
    maximum_open_risk_percentage: float = Field(gt=0, le=100)
    maximum_daily_loss_percentage: float = Field(gt=0, le=100)
    maximum_consecutive_losses: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_leverage_order(self) -> Self:
        if not self.minimum_leverage <= self.preferred_leverage <= self.maximum_leverage:
            raise ValueError("risk-mode leverage must satisfy minimum <= preferred <= maximum")
        return self


class FuturesExecutionCostConfig(BaseModel):
    """Generic exchange-cost and liquidation assumptions for account plans."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_fee_percentage: float = Field(default=0.04, ge=0)
    exit_fee_percentage: float = Field(default=0.04, ge=0)
    entry_slippage_percentage: float = Field(default=0.03, ge=0)
    exit_slippage_percentage: float = Field(default=0.03, ge=0)
    maintenance_margin_percentage: float = Field(default=0.5, ge=0)
    liquidation_fee_buffer_percentage: float = Field(default=0.1, ge=0)
    minimum_stop_to_liquidation_buffer_percentage: float = Field(default=0.2, ge=0)

    @property
    def total_cost_fraction(self) -> float:
        return (
            self.entry_fee_percentage
            + self.exit_fee_percentage
            + self.entry_slippage_percentage
            + self.exit_slippage_percentage
        ) / 100.0


class FuturesProductConfig(BaseModel):
    """Validated futures product behavior and canonical risk-mode defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    futures_only: bool = True
    margin_mode: MarginMode = MarginMode.ISOLATED
    default_leverage_mode: LeverageMode = LeverageMode.AUTOMATIC
    default_risk_mode: RiskMode = RiskMode.STANDARD
    execution_costs: FuturesExecutionCostConfig = Field(default_factory=FuturesExecutionCostConfig)
    risk_modes: dict[RiskMode, RiskModeDefaults]

    @model_validator(mode="after")
    def validate_product_contract(self) -> Self:
        if not self.futures_only:
            raise ValueError("Apex futures product configuration must remain futures-only")
        if self.margin_mode is not MarginMode.ISOLATED:
            raise ValueError("Apex futures positions must use isolated margin")
        configured = set(self.risk_modes)
        required = set(RiskMode)
        missing = required - configured
        extra = configured - required
        if missing:
            labels = ", ".join(sorted(mode.value for mode in missing))
            raise ValueError(f"missing risk-mode configuration: {labels}")
        if extra:
            labels = ", ".join(sorted(str(mode) for mode in extra))
            raise ValueError(f"unsupported risk-mode configuration: {labels}")
        return self

    def defaults_for(self, risk_mode: RiskMode) -> RiskModeDefaults:
        """Return validated defaults for the selected account-risk mode."""

        return self.risk_modes[risk_mode]


def load_futures_product_config(path: str | Path) -> FuturesProductConfig:
    """Load the futures product contract from YAML."""

    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("futures configuration file must contain a mapping")
    return FuturesProductConfig.model_validate(raw)
