"""Deterministic provider-independent spot analysis and planning bridge."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_analysis import (
    SpotAnalysisRequest,
    SpotAnalysisResult,
    analyze_spot_request,
)
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy import SpotStrategyInput
from apex.domain.spot_structure import (
    SpotRegimeResult,
    SpotStructureResult,
    SpotTimeframeStructure,
    SpotZoneType,
)

_THESIS_TIMEFRAME_PRIORITY = {"1w": 5, "1d": 4, "12h": 3, "8h": 2, "4h": 1}


class SpotSetupEvidence(BaseModel):
    """Measurable setup evidence not derivable from structure alone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    volume_ratio: float | None = Field(default=None, ge=0)
    pullback_depth_percentage: float | None = Field(default=None, ge=0)
    range_width_percentage: float | None = Field(default=None, ge=0)
    breakout_confirmed: bool | None = None
    retest_held: bool | None = None
    accumulation_confirmed: bool | None = None
    liquidity_sweep_confirmed: bool | None = None
    daily_recovery_confirmed: bool | None = None
    capitulation_recovery_confirmed: bool | None = None


class SpotOrchestrationInput(BaseModel):
    """Canonical inputs for structure-to-strategy-to-plan orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    symbol: str = Field(min_length=1)
    current_price: float = Field(gt=0)
    structure: SpotStructureResult
    regime: SpotRegimeResult
    account: SpotAccountInput
    evidence: SpotSetupEvidence = SpotSetupEvidence()
    deeper_support_price: float = Field(gt=0)
    recovery_entry_price: float = Field(gt=0)
    current_sector_exposure_percentage: float = Field(
        default=0.0,
        ge=0,
        validation_alias=AliasChoices(
            "current_sector_exposure_percentage",
            "correlated_sector_exposure",
        ),
    )

    @property
    def correlated_sector_exposure(self) -> float:
        """Backward-compatible application alias for existing callers."""

        return self.current_sector_exposure_percentage

    @model_validator(mode="after")
    def validate_geometry(self) -> SpotOrchestrationInput:
        if not self.symbol.strip():
            raise ValueError("spot orchestration symbol cannot be blank")
        _validate_structure_geometry(self.structure)
        thesis = _select_thesis_timeframe(self.structure)
        if self.deeper_support_price >= min(
            thesis.support.lower,
            self.recovery_entry_price,
            self.current_price,
        ):
            raise ValueError(
                "deeper spot support must be below canonical support, recovery entry, and current price"
            )
        if self.recovery_entry_price > self.current_price:
            raise ValueError("spot recovery entry cannot exceed current price")
        return self


def build_spot_strategy_input(inputs: SpotOrchestrationInput) -> SpotStrategyInput:
    """Normalize canonical structure, regime, and explicit setup evidence."""

    thesis = _select_thesis_timeframe(inputs.structure)
    evidence = inputs.evidence
    return SpotStrategyInput(
        symbol=inputs.symbol,
        current_price=inputs.current_price,
        market_regime=inputs.regime.regime,
        allow_new_entries=inputs.regime.allow_new_entries,
        structure_trend=inputs.structure.trend,
        extension=inputs.structure.extension,
        support_price=thesis.support.lower,
        resistance_price=thesis.resistance.upper,
        demand_lower=thesis.demand.lower,
        demand_upper=thesis.demand.upper,
        relative_strength_percentage=inputs.structure.relative_strength_score,
        volume_ratio=evidence.volume_ratio if evidence.volume_ratio is not None else 0.0,
        pullback_depth_percentage=evidence.pullback_depth_percentage,
        range_width_percentage=evidence.range_width_percentage,
        breakout_confirmed=evidence.breakout_confirmed is True,
        retest_held=evidence.retest_held is True,
        accumulation_confirmed=evidence.accumulation_confirmed is True,
        liquidity_sweep_confirmed=evidence.liquidity_sweep_confirmed is True,
        daily_recovery_confirmed=evidence.daily_recovery_confirmed is True,
        capitulation_recovery_confirmed=evidence.capitulation_recovery_confirmed is True,
    )


def analyze_spot_orchestration(
    inputs: SpotOrchestrationInput,
    *,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig | None = None,
) -> SpotAnalysisResult:
    """Route canonical structure through strategies and bounded spot planning."""

    strategy_input = build_spot_strategy_input(inputs)
    return analyze_spot_request(
        SpotAnalysisRequest(
            strategy_input=strategy_input,
            account=inputs.account,
            support_price=strategy_input.support_price,
            resistance_price=strategy_input.resistance_price,
            deeper_support_price=inputs.deeper_support_price,
            recovery_entry_price=inputs.recovery_entry_price,
            correlated_sector_exposure=inputs.current_sector_exposure_percentage,
        ),
        product_config=product_config,
        strategy_config=strategy_config,
    )


def _validate_structure_geometry(structure: SpotStructureResult) -> None:
    if not structure.timeframes:
        raise ValueError("spot orchestration requires canonical timeframe structure")
    for timeframe in structure.timeframes:
        if timeframe.support.zone_type is not SpotZoneType.SUPPORT:
            raise ValueError("canonical support zone must use SUPPORT zone type")
        if timeframe.resistance.zone_type is not SpotZoneType.RESISTANCE:
            raise ValueError("canonical resistance zone must use RESISTANCE zone type")
        if timeframe.demand.zone_type is not SpotZoneType.DEMAND:
            raise ValueError("canonical demand zone must use DEMAND zone type")
        if timeframe.support.upper >= timeframe.resistance.lower:
            raise ValueError("canonical spot support must be below resistance")
        if timeframe.demand.lower > timeframe.demand.upper:
            raise ValueError("canonical spot demand lower bound cannot exceed upper bound")


def _select_thesis_timeframe(structure: SpotStructureResult) -> SpotTimeframeStructure:
    if not structure.timeframes:
        raise ValueError("spot orchestration requires canonical timeframe structure")
    return max(
        structure.timeframes,
        key=lambda item: (_THESIS_TIMEFRAME_PRIORITY.get(item.timeframe, 0), item.timeframe),
    )
