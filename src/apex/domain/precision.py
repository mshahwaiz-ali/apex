"""Precision-entry scoring contracts."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain.entry import EntryClassificationResult


class PrecisionEntryScore(BaseModel):
    """Entry-quality score separate from generic setup confidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    structural_quality: float = Field(ge=0, le=100)
    liquidity_quality: float = Field(ge=0, le=100)
    momentum_alignment: float = Field(ge=0, le=100)
    volatility_suitability: float = Field(ge=0, le=100)
    distance_from_ideal: float = Field(ge=0, le=100)
    extension_penalty: float = Field(ge=0, le=100)
    trap_penalty: float = Field(ge=0, le=100)
    spread_slippage_penalty: float = Field(ge=0, le=100)
    multi_timeframe_agreement: float = Field(ge=0, le=100)
    final_score: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_final_score(self) -> PrecisionEntryScore:
        expected = _weighted_final_score(
            structural_quality=self.structural_quality,
            liquidity_quality=self.liquidity_quality,
            momentum_alignment=self.momentum_alignment,
            volatility_suitability=self.volatility_suitability,
            distance_from_ideal=self.distance_from_ideal,
            extension_penalty=self.extension_penalty,
            trap_penalty=self.trap_penalty,
            spread_slippage_penalty=self.spread_slippage_penalty,
            multi_timeframe_agreement=self.multi_timeframe_agreement,
        )
        if abs(self.final_score - expected) > 1e-9:
            raise ValueError("precision final score must match configured component weights")
        return self


class PrecisionEntryPlan(BaseModel):
    """Actionable precision-entry view carried by analysis and scan outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_state: str
    entry_zone_low: float = Field(gt=0)
    entry_zone_high: float = Field(gt=0)
    ideal_entry: float = Field(gt=0)
    current_price: float = Field(gt=0)
    current_distance_from_ideal: float = Field(ge=0)
    current_distance_from_ideal_pct: float = Field(ge=0)
    maximum_chase_price: float = Field(gt=0)
    reclaim_trigger: float | None = Field(default=None, gt=0)
    retest_trigger: float | None = Field(default=None, gt=0)
    fast_failure_trigger: float | None = Field(default=None, gt=0)
    trigger_timeframes: tuple[str, ...] = ()
    trigger_state: str = "UNAVAILABLE"
    trigger_evidence: tuple[str, ...] = ()
    structural_invalidation: float = Field(gt=0)
    expected_time_to_entry: str
    actionability_explanation: str
    missing_data_warnings: tuple[str, ...] = ()
    score: PrecisionEntryScore
    classification: EntryClassificationResult

    @model_validator(mode="after")
    def validate_zone(self) -> PrecisionEntryPlan:
        if self.entry_zone_low > self.entry_zone_high:
            raise ValueError("precision entry-zone low cannot exceed high")
        if not self.entry_zone_low <= self.ideal_entry <= self.entry_zone_high:
            raise ValueError("precision ideal entry must remain inside the entry zone")
        if not math.isfinite(self.current_distance_from_ideal_pct):
            raise ValueError("precision distance percentage must be finite")
        return self


def weighted_precision_score(
    *,
    structural_quality: float,
    liquidity_quality: float,
    momentum_alignment: float,
    volatility_suitability: float,
    distance_from_ideal: float,
    extension_penalty: float,
    trap_penalty: float,
    spread_slippage_penalty: float,
    multi_timeframe_agreement: float,
) -> PrecisionEntryScore:
    """Build a validated weighted precision score."""

    return PrecisionEntryScore(
        structural_quality=structural_quality,
        liquidity_quality=liquidity_quality,
        momentum_alignment=momentum_alignment,
        volatility_suitability=volatility_suitability,
        distance_from_ideal=distance_from_ideal,
        extension_penalty=extension_penalty,
        trap_penalty=trap_penalty,
        spread_slippage_penalty=spread_slippage_penalty,
        multi_timeframe_agreement=multi_timeframe_agreement,
        final_score=_weighted_final_score(
            structural_quality=structural_quality,
            liquidity_quality=liquidity_quality,
            momentum_alignment=momentum_alignment,
            volatility_suitability=volatility_suitability,
            distance_from_ideal=distance_from_ideal,
            extension_penalty=extension_penalty,
            trap_penalty=trap_penalty,
            spread_slippage_penalty=spread_slippage_penalty,
            multi_timeframe_agreement=multi_timeframe_agreement,
        ),
    )


def _weighted_final_score(
    *,
    structural_quality: float,
    liquidity_quality: float,
    momentum_alignment: float,
    volatility_suitability: float,
    distance_from_ideal: float,
    extension_penalty: float,
    trap_penalty: float,
    spread_slippage_penalty: float,
    multi_timeframe_agreement: float,
) -> float:
    return max(
        0.0,
        min(
            100.0,
            structural_quality * 0.18
            + liquidity_quality * 0.12
            + momentum_alignment * 0.14
            + volatility_suitability * 0.10
            + distance_from_ideal * 0.18
            + multi_timeframe_agreement * 0.18
            - extension_penalty * 0.05
            - trap_penalty * 0.03
            - spread_slippage_penalty * 0.02,
        ),
    )
