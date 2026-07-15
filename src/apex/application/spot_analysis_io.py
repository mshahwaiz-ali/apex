"""Typed JSON boundary for canonical spot analysis requests and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_analysis import (
    SpotAnalysisRequest,
    SpotAnalysisResult,
    analyze_spot_request,
    spot_analysis_result_to_payload,
)
from apex.config.spot import