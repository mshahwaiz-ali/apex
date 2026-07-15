"""Tests for canonical spot strategy and planning orchestration."""

from __future__ import annotations

from apex.application.spot_analysis import (
    SPOT_ANALYSIS_SCHEMA_VERSION,
    SpotAnalysisRequest,
    analyze_spot_request,
    spot_analysis_result_to_payload,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot