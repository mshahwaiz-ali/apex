"""Deterministic multi-symbol live spot scanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.spot_analysis import SpotAnalysisResult, spot_analysis_result_to_payload
from apex.application.spot_live import SpotLiveAccountInput, analyze_live_spot
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import Spot