"""Typed JSON boundary for canonical spot analysis requests and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_analysis import (
    SpotAnalysisRequest,
    SpotAnalysisResult,
    analyze_spot_request,
    spot_analysis_result_to_payload,
)
from apex.config.spot import SpotProductConfig, load_spot_product_config
from apex.config.spot_strategies import SpotStrategyConfig, load_spot_strategy_config
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy import SpotStrategyInput

DEFAULT_SPOT_CONFIG_PATH = Path("config/spot.yaml")
DEFAULT_SPOT_STRATEGY_CONFIG_PATH = Path("config/spot_strategies.yaml")


class SpotAnalysisInput(BaseModel):
    """Validated transport input for one canonical spot analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_input: SpotStrategyInput
    account: SpotAccountInput
    support_price: float = Field(gt=0)
    resistance_price: float = Field(gt=0)
    deeper_support_price: float = Field(gt=0)
    recovery_entry_price: float = Field(gt=0)
    correlated_sector_exposure: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if self.support_price >= self.resistance_price:
            raise ValueError("spot support must be below resistance")
        if self.deeper_support_price >= min(
            self.strategy_input.current_price,
            self.support_price,
            self.recovery_entry_price,
        ):
            raise ValueError(
                "deeper spot support must be below current price, support, and recovery entry"
            )
        if self.recovery_entry_price > self.strategy_input.current_price:
            raise ValueError("spot recovery entry cannot exceed current price")
        return self

    def to_request(self) -> SpotAnalysisRequest:
        return SpotAnalysisRequest(
            strategy_input=self.strategy_input,
            account=self.account,
            support_price=self.support_price,
            resistance_price=self.resistance_price,
            deeper_support_price=self.deeper_support_price,
            recovery_entry_price=self.recovery_entry_price,
            correlated_sector_exposure=self.correlated_sector_exposure,
        )


def load_spot_analysis_input(path: str | Path) -> SpotAnalysisInput:
    """Load and validate a canonical spot analysis JSON object."""

    loaded: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("spot analysis input must contain a JSON object")
    return SpotAnalysisInput.model_validate(cast(dict[str, Any], loaded))


def analyze_spot_from_input(
    analysis_input: SpotAnalysisInput,
    *,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
) -> SpotAnalysisResult:
    """Run canonical spot analysis from validated transport input."""

    return analyze_spot_request(
        analysis_input.to_request(),
        product_config=product_config,
        strategy_config=strategy_config,
    )


def analyze_spot_from_files(
    *,
    input_path: str | Path,
    product_config_path: str | Path = DEFAULT_SPOT_CONFIG_PATH,
    strategy_config_path: str | Path = DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
) -> SpotAnalysisResult:
    """Load configs and input files, then run canonical spot analysis."""

    analysis_input = load_spot_analysis_input(input_path)
    product_config = load_spot_product_config(product_config_path)
    strategy_config = load_spot_strategy_config(strategy_config_path)
    return analyze_spot_from_input(
        analysis_input,
        product_config=product_config,
        strategy_config=strategy_config,
    )


def write_spot_analysis_result(path: str | Path, result: SpotAnalysisResult) -> None:
    """Write a deterministic canonical spot analysis payload."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(spot_analysis_result_to_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
