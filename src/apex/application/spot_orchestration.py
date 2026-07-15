"""Deterministic provider-independent S2-to-S4 spot orchestration bridge."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_analysis import (
    SpotAnalysisRequest,
    SpotAnalysisResult,
    analyze_spot_request,
)
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy import SpotStrategyInput
from apex.domain.spot_structure import SpotRegimeResult, SpotStructureResult


class SpotSetupEvidence(BaseModel):
    """Measurable setup evidence not derivable from structure classification alone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    volume_ratio: float | None = Field(default=None, ge=0)
    pullback_depth_percentage: float | None = Field(default=None, ge=0)
    range_width_percentage: float | None = Field(default=None, ge=0)
    breakout_confirmed: bool |