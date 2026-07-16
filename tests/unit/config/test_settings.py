from copy import deepcopy

import pytest

from apex.config import (
    DEFAULT_STRATEGY_ROUTING,
    DEFAULT_TIMEFRAME_RESAMPLING_SOURCES,
    DEFAULT_TIMEFRAME_ROLES,
    FileSettings,
    FuturesScreenerSettings,
)


def test_default_timeframe_roles_include_higher_context() -> None:
    settings = FileSettings(analysis_timeframes=["1m", "5m", "4h"])

    assert settings.timeframe_roles["1W"] == "long_term_macro"
    assert settings.timeframe_roles["3D"] == "swing"
    assert settings.timeframe_roles["4h"] == "macro"
    assert settings.timeframe_roles == DEFAULT_TIMEFRAME_ROLES
    assert settings.timeframe_resampling_sources == DEFAULT_TIMEFRAME_RESAMPLING_SOURCES
    assert settings.strategy_routing == DEFAULT_STRATEGY_ROUTING
    assert set(settings.strategy_routing) == {"enabled"}


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
    routing["enabled"] = ["not_a_strategy"]

    with pytest.raises(ValueError, match="unsupported strategy"):
        FileSettings(strategy_routing=routing)


def test_settings_reject_duplicate_strategy_route_member() -> None:
    routing = deepcopy(DEFAULT_STRATEGY_ROUTING)
    routing["enabled"] = ["trend_pullback", "trend_pullback"]

    with pytest.raises(ValueError, match="cannot contain duplicates"):
        FileSettings(strategy_routing=routing)


def test_default_futures_screener_settings_are_canonical() -> None:
    settings = FileSettings()

    assert settings.futures_screener == FuturesScreenerSettings(
        minimum_quote_volume_24h=5_000_000.0,
        maximum_spread_percentage=0.25,
        minimum_absolute_movement_percentage=1.0,
        shortlist_size=30,
    )

    domain_config = settings.futures_screener.to_domain()

    assert domain_config.minimum_quote_volume_24h == 5_000_000.0
    assert domain_config.maximum_spread_percentage == 0.25
    assert domain_config.minimum_absolute_movement_percentage == 1.0
    assert domain_config.shortlist_size == 30


def test_settings_accept_custom_futures_screener_values() -> None:
    settings = FileSettings(
        futures_screener=FuturesScreenerSettings(
            minimum_quote_volume_24h=25_000_000,
            maximum_spread_percentage=0.1,
            minimum_absolute_movement_percentage=3.5,
            shortlist_size=12,
        )
    )

    assert settings.futures_screener.minimum_quote_volume_24h == 25_000_000
    assert settings.futures_screener.maximum_spread_percentage == 0.1
    assert settings.futures_screener.minimum_absolute_movement_percentage == 3.5
    assert settings.futures_screener.shortlist_size == 12


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("minimum_quote_volume_24h", -1),
        ("maximum_spread_percentage", -1),
        ("minimum_absolute_movement_percentage", -1),
        ("shortlist_size", 0),
    ],
)
def test_settings_reject_invalid_futures_screener_values(
    field_name: str,
    value: float | int,
) -> None:
    screener = {
        "minimum_quote_volume_24h": 5_000_000,
        "maximum_spread_percentage": 0.25,
        "minimum_absolute_movement_percentage": 1.0,
        "shortlist_size": 30,
    }
    screener[field_name] = value

    with pytest.raises(ValueError):
        FuturesScreenerSettings.model_validate(screener)


def test_settings_reject_unknown_futures_screener_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        FuturesScreenerSettings.model_validate(
            {
                "minimum_quote_volume_24h": 5_000_000,
                "maximum_spread_percentage": 0.25,
                "minimum_absolute_movement_percentage": 1.0,
                "shortlist_size": 30,
                "unknown": True,
            }
        )
