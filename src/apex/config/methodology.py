"""Validated methodology thresholds and ranking configuration."""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUIRED_GEOMETRY_LANES = frozenset(
    {
        "cmp_scalp",
        "confirmation_scalp",
        "pullback_scalp",
        "nearby_structured",
        "runner",
        "developing",
    }
)


class LaneGeometrySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_tp1_reward_to_risk: float = Field(gt=0)
    maximum_stop_distance_pct: float = Field(gt=0)
    minimum_target_quality: float = Field(ge=0, le=100)
    minimum_stop_distance_atr: float = Field(default=0.25, ge=0)
    minimum_stop_to_cost_ratio: float = Field(default=1.25, ge=0)
    maximum_tp1_distance_atr: float | None = Field(default=None, gt=0)


class ExecutionQualityCapSettings(BaseModel):
    """Validated hard caps applied to otherwise strong execution scores."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provisional_evidence: float = Field(default=0.65, ge=0, le=1)
    trigger_incomplete: float = Field(default=0.55, ge=0, le=1)
    data_stale: float = Field(default=0.25, ge=0, le=1)
    data_degraded: float = Field(default=0.50, ge=0, le=1)
    outside_entry_zone: float = Field(default=0.60, ge=0, le=1)
    chase_limit_violated: float = Field(default=0.20, ge=0, le=1)
    stop_infeasible: float = Field(default=0.00, ge=0, le=1)
    spread_slippage_unavailable: float = Field(default=0.75, ge=0, le=1)


class HtfConsequenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    countertrend_scalp_target_ceiling_r: float = Field(default=1.5, gt=0)
    reversal_attempt_target_ceiling_r: float = Field(default=2.0, gt=0)
    mixed_mild_target_ceiling_r: float = Field(default=2.5, gt=0)
    mixed_constrained_target_ceiling_r: float = Field(default=2.0, gt=0)


class PortfolioRankingWeightSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_precedence: float = Field(default=0.22, ge=0)
    tp1_reward_quality: float = Field(default=0.20, ge=0)
    target_quality: float = Field(default=0.12, ge=0)
    setup_quality: float = Field(default=0.12, ge=0)
    execution_quality: float = Field(default=0.12, ge=0)
    htf_alignment: float = Field(default=0.08, ge=0)
    timing_quality: float = Field(default=0.05, ge=0)
    data_confidence: float = Field(default=0.04, ge=0)
    overall_trade_quality: float = Field(default=0.05, ge=0)

    @model_validator(mode="after")
    def _validate_weight_total(self) -> Self:
        values = tuple(float(value) for value in self.model_dump().values())
        if not all(math.isfinite(value) for value in values):
            raise ValueError("portfolio ranking weights must be finite")
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("portfolio ranking weights must sum to 1.0")
        return self


def _default_lane_geometry() -> dict[str, LaneGeometrySettings]:
    return {
        "cmp_scalp": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.00,
            maximum_stop_distance_pct=2.0,
            minimum_target_quality=45.0,
            maximum_tp1_distance_atr=1.50,
        ),
        "confirmation_scalp": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.00,
            maximum_stop_distance_pct=2.0,
            minimum_target_quality=45.0,
            maximum_tp1_distance_atr=1.50,
        ),
        "pullback_scalp": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.20,
            maximum_stop_distance_pct=2.5,
            minimum_target_quality=50.0,
            maximum_tp1_distance_atr=2.00,
        ),
        "nearby_structured": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.25,
            maximum_stop_distance_pct=6.0,
            minimum_target_quality=50.0,
            maximum_tp1_distance_atr=3.00,
        ),
        "runner": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.80,
            maximum_stop_distance_pct=8.0,
            minimum_target_quality=60.0,
        ),
        "developing": LaneGeometrySettings(
            minimum_tp1_reward_to_risk=1.25,
            maximum_stop_distance_pct=6.0,
            minimum_target_quality=50.0,
        ),
    }


class MethodologySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane_geometry: dict[str, LaneGeometrySettings] = Field(default_factory=_default_lane_geometry)
    execution_quality_caps: ExecutionQualityCapSettings = Field(
        default_factory=ExecutionQualityCapSettings
    )
    htf_consequences: HtfConsequenceSettings = Field(default_factory=HtfConsequenceSettings)
    ranking_weights: PortfolioRankingWeightSettings = Field(
        default_factory=PortfolioRankingWeightSettings
    )

    @model_validator(mode="after")
    def _validate_lane_geometry(self) -> Self:
        configured = frozenset(self.lane_geometry)
        missing = sorted(REQUIRED_GEOMETRY_LANES - configured)
        unknown = sorted(configured - REQUIRED_GEOMETRY_LANES)
        if missing:
            raise ValueError(f"methodology lane geometry is missing lanes: {', '.join(missing)}")
        if unknown:
            raise ValueError(
                f"methodology lane geometry contains unsupported lanes: {', '.join(unknown)}"
            )
        return self


__all__ = [
    "REQUIRED_GEOMETRY_LANES",
    "ExecutionQualityCapSettings",
    "HtfConsequenceSettings",
    "LaneGeometrySettings",
    "MethodologySettings",
    "PortfolioRankingWeightSettings",
]
