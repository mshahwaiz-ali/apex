"""Focused tests for deterministic market-environment classification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apex.market_environment import (
    ExtensionState,
    MarketEnvironmentConfig,
    MarketRegime,
    TimeframeMarketSnapshot,
    VolatilityState,
    classify_timeframe_regime,
)


def _snapshot(**overrides: object) -> TimeframeMarketSnapshot:
    values: dict[str, object] = {
        "timeframe": "15m",
        "candle_timestamp": datetime(2026, 7, 16, tzinfo=UTC),
        "current_price": 105.0,
        "last_closed_price": 104.5,
        "recent_swing_high": 103.0,
        "recent_swing_low": 98.0,
        "trend_direction": "bullish",
        "ema_fast": 102.0,
        "ema_slow": 100.0,
        "ema_slope": None,
        "vwap": 101.0,
        "atr": 2.0,
        "candle_body_ratio": None,
        "upper_wick_ratio": None,
        "lower_wick_ratio": None,
        "volume": None,
        "relative_volume": 1.5,
        "rsi": 62.0,
        "macd_histogram": 0.4,
        "recent_high_break": False,
        "recent_low_break": False,
        "consolidation": False,
        "compression": False,
        "range_position": 0.7,
        "volatility_expansion": 1.0,
        "data_confidence": 1.0,
        "missing_data": (),
    }
    values.update(overrides)
    return TimeframeMarketSnapshot(**values)  # type: ignore[arg-type]


def test_clear_bullish_trend_is_deterministic() -> None:
    snapshot = _snapshot()

    first = classify_timeframe_regime(snapshot)
    second = classify_timeframe_regime(snapshot)

    assert first == second
    assert first.regime is MarketRegime.TREND_UP
    assert first.bullish_score > first.bearish_score
    assert first.reason_codes == ("TIMEFRAME_TREND_UP",)


def test_bearish_breakout_expansion() -> None:
    result = classify_timeframe_regime(
        _snapshot(
            current_price=95.0,
            last_closed_price=95.5,
            trend_direction="bearish",
            ema_fast=98.0,
            ema_slow=100.0,
            vwap=99.0,
            rsi=36.0,
            macd_histogram=-0.5,
            recent_high_break=False,
            recent_low_break=True,
            range_position=0.1,
            volatility_expansion=1.4,
        )
    )

    assert result.regime is MarketRegime.BREAKOUT_EXPANSION_DOWN
    assert result.volatility_state is VolatilityState.EXPANDING
    assert result.bearish_score > result.bullish_score


def test_squeeze_precedes_range_classification() -> None:
    result = classify_timeframe_regime(
        _snapshot(
            trend_direction="range",
            consolidation=True,
            compression=True,
            volatility_expansion=0.6,
            recent_swing_high=106.0,
            recent_swing_low=100.0,
        )
    )

    assert result.regime is MarketRegime.SQUEEZE
    assert result.volatility_state is VolatilityState.COMPRESSED


def test_higher_extension_warns_without_forcing_untradeable() -> None:
    result = classify_timeframe_regime(
        _snapshot(
            timeframe="4h",
            current_price=110.0,
            ema_fast=103.0,
            ema_slow=101.0,
            vwap=102.0,
            atr=2.0,
            rsi=76.0,
        )
    )

    assert result.regime is MarketRegime.EXHAUSTION_UP
    assert result.extension_state is ExtensionState.EXTREME
    assert "TIMEFRAME_EXTENSION_WARNING" in result.reason_codes


def test_low_confidence_is_untradeable() -> None:
    result = classify_timeframe_regime(_snapshot(data_confidence=0.25))

    assert result.regime is MarketRegime.UNTRADEABLE
    assert result.reason_codes[0] == "LOW_DATA_CONFIDENCE"


def test_unknown_configuration_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MarketEnvironmentConfig.model_validate({"unknown_threshold": 1})


def test_incomplete_weight_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing timeframe weights"):
        MarketEnvironmentConfig.model_validate({"timeframe_weights": {"1m": 1.0}})
