import pytest

from apex.config import DEFAULT_TIMEFRAME_RESAMPLING_SOURCES, DEFAULT_TIMEFRAME_ROLES, FileSettings


def test_default_timeframe_roles_include_higher_context() -> None:
    settings = FileSettings(analysis_timeframes=["1m", "5m", "4h"])

    assert settings.timeframe_roles["1W"] == "long_term_macro"
    assert settings.timeframe_roles["3D"] == "swing"
    assert settings.timeframe_roles["4h"] == "macro"
    assert settings.timeframe_roles == DEFAULT_TIMEFRAME_ROLES
    assert settings.timeframe_resampling_sources == DEFAULT_TIMEFRAME_RESAMPLING_SOURCES


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
