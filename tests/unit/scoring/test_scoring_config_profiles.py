"""Tests for current Stage 3 strategy scoring configuration."""

from apex.scoring import DEFAULT_SCORING_CONFIG
from apex.scoring.config import QUALITY_COMPONENTS, StrategyProfile
from apex.strategies import StrategyType


def test_default_scoring_profiles_cover_current_strategy_types() -> None:
    assert set(DEFAULT_SCORING_CONFIG.strategy_profiles) == set(StrategyType)


def test_default_scoring_profiles_use_only_supported_neutral_metrics() -> None:
    supported = set(QUALITY_COMPONENTS)

    for profile in DEFAULT_SCORING_CONFIG.strategy_profiles.values():
        assert isinstance(profile, StrategyProfile)
        assert set(profile.neutral_metrics) <= supported
