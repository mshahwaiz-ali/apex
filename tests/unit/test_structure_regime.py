from apex.structure import (
    MarketRegime,
    RangeBoundarySide,
    RangeBreakoutState,
    RangeStructure,
    StructureAnalysisResult,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
    TrendStrength,
    classify_market_regime,
    range_boundaries,
    trend_strength_band,
)


def _trend(direction: TrendDirection, strength: float) -> TrendAnalysis:
    return TrendAnalysis(
        direction=direction,
        strength=strength,
        evidence=TrendEvidence(persistence=strength),
    )


def _range() -> RangeStructure:
    return RangeStructure(
        low=95.0,
        high=105.0,
        midpoint=100.0,
        width=10.0,
        width_percentage=0.1,
        start_index=0,
        end_index=20,
        upper_tests=3,
        lower_tests=2,
        breakout_state=RangeBreakoutState.NONE,
        current_position=0.5,
        quality=0.8,
    )


def test_strong_structural_trend_maps_to_strong_regime() -> None:
    result = StructureAnalysisResult(
        swings=(),
        trend=_trend(TrendDirection.STRONG_BULLISH, 0.9),
    )

    assert trend_strength_band(result.trend) is TrendStrength.STRONG
    assert classify_market_regime(result) is MarketRegime.STRONG_TREND


def test_validated_range_takes_range_regime() -> None:
    result = StructureAnalysisResult(
        swings=(),
        trend=_trend(TrendDirection.UNCERTAIN, 0.0),
        ranges=(_range(),),
    )

    assert classify_market_regime(result) is MarketRegime.RANGE


def test_transition_trend_maps_to_reversal_transition() -> None:
    result = StructureAnalysisResult(
        swings=(),
        trend=_trend(TrendDirection.TRANSITION, 0.5),
    )

    assert classify_market_regime(result) is MarketRegime.REVERSAL_TRANSITION


def test_range_boundaries_are_stably_lower_then_upper() -> None:
    lower, upper = range_boundaries(_range(), tolerance=0.002)

    assert lower.side is RangeBoundarySide.LOWER
    assert lower.price == 95.0
    assert lower.tests == 2
    assert upper.side is RangeBoundarySide.UPPER
    assert upper.price == 105.0
    assert upper.tests == 3
