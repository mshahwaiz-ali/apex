from copy import deepcopy

import pytest

from apex.config import (
    DEFAULT_STRATEGY_ROUTING,
    DEFAULT_TIMEFRAME_RESAMPLING_SOURCES,
    DEFAULT_TIMEFRAME_ROLES,
    FileSettings,
)
from apex.domain import GainerStateThresholds


def test_default_timeframe_roles_include_higher_context() -> None:
    settings = FileSettings(analysis_timeframes=["1m", "5m", "4h"])

    assert settings.timeframe_roles["1W"] == "long_term_macro"
    assert settings.timeframe_roles["3D"] == "swing"
    assert settings.timeframe_roles["4h"] == "macro"
    assert settings.timeframe_roles == DEFAULT_TIMEFRAME_ROLES
    assert settings.timeframe_resampling_sources == DEFAULT_TIMEFRAME_RESAMPLING_SOURCES
    assert settings.strategy_routing == DEFAULT_STRATEGY_ROUTING
    assert settings.gainer_state_thresholds == GainerStateThresholds()


def test_settings_reject_missing_enabled_timeframe_role() -> None:
    with pytest.raises(ValueError, match="missing role configuration"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_roles={"4h": "macro"},
        )


def test_settings_reject_invalid_timeframe_role() -> None:
    with pytest.raises(ValueError, match="unsupported timeframe role"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_roles={"5m": "execution"},
        )


def test_settings_reject_duplicate_enabled_roles() -> None:
    with pytest.raises(ValueError, match="unique roles"):
        FileSettings(
            analysis_timeframes=["8h", "4h"],
            timeframe_roles={"8h": "macro", "4h": "macro"},
        )


def test_settings_reject_resampling_target_without_role() -> None:
    with pytest.raises(ValueError, match="resampling target lacks role"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_resampling_sources={"45m": "15m"},
        )


def test_settings_reject_resampling_source_that_is_not_lower() -> None:
    with pytest.raises(ValueError, match="target must be higher than source"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_resampling_sources={"2h": "4h"},
        )


def test_settings_reject_missing_enabled_timeframe_staleness_limit() -> None:
    with pytest.raises(ValueError, match="missing staleness configuration"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_max_staleness_seconds={"4h": 100},
        )


def test_settings_reject_negative_staleness_limit() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        FileSettings(
            analysis_timeframes=["5m"],
            timeframe_max_staleness_seconds={"5m": -1},
        )


def test_settings_reject_unknown_strategy_route() -> None:
    routing = deepcopy(DEFAULT_STRATEGY_ROUTING)
    routing["experimental"] = ["trend_pullback"]

    with pytest.raises(ValueError, match="unsupported strategy routing keys"):
        FileSettings(strategy_routing=routing)


def test_settings_reject_invalid_strategy_route_member() -> None:
    routing = deepcopy(DEFAULT_STRATEGY_ROUTING)
    routing["gainer"] = ["not_a_strategy"]

    with pytest.raises(ValueError, match="unsupported strategy"):
        FileSettings(strategy_routing=routing)


def test_settings_reject_duplicate_strategy_route_member() -> None:
    routing = deepcopy(DEFAULT_STRATEGY_ROUTING)
    routing["normal_market"] = ["trend_pullback", "trend_pullback"]

    with pytest.raises(ValueError, match="cannot contain duplicates"):
        FileSettings(strategy_routing=routing)


def test_settings_reject_invalid_gainer_threshold() -> None:
    with pytest.raises(ValueError, match="greater than or equal"):
        FileSettings(gainer_state_thresholds={"fresh_total_return_pct": -1})
