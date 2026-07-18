"""Regression tests for entry-quality-first futures shortlisting."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.futures_screening import score_futures_opportunity
from apex.domain.futures_screening import (
    FuturesOpportunityFeatures,
    FuturesScreenerConfig,
    FuturesTickerSnapshot,
)


def _ticker() -> FuturesTickerSnapshot:
    return FuturesTickerSnapshot(
        symbol="TEST/USDT",
        exchange_symbol="TESTUSDT",
        last_price=100.0,
        bid_price=99.99,
        ask_price=100.01,
        quote_volume_24h=50_000_000.0,
        price_change_percentage_24h=6.0,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        source="test",
    )


def _features(
    *,
    ema_distance_atr: float,
    range_expansion: float,
    breakout_proximity: float,
    wick_intensity: float,
    current_participation: float,
) -> FuturesOpportunityFeatures:
    return FuturesOpportunityFeatures(
        return_5m_pct=0.4,
        return_15m_pct=0.9,
        return_30m_pct=1.4,
        return_1h_pct=2.2,
        relative_volume=1.6,
        volume_acceleration=1.4,
        atr_percentage=1.8,
        range_expansion=range_expansion,
        trend_slope_percentage=0.25,
        breakout_proximity=breakout_proximity,
        ema_distance_atr=ema_distance_atr,
        wick_intensity=wick_intensity,
        directional_persistence=0.67,
        current_participation=current_participation,
    )


def test_fresh_pullback_profile_outranks_overextended_mover() -> None:
    config = FuturesScreenerConfig(
        minimum_quote_volume_24h=5_000_000.0,
        maximum_spread_percentage=0.25,
        minimum_absolute_movement_percentage=1.0,
    )
    fresh = score_futures_opportunity(
        _ticker(),
        _features(
            ema_distance_atr=0.35,
            range_expansion=0.95,
            breakout_proximity=0.85,
            wick_intensity=0.15,
            current_participation=1.15,
        ),
        config,
    )
    extended = score_futures_opportunity(
        _ticker(),
        _features(
            ema_distance_atr=3.4,
            range_expansion=3.0,
            breakout_proximity=0.35,
            wick_intensity=0.55,
            current_participation=2.2,
        ),
        config,
    )

    assert fresh.total > extended.total
    assert fresh.entry_freshness > extended.entry_freshness
    assert fresh.structure_proximity > extended.structure_proximity
    assert fresh.noise_quality > extended.noise_quality
    assert any("overextension reduced shortlist score" in item for item in extended.cautions)


def test_default_weights_remain_normalized() -> None:
    config = FuturesScreenerConfig()
    assert abs(sum(config.weights.as_dict().values()) - 1.0) < 1e-9
