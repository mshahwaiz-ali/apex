from datetime import UTC, datetime

import pytest

from apex.risk import (
    ExposureState,
    RiskConfig,
    RiskDecision,
    RiskRejectionCode,
    analyze_phase6,
)
from apex.scoring import analyze_phase5
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    Phase4AnalysisResult,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ORDER = tuple(StrategyType)


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    current_price: float = 100.0,
    invalidation: float | None = None,
    target: float | None = None,
    extended: bool = False,
) -> TradeCandidate:
    if invalidation is None:
        invalidation = 98.0 if direction is TradeDirection.LONG else 102.0
    if target is None:
        target = 105.0 if direction is TradeDirection.LONG else 95.0
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=current_price,
            distance_from_current=abs(current_price - 100.0),
            atr_distance=abs(current_price - 100.0),
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("actionable entry",),
            is_extended=extended,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("thesis invalidated",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target,
                    label="TP1",
                    rationale=("structural target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.9,
            structure_quality=0.9,
            entry_quality=0.9,
            momentum_quality=0.9,
            volume_quality=0.9,
            liquidity_quality=0.9,
            target_space_quality=0.9,
        ),
        evidence=StrategyEvidence(supporting=("valid deterministic thesis",)),
        metadata={},
    )


def _phase5(candidate: TradeCandidate | None = None):  # type: ignore[no-untyped-def]
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=() if candidate is None else (candidate,),
        evaluated_strategies=ORDER,
    )
    return analyze_phase5(phase4)


def test_long_candidate_receives_controlled_risk_setup() -> None:
    result = analyze_phase6(_phase5(_candidate()))
    assert result.decision is RiskDecision.APPROVED
    assert result.setup is not None
    assert result.setup.stop_loss.price < result.setup.entry.lower
    assert result.setup.take_profits[0].price > result.setup.entry.upper
    assert result.setup.position_size.risk_amount == pytest.approx(50.0)
    assert result.setup.leverage.liquidation_price_at_maximum < result.setup.stop_loss.price


def test_short_candidate_is_directionally_symmetric() -> None:
    result = analyze_phase6(_phase5(_candidate(direction=TradeDirection.SHORT)))
    assert result.setup is not None
    assert result.setup.stop_loss.price > result.setup.entry.upper
    assert result.setup.take_profits[0].price < result.setup.entry.lower
    assert result.setup.leverage.liquidation_price_at_maximum > result.setup.stop_loss.price


def test_no_selected_candidate_remains_no_trade() -> None:
    result = analyze_phase6(_phase5())
    assert result.decision is RiskDecision.REJECTED
    assert result.rejection_codes == (RiskRejectionCode.NO_SELECTED_CANDIDATE,)


def test_extended_entry_is_rejected() -> None:
    result = analyze_phase6(_phase5(_candidate(extended=True)))
    assert result.rejection_codes == (RiskRejectionCode.ENTRY_TOO_EXTENDED,)


def test_stop_outside_configured_bounds_is_rejected() -> None:
    tight = analyze_phase6(_phase5(_candidate(invalidation=99.95)))
    wide = analyze_phase6(_phase5(_candidate(invalidation=90.0)))
    assert tight.rejection_codes == (RiskRejectionCode.STOP_TOO_TIGHT,)
    assert wide.rejection_codes == (RiskRejectionCode.STOP_TOO_WIDE,)


def test_insufficient_target_space_is_rejected() -> None:
    result = analyze_phase6(_phase5(_candidate(target=102.0)))
    assert result.rejection_codes == (RiskRejectionCode.INSUFFICIENT_TARGET_SPACE,)


def test_position_size_never_exceeds_configured_account_risk() -> None:
    config = RiskConfig(account_equity=20_000.0, risk_per_trade_pct=0.25)
    result = analyze_phase6(_phase5(_candidate()), config=config)
    assert result.setup is not None
    assert result.setup.position_size.risk_amount == pytest.approx(50.0)
    modeled_loss = result.setup.position_size.quantity * result.setup.stop_loss.distance
    assert modeled_loss == pytest.approx(50.0)


def test_exposure_limits_reject_new_trade() -> None:
    result = analyze_phase6(
        _phase5(_candidate()),
        exposure=ExposureState(open_trades=3, open_risk_amount=100.0),
    )
    assert RiskRejectionCode.MAX_CONCURRENT_TRADES in result.rejection_codes


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_configuration_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError):
        RiskConfig(account_equity=value)
