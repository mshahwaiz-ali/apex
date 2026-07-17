"""Strategy generation orchestration without regime pre-filtering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType

from apex.strategies.actionability import classify_candidate_actionability
from apex.strategies.applicability import (
    StrategyApplicability,
    build_strategy_app