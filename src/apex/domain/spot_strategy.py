"""Provider-independent contracts for spot strategy evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_structure import SpotExtensionState, SpotTrendState


class SpotStrategy(StrEnum):
    HIGHER_TIMEFRAME_TREND_PULLBACK = "higher_timeframe_trend_pullback"
    BREAKOUT_RETEST = "breakout_retest"
    ACCUMULATION_RANGE_BREAKOUT = "accumulation_range_breakout"
    LIQUIDITY_SWEEP_DAILY_RECOVERY = "liquidity_sweep_daily_recovery"
    RELATIVE_STRENGTH_LEADER_PULLBACK = "relative_strength_leader_pullback"
    POST_CAPITULATION_RECOVERY = "post_capitulation_recovery"


class SpotStrategyDecision(StrEnum):
    APPROVE = "APPROVE"
    WATCH = "WATCH"
    REJECT = "REJECT"


class SpotStrategyEligibility(StrEnum):
    RESEARCH = "RESEARCH"
    PAPER_ONLY = "PAPER_ONLY"


class SpotStrategyInput(BaseModel):
    """Normalized structure outputs and measurable strategy setup features."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    current_price: float = Field(gt=0)
    market_regime: SpotMarketRegime
    allow_new_entries: bool
    structure_trend: SpotTrendState
    extension: SpotExtensionState
    support_price: float = Field(gt=0)
    resistance_price: float = Field(gt=0)
    demand_lower: float = Field(gt=0)
    demand_upper: float = Field(gt=0)
    relative_strength_percentage: float | None = None
    volume_ratio: float = Field(default=1.0, ge=0)
    pullback_depth_percentage: float | None = Field(default=None, ge=0)
    range_width_percentage: float | None = Field(default=None, ge=0)
    breakout_confirmed: bool = False
    retest_held: bool = False
    accumulation_confirmed: bool = False
    liquidity_sweep_confirmed: bool = False
    daily_recovery_confirmed: bool = False
    capitulation_recovery_confirmed: bool = False

    @model_validator(mode="after")
    def validate_geometry(self) -> Self:
        if self.support_price >= self.resistance_price:
            raise ValueError("spot support must be below resistance")
        if self.demand_lower > self.demand_upper:
            raise ValueError("spot demand lower must not exceed demand upper")
        return self


class SpotStrategyCandidate(BaseModel):
    """One deterministic strategy opinion without position sizing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: SpotStrategy
    decision: SpotStrategyDecision
    eligibility: SpotStrategyEligibility
    thesis: str = Field(min_length=1)
    invalidation_price: float = Field(gt=0)
    evidence: tuple[str, ...]
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class SpotStrategyRoutingResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selected: SpotStrategyCandidate | None
    candidates: tuple[SpotStrategyCandidate, ...]

    @model_validator(mode="after")
    def validate_selected_candidate(self) -> Self:
        if self.selected is not None and self.selected not in self.candidates:
            raise ValueError("selected spot strategy must be present in candidates")
        return self
