"""Strict JSON boundary for provider-independent spot orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_analysis import (
    SpotAnalysisResult,
    spot_analysis_result_to_payload,
)
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    SpotSetupEvidence,
    analyze_spot_orchestration,
)
from apex.config.spot import SpotProductConfig, load_spot_product_config
from apex.config.spot_strategies import SpotStrategyConfig, load_spot_strategy_config
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_structure import SpotRegimeResult, SpotStructureResult

DEFAULT_SPOT_CONFIG_PATH = Path("config/spot