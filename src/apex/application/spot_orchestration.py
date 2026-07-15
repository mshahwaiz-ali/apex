"""Deterministic provider-independent S2-to-S4 spot orchestration bridge."""

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

_THESIS_TIMEFRAME_PRIORITY = {"1w": 5, "1d": 4,