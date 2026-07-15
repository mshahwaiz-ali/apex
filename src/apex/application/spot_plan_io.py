"""Typed JSON boundary for canonical spot planning requests and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_planning import (
    SpotPlanningRequest,
    SpotPlanningResult,
    build_spot_plan,
)
from apex.config.spot import SpotProductConfig, load_spot_product_config
from apex.domain.spot import SpotAccountInput
from