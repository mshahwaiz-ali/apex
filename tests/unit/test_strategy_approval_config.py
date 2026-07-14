"""Tests for strategy-specific futures approval configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.config import (
    StrategyApprovalConfig,
    StrategyApprovalRule,
    StrategyQualityClass,
    load_strategy_approval_config,
)
from apex.domain import RiskMode
from apex.strategies import StrategyType


def _thresholds() -> dict[RiskMode, float]:
    return {
        RiskMode.STANDARD: 80.0,
        RiskMode.AGGRESSIVE: 72.0,
        RiskMode.EXTREME: 64.0,
    }


def _rule() -> StrategyApprovalRule:
    return StrategyApprovalRule(
        quality_class=StrategyQualityClass.CONTROLLED,
        minimum_scores=_thresholds(),
    )


def test_default_strategy_approval_configuration_loads() -> None:
    config = load_strategy_approval_config(Path("config/strategy_approval.yaml"))

    assert set(config.strategies) == set(StrategyType)
    assert config.rule_for(StrategyType.TREND_PULLBACK).quality_class is (
        StrategyQualityClass.PREFERRED
    )
    assert (
        config.minimum_score_for(
            StrategyType.BREAKOUT_CONTINUATION,
            RiskMode.STANDARD,
        )
        == 84.0
    )
    assert (
        config.minimum_score_for(
            StrategyType.MOMENTUM_GAINER_CONTINUATION,
            RiskMode.EXTREME,
        )
        == 70.0
    )


def test_all_risk_mode_thresholds_are_required() -> None:
    with pytest.raises(ValidationError, match="missing strategy approval risk modes"):
        StrategyApprovalRule(
            quality_class=StrategyQualityClass.PREFERRED,
            minimum_scores={RiskMode.STANDARD: 74.0},
        )


def test_thresholds_must_be_between_zero_and_one_hundred() -> None:
    invalid = _thresholds()
    invalid[RiskMode.STANDARD] = 101.0

    with pytest.raises(ValidationError, match="scores must be between 0 and 100"):
        StrategyApprovalRule(
            quality_class=StrategyQualityClass.RESTRICTED,
            minimum_scores=invalid,
        )


def test_all_canonical_strategies_are_required() -> None:
    with pytest.raises(ValidationError, match="missing strategy approval configuration"):
        StrategyApprovalConfig(strategies={StrategyType.TREND_PULLBACK: _rule()})


def test_unknown_strategy_is_rejected() -> None:
    payload = {
        "strategies": {
            strategy.value: {
                "quality_class": "CONTROLLED",
                "minimum_scores": {
                    "STANDARD": 80,
                    "AGGRESSIVE": 72,
                    "EXTREME": 64,
                },
            }
            for strategy in StrategyType
        }
    }
    payload["strategies"]["unknown_strategy"] = {
        "quality_class": "RESTRICTED",
        "minimum_scores": {
            "STANDARD": 90,
            "AGGRESSIVE": 80,
            "EXTREME": 70,
        },
    }

    with pytest.raises(ValidationError):
        StrategyApprovalConfig.model_validate(payload)


def test_threshold_lookup_is_deterministic() -> None:
    config = load_strategy_approval_config(Path("config/strategy_approval.yaml"))

    first = config.minimum_score_for(StrategyType.LIQUIDITY_REVERSAL, RiskMode.AGGRESSIVE)
    second = config.minimum_score_for(StrategyType.LIQUIDITY_REVERSAL, RiskMode.AGGRESSIVE)

    assert first == second == 71.0
