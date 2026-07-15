"""Canonical research-only spot strategy and planning orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.spot_planning import SpotPlanningRequest, SpotPlanningResult, build_spot_plan
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy