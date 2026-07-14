"""Deterministic S2 spot structure and regime classifiers."""

from __future__ import annotations

from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_structure import (
    SpotExtensionState,
    SpotPriceZone,
    SpotRegimeInput,
    SpotRegimeResult,
    SpotStructureResult,
    SpotStructureThresholds,
    SpotTimeframeSnapshot,
    SpotTimeframeStructure,
    SpotTrendState,
    SpotZoneType,
)


def classify_spot_timeframe(
    snapshot: SpotTimeframeSnapshot,
    *,
    thresholds: SpotStructureThresholds | None = None,
) -> SpotTimeframeStructure:
    config = thresholds or SpotStructureThresholds()
    if snapshot.timeframe not in config.approved_timeframes:
        raise ValueError(f"unsupported spot thesis timeframe: {snapshot.timeframe}")

    bullish = snapshot.close > snapshot.ema_fast > snapshot.ema_slow
    bearish = snapshot.close < snapshot.ema_fast < snapshot.ema_slow
    if bullish and snapshot.higher_high and snapshot.higher_low:
        trend = SpotTrendState.STRONG_UPTREND
    elif bullish or (snapshot.higher_high and snapshot.higher_low):
        trend = SpotTrendState.UPTREND
    elif bearish and snapshot.lower_high and snapshot.lower_low:
        trend = SpotTrendState.STRONG_DOWNTREND
    elif bearish or (snapshot.lower_high and snapshot.lower_low):
        trend = SpotTrendState.DOWNTREND
    else:
        trend = SpotTrendState.RANGE

    above_fast = (snapshot.close - snapshot.ema_fast) / snapshot.atr
    below_slow = (snapshot.ema_slow - snapshot.close) / snapshot.atr
    if above_fast >= config.terminal_extension_atr_multiple:
        extension = SpotExtensionState.TERMINAL
    elif above_fast >= config.extension_atr_multiple:
        extension = SpotExtensionState.EXTENDED
    elif below_slow >= config.downside_risk_atr_multiple:
        extension = SpotExtensionState.DOWNSIDE_RISK
    else:
        extension = SpotExtensionState.NORMAL

    width = snapshot.atr * config.zone_half_width_atr_multiple
    support = _zone(SpotZoneType.SUPPORT, snapshot.swing_low, width, snapshot.timeframe)
    resistance = _zone(SpotZoneType.RESISTANCE, snapshot.swing_high, width, snapshot.timeframe)
    demand = _zone(
        SpotZoneType.DEMAND,
        min(snapshot.ema_slow, snapshot.swing_low + snapshot.atr),
        width,
        snapshot.timeframe,
    )
    return SpotTimeframeStructure(
        timeframe=snapshot.timeframe,
        trend=trend,
        extension=extension,
        support=support,
        resistance=resistance,
        demand=demand,
        evidence=(f"trend={trend.value}", f"extension={extension.value}"),
    )


def analyze_spot_structure(
    snapshots: tuple[SpotTimeframeSnapshot, ...],
    *,
    thresholds: SpotStructureThresholds | None = None,
) -> SpotStructureResult:
    if not snapshots:
        raise ValueError("spot structure analysis requires at least one timeframe")
    if len({item.timeframe for item in snapshots}) != len(snapshots):
        raise ValueError("spot structure timeframes must be unique")

    config = thresholds or SpotStructureThresholds()
    items = tuple(classify_spot_timeframe(item, thresholds=config) for item in snapshots)
    trend_score = {
        SpotTrendState.STRONG_UPTREND: 2,
        SpotTrendState.UPTREND: 1,
        SpotTrendState.RANGE: 0,
        SpotTrendState.DOWNTREND: -1,
        SpotTrendState.STRONG_DOWNTREND: -2,
    }
    weights = {"1w": 5, "1d": 4, "12h": 3, "8h": 3, "4h": 2}
    score = sum(weights[item.timeframe] * trend_score[item.trend] for item in items)
    score /= sum(weights[item.timeframe] for item in items)
    if score >= 1.25:
        trend = SpotTrendState.STRONG_UPTREND
    elif score >= 0.35:
        trend = SpotTrendState.UPTREND
    elif score <= -1.25:
        trend = SpotTrendState.STRONG_DOWNTREND
    elif score <= -0.35:
        trend = SpotTrendState.DOWNTREND
    else:
        trend = SpotTrendState.RANGE

    severity = {
        SpotExtensionState.NORMAL: 0,
        SpotExtensionState.EXTENDED: 1,
        SpotExtensionState.DOWNSIDE_RISK: 2,
        SpotExtensionState.TERMINAL: 3,
    }
    extension = max(items, key=lambda item: severity[item.extension]).extension
    strengths = [item.relative_strength_percentage for item in snapshots if item.relative_strength_percentage is not None]
    relative_strength = sum(strengths) / len(strengths) if strengths else None
    return SpotStructureResult(
        trend=trend,
        extension=extension,
        timeframes=items,
        relative_strength_score=relative_strength,
        evidence=(f"weighted_trend_score={score:.3f}",),
    )


def classify_spot_market_regime(
    inputs: SpotRegimeInput,
    *,
    thresholds: SpotStructureThresholds | None = None,
) -> SpotRegimeResult:
    config = thresholds or SpotStructureThresholds()
    breadth = inputs.breadth.percentage_above_trend
    if breadth is None:
        total = inputs.breadth.observed_assets
        breadth = inputs.breadth.advancing_assets / total * 100 if total else 0.0

    if inputs.market_drawdown_percentage is not None and inputs.market_drawdown_percentage >= 20:
        return SpotRegimeResult(
            regime=SpotMarketRegime.CAPITULATION,
            allow_new_entries=False,
            evidence=("market drawdown reached capitulation threshold",),
        )
    if inputs.btc_extension is SpotExtensionState.DOWNSIDE_RISK or (
        inputs.btc_trend in {SpotTrendState.DOWNTREND, SpotTrendState.STRONG_DOWNTREND}
        and breadth <= config.risk_off_maximum_breadth_percentage
    ):
        return SpotRegimeResult(
            regime=SpotMarketRegime.RISK_OFF,
            allow_new_entries=False,
            evidence=("BTC structure and breadth are risk-off",),
        )
    if inputs.btc_trend in {SpotTrendState.UPTREND, SpotTrendState.STRONG_UPTREND}:
        regime = (
            SpotMarketRegime.RISK_ON
            if breadth >= config.risk_on_minimum_breadth_percentage
            else SpotMarketRegime.SELECTIVE_RISK_ON
        )
        return SpotRegimeResult(
            regime=regime,
            allow_new_entries=True,
            evidence=("BTC trend is constructive",),
        )
    if inputs.btc_return_percentage is not None and inputs.btc_return_percentage > 0:
        return SpotRegimeResult(
            regime=SpotMarketRegime.RECOVERY,
            allow_new_entries=True,
            evidence=("BTC return indicates early recovery",),
        )
    return SpotRegimeResult(
        regime=SpotMarketRegime.NEUTRAL,
        allow_new_entries=False,
        evidence=("broad-market confirmation is insufficient",),
    )


def _zone(
    zone_type: SpotZoneType,
    anchor: float,
    width: float,
    timeframe: str,
) -> SpotPriceZone:
    return SpotPriceZone(
        zone_type=zone_type,
        lower=max(anchor - width, anchor * 0.01),
        upper=anchor + width,
        source_timeframe=timeframe,
    )
