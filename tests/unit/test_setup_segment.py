"""Canonical setup-segment identity tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.domain import RiskMode, ScannerMode
from apex.risk.contracts import (
    ActionableEntry,
    LeverageRange,
    ManagementPolicy,
    ManagementPolicyType,
    PositionSize,
    RiskApprovedSetup,
    StopLoss,
    TakeProfit,
)
from apex.scoring import SetupSegmentContext, SetupSegmentIdentity, score_band_for
from apex.strategies import StrategyType, TradeDirection


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "00_54"),
        (54.999, "00_54"),
        (55.0, "55_64"),
        (64.999, "55_64"),
        (65.0, "65_74"),
        (74.999, "65_74"),
        (75.0, "75_84"),
        (84.999, "75_84"),
        (85.0, "85_89"),
        (89.999, "85_89"),
        (90.0, "90_94"),
        (94.999, "90_94"),
        (95.0, "95_100"),
        (100.0, "95_100"),
    ],
)
def test_score_band_boundaries(score: float, expected: str) -> None:
    assert score_band_for(score) == expected


@pytest.mark.parametrize("score", [-0.001, 100.001, float("inf"), float("nan")])
def test_score_band_rejects_invalid_scores(score: float) -> None:
    with pytest.raises(ValueError):
        score_band_for(score)


def test_identity_is_derived_from_setup_and_account_mode() -> None:
    identity = SetupSegmentIdentity.from_setup(
        setup=_setup(),
        risk_mode=RiskMode.STANDARD,
        context=SetupSegmentContext(
            scanner_type=ScannerMode.NORMAL,
            market_regime=" Trend ",
        ),
    )

    assert dict(identity.to_dimensions()) == {
        "strategy": StrategyType.TREND_PULLBACK.value,
        "symbol": "BTCUSDT",
        "direction": TradeDirection.LONG.value,
        "risk_mode": RiskMode.STANDARD.value,
        "scanner_type": ScannerMode.NORMAL.value,
        "market_regime": "trend",
        "score_band": "85_89",
    }


def test_all_scanner_mode_cannot_identify_one_setup_segment() -> None:
    with pytest.raises(
        ValueError,
        match="must identify normal or gainers analysis",
    ):
        SetupSegmentContext(
            scanner_type=ScannerMode.ALL,
            market_regime="trend",
        )


def _setup() -> RiskApprovedSetup:
    return RiskApprovedSetup(
        symbol="btcusdt",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        decision_time=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        candidate_id="segment-fixture",
        confidence_score=85.0,
        entry=ActionableEntry(
            lower=100.0,
            upper=101.0,
            preferred=100.5,
            current_price=100.6,
            maximum_chase_price=101.5,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=98.0,
            distance=2.5,
            distance_pct=2.487562189054726,
            rationale=("structure invalidation",),
            quality_score=0.8,
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=103.0,
                reward=2.5,
                risk_reward=1.0,
                rationale=("first target",),
                partial_close_pct=60.0,
            ),
            TakeProfit(
                label="TP2",
                price=106.0,
                reward=5.5,
                risk_reward=2.2,
                rationale=("second target",),
                partial_close_pct=40.0,
            ),
        ),
        position_size=PositionSize(
            risk_amount=25.0,
            quantity=10.0,
            notional_value=1005.0,
            account_risk_pct=0.25,
            required_leverage=2.0,
        ),
        leverage=LeverageRange(
            minimum=1.0,
            maximum=5.0,
            modeled_maximum=10.0,
            liquidation_price_at_maximum=50.0,
            stop_to_liquidation_buffer_pct=48.0,
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.BREAKEVEN,
                trigger="TP1 reached",
                action="move stop to breakeven",
                rationale=("protect remainder",),
            ),
        ),
    )
