from __future__ import annotations

from datetime import UTC, datetime

from apex.backtesting.contracts import BacktestSignal
from apex.domain.decision_volatility import (
    DecisionVolatilityClass,
    DecisionVolatilityProfile,
)
from apex.domain.volatility_risk import VolatilityClass, assess_volatility_risk
from apex.strategies import StrategyType, TradeDirection


def test_canonical_profile_overrides_fixed_atr_fallback() -> None:
    profile = DecisionVolatilityProfile(
        volatility_class=DecisionVolatilityClass.EXTREME,
        atr_pct=0.2,
        realized_range_pct=2.0,
        percentile=99.0,
        source="dynamic_symbol_profile",
        timeframe="5m",
        sample_size=100,
        baseline_bars=120,
        available=True,
    )
    signal = BacktestSignal(
        symbol="TEST/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=70.0,
        diagnostics={"decision_atr": 0.1},
        decision_volatility_profile=profile,
    )
    assessment = assess_volatility_risk(signal)
    assert assessment.volatility_class is VolatilityClass.EXTREME
    assert assessment.source == "dynamic_symbol_profile"
    assert assessment.authority == "observe_only"
