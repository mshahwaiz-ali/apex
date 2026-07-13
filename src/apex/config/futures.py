"""Validated futures-only product configuration.

This module translates Phase 1 product decisions into configuration without
changing strategy or risk-engine behavior. Runtime integration can consume this
contract incrementally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain import LeverageMode, MarginMode, RiskMode


class RiskModeDefaults(BaseModel):
    """Default account-loss and leverage bounds for one risk mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_loss_percentage: float = Field(gt=0, le=100)
    minimum_leverage: float = Field(gt=0)
    preferred_leverage: float = Field(gt=0)
    maximum_leverage: float = Field(gt=0)
    maximum_wallet_exposure_percentage: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_leverage_order(self) -> Self:
        if not self.minimum_leverage <= self.preferred_leverage <= self.maximum_leverage:
            raise ValueError(
                "risk-mode leverage must satisfy minimum <= preferred <= maximum"
            )
        return self


class FuturesProductConfig(BaseModel):
    """Frozen Phase 1 futures product behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    futures_only: bool = True
    margin_mode: MarginMode = MarginMode.ISOLATED
    default_leverage_mode: LeverageMode = LeverageMode.AUTOMATIC
    default_risk_mode: RiskMode = RiskMode.AGGRESSIVE
    risk_modes: dict[RiskMode, RiskModeDefaults]

    @model_validator(mode="after")
    def validate_product_contract(self) -> Self:
        if not self.futures_only:
            raise ValueError("Apex Phase 1 must remain futures-only")
        if self.margin_mode is not MarginMode.ISOLATED:
            raise ValueError("Apex Phase 1 must use isolated margin")
        missing = set(RiskMode) - set(self.risk_modes)
        if missing:
            labels = ", ".join(sorted(mode.value for mode in missing))
            raise ValueError(f"missing risk-mode configuration: {labels}")
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
