from apex.application.spot_structure import (
    analyze_spot_structure,
    classify_spot_market_regime,
    classify_spot_timeframe,
)
from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_market import SpotMarketBreadthSnapshot
from apex.domain.spot_structure import (
    SpotExtensionState,
    SpotRegimeInput,
    SpotTimeframeSnapshot,
    SpotTrendState,
)


def _snapshot(timeframe: str, close: float = 120.0) -> SpotTimeframeSnapshot:
    return SpotTimeframeSnapshot(
        timeframe=timeframe,
        close=close,
        ema_fast=110.0,
        ema_slow=100.0,
        swing_high=125.0,
        swing_low=95.0,
        atr=5.0,
        higher_high=True,
        higher_low=True,
        lower_high=False,
        lower_low=False,
        relative_strength_percentage=4.0,
    )


def test_classifies_higher_timeframe_uptrend_and_zones() -> None:
    result = classify_spot_timeframe(_snapshot("1d"))

    assert result.trend is SpotTrendState.STRONG_UPTREND
    assert result.extension is SpotExtensionState.NORMAL
    assert result.support.lower < result.support.upper
    assert result.resistance.lower < result.resistance.upper
    assert result.demand.lower < result.demand.upper


def test_terminal_extension_is_detected() -> None:
    result = classify_spot_timeframe(_snapshot("4h", close=135.0))

    assert result.extension is SpotExtensionState.TERMINAL


def test_low_timeframe_dependency_is_rejected() -> None:
    snapshot = _snapshot("1m")

    try:
        classify_spot_timeframe(snapshot)
    except ValueError as error:
        assert "unsupported spot thesis timeframe" in str(error)
    else:
        raise AssertionError("1m spot thesis timeframe should be rejected")


def test_multi_timeframe_structure_uses_relative_strength() -> None:
    result = analyze_spot_structure(
        (_snapshot("1w"), _snapshot("1d"), _snapshot("12h"), _snapshot("4h"))
    )

    assert result.trend is SpotTrendState.STRONG_UPTREND
    assert result.relative_strength_score == 4.0


def test_risk_off_regime_blocks_new_entries() -> None:
    result = classify_spot_market_regime(
        SpotRegimeInput(
            btc_trend=SpotTrendState.STRONG_DOWNTREND,
            btc_extension=SpotExtensionState.DOWNSIDE_RISK,
            breadth=SpotMarketBreadthSnapshot(
                advancing_assets=10,
                declining_assets=90,
                percentage_above_trend=20.0,
            ),
        )
    )

    assert result.regime is SpotMarketRegime.RISK_OFF
    assert result.allow_new_entries is False


def test_risk_on_regime_allows_new_entries() -> None:
    result = classify_spot_market_regime(
        SpotRegimeInput(
            btc_trend=SpotTrendState.UPTREND,
            btc_extension=SpotExtensionState.NORMAL,
            breadth=SpotMarketBreadthSnapshot(
                advancing_assets=70,
                declining_assets=30,
                percentage_above_trend=70.0,
            ),
        )
    )

    assert result.regime is SpotMarketRegime.RISK_ON
    assert result.allow_new_entries is True
