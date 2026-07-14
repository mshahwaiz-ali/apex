"""Validated strategy-specific futures approval thresholds.

This module owns the N3 strategy-quality configuration. Thresholds are
selected by canonical strategy and risk mode; unknown or incomplete
configuration fails validation rather than falling back silently.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.domain import RiskMode
from apex.strategies import StrategyType


class StrategyQualityClass(StrEnum):
    """Relative approval strictness for a futures strategy family."""

    PREFERRED = "PREFERRED"
    CONTROLLED = "CONTROLLED"
    RESTRICTED = "RESTRICTED"


class StrategyApprovalRule(BaseModel):
    """Approval thresholds for one canonical strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quality_class: StrategyQualityClass
    minimum_scores: dict[RiskMode, float]

    @model_validator(mode="after")
    def validate_risk_mode_thresholds(self) -> Self:
        configured = set(self.minimum_scores)
        required = set(RiskMode)
        missing = required - configured
        extra = configured - required
        if missing:
            labels = ", ".join(sorted(mode.value for mode in missing))
            raise ValueError(f"missing strategy approval risk modes: {labels}")
        if extra:
            labels = ", ".join(sorted(str(mode) for mode in extra))
            raise ValueError(f"unsupported strategy approval risk modes: {labels}")
        invalid = {
            mode: score
            for mode, score in self.minimum_scores.items()
            if not 0 <= score <= 100
        }
        if invalid:
            details = ", ".join(
                f"{mode.value}={score}" for mode, score in sorted(invalid.items(), key=lambda item: item[0].value)
            )
            raise ValueError(f"strategy approval scores must be between 0 and 100: {details}")
        return self

    def minimum_score_for(self, risk_mode: RiskMode) -> float:
        """Return the exact configured threshold for a risk mode."""

        return self.minimum_scores[risk_mode]


class StrategyApprovalConfig(BaseModel):
    """Complete strategy approval configuration for all futures strategies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategies: dict[StrategyType, StrategyApprovalRule]

    @model_validator(mode="after")
    def validate_strategy_coverage(self) -> Self:
        configured = set(self.strategies)
        required = set(StrategyType)
        missing = required - configured
        extra = configured - required
        if missing:
            labels = ", ".join(sorted(strategy.value for strategy in missing))
            raise ValueError(f"missing strategy approval configuration: {labels}")
        if extra:
            labels = ", ".join(sorted(str(strategy) for strategy in extra))
            raise ValueError(f"unsupported strategy approval configuration: {labels}")
        return self

    def rule_for(self, strategy: StrategyType) -> StrategyApprovalRule:
        """Return the validated rule for a canonical strategy."""

        return self.strategies[strategy]

    def minimum_score_for(self, strategy: StrategyType, risk_mode: RiskMode) -> float:
        """Return the deterministic strategy and risk-mode threshold."""

        return self.rule_for(strategy).minimum_score_for(risk_mode)


def load_strategy_approval_config(path: str | Path) -> StrategyApprovalConfig:
    """Load strategy approval thresholds from YAML."""

    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("strategy approval configuration file must contain a mapping")
    return StrategyApprovalConfig.model_validate(raw)
