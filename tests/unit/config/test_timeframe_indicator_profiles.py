from __future__ import annotations

from apex.config.settings import (
    DEFAULT_TIMEFRAME_INDICATOR_PROFILES,
    DEFAULT_TIMEFRAME_ROLES,
    FileSettings,
)


def test_core_trading_timeframes_resolve_distinct_indicator_profiles() -> None:
    settings = FileSettings(analysis_timeframes=["1m", "3m", "5m", "15m", "30m", "1h", "4h"])
    profiles = {
        timeframe: settings.timeframe_indicator_profiles[settings.timeframe_roles[timeframe]]
        for timeframe in settings.analysis_timeframes
    }

    assert len({profile.model_dump_json() for profile in profiles.values()}) == 7
    assert profiles["1m"].ema_fast < profiles["5m"].ema_fast < profiles["4h"].ema_fast
    assert profiles["1m"].atr < profiles["5m"].atr <= profiles["4h"].atr
    assert profiles["1m"].range_lookback < profiles["15m"].range_lookback
    assert profiles["30m"].range_lookback < profiles["4h"].range_lookback


def test_default_role_mapping_preserves_timeframe_specific_authority() -> None:
    expected = {
        "1m": "timing",
        "3m": "refinement",
        "5m": "entry",
        "15m": "setup",
        "30m": "intraday",
        "1h": "intermediate",
        "4h": "macro",
    }
    assert {timeframe: DEFAULT_TIMEFRAME_ROLES[timeframe] for timeframe in expected} == expected


def test_all_default_indicator_profiles_respect_period_ordering() -> None:
    for profile in DEFAULT_TIMEFRAME_INDICATOR_PROFILES.values():
        assert profile.ema_fast < profile.ema_slow
        assert profile.macd_fast < profile.macd_slow
        assert profile.range_lookback <= 50
