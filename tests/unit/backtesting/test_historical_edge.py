"""Tests for setup-specific historical edge aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting import (
    BacktestOutcome,
    BacktestSignal,
    EvidenceQuality,
    SimulatedTrade,
    aggregate_historical_edges,
    build_historical_edge_profile,
)
from apex.strategies import StrategyType, TradeDirection


def _trade(
    index: int,
    realized_r: float,
    *,
    symbol: str = "BTC/USDT",
    strategy: StrategyType = StrategyType.TREND_PULLBACK,
    direction: TradeDirection = TradeDirection.LONG,
    risk_mode: str = "STANDARD",
    confidence_score: float = 75.0,
    fees: float = 0.05,
    risk_amount: float = 1.0,
) -> SimulatedTrade:
    generated_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5)
    signal = BacktestSignal(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=99.0 if direction is TradeDirection.LONG else 101.0,
        target_price=102.0 if direction is TradeDirection.LONG else 98.0,
        quantity=1.0,
        risk_amount=risk_amount,
        confidence_score=confidence_score,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET if realized_r > 0.0 else BacktestOutcome.STOP,
        exit_time=generated_at + timedelta(minutes=15),
        exit_price=102.0 if realized_r > 0.0 else 99.0,
        gross_pnl=realized_r + fees,
        fees=fees,
        net_pnl=realized_r,
        realized_r_multiple=realized_r,
        holding_candles=3,
        metadata={
            "active_risk_mode": risk_mode,
            "market_regime": "trend",
            "entry_state": "READY_NOW",
        },
    )


def test_build_profile_calculates_r_metrics() -> None:
    profile = build_historical_edge_profile(
        (_trade(0, 2.0), _trade(1, -1.0), _trade(2, -0.5), _trade(3, 1.0))
    )

    assert profile.sample_size == 4
    assert profile.win_rate == pytest.approx(0.5)
    assert profile.loss_rate == pytest.approx(0.5)
    assert profile.average_r == pytest.approx(0.375)
    assert profile.median_r == pytest.approx(0.25)
    assert profile.profit_factor == pytest.approx(2.0)
    assert profile.maximum_drawdown_r == pytest.approx(1.5)
    assert profile.maximum_losing_streak == 2
    assert profile.average_holding_candles == pytest.approx(3.0)
    assert profile.average_execution_cost_r == pytest.approx(0.05)
    assert profile.evidence_quality is EvidenceQuality.INSUFFICIENT_SAMPLE


def test_aggregation_segments_deterministically() -> None:
    profiles = aggregate_historical_edges(
        (
            _trade(2, 1.0, symbol="ETH/USDT", risk_mode="AGGRESSIVE"),
            _trade(0, 1.0),
            _trade(1, -1.0),
        ),
        segment_by=("symbol", "risk_mode"),
    )

    assert tuple(dict(profile.dimensions) for profile in profiles) == (
        {"symbol": "BTC/USDT", "risk_mode": "STANDARD"},
        {"symbol": "ETH/USDT", "risk_mode": "AGGRESSIVE"},
    )
    assert tuple(profile.sample_size for profile in profiles) == (2, 1)


def test_score_band_is_derived_when_metadata_is_missing() -> None:
    profile = aggregate_historical_edges(
        (_trade(0, 1.0, confidence_score=83.0),),
        segment_by=("score_band",),
    )[0]

    assert profile.dimensions["score_band"] == "80_89"


@pytest.mark.parametrize(
    ("sample_size", "realized_r", "expected"),
    (
        (29, 1.0, EvidenceQuality.INSUFFICIENT_SAMPLE),
        (30, 1.0, EvidenceQuality.RESEARCH_ONLY),
        (99, 1.0, EvidenceQuality.RESEARCH_ONLY),
        (100, 1.0, EvidenceQuality.PROMISING),
        (249, 1.0, EvidenceQuality.PROMISING),
        (250, 1.0, EvidenceQuality.VALIDATED_BACKTEST),
        (100, -1.0, EvidenceQuality.DEGRADED),
        (250, -1.0, EvidenceQuality.REJECTED),
    ),
)
def test_evidence_thresholds(
    sample_size: int,
    realized_r: float,
    expected: EvidenceQuality,
) -> None:
    trades = tuple(_trade(index, realized_r) for index in range(sample_size))

    assert build_historical_edge_profile(trades).evidence_quality is expected


def test_external_validation_cannot_be_claimed_by_v1_1_profile() -> None:
    base = build_historical_edge_profile((_trade(0, 1.0),))

    with pytest.raises(ValueError, match="cannot claim external validation"):
        type(base)(
            dimensions=base.dimensions,
            sample_size=base.sample_size,
            win_rate=base.win_rate,
            loss_rate=base.loss_rate,
            breakeven_rate=base.breakeven_rate,
            average_r=base.average_r,
            median_r=base.median_r,
            expectancy=base.expectancy,
            profit_factor=base.profit_factor,
            maximum_drawdown_r=base.maximum_drawdown_r,
            maximum_losing_streak=base.maximum_losing_streak,
            average_holding_candles=base.average_holding_candles,
            average_execution_cost_r=base.average_execution_cost_r,
            evidence_quality=EvidenceQuality.PRODUCTION_ELIGIBLE,
        )


def test_empty_sample_and_duplicate_dimensions_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least one trade"):
        build_historical_edge_profile(())
    with pytest.raises(ValueError, match="must be unique"):
        aggregate_historical_edges((_trade(0, 1.0),), segment_by=("symbol", "symbol"))
