from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apex.domain.futures import RiskMode
from apex.risk import (
    ExposureState,
    ManagementPolicyType,
    RiskConfig,
    RiskDecision,
    RiskRejectionCode,
    StopQualityBand,
    analyze_risk,
    load_risk_config,
    resolve_risk_config_for_mode,
)
from apex.scoring import (
    CandidateOutcome,
    ConflictSummary,
    DirectionalConsensus,
    CandidateSelectionResult,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
    analyze_candidate_selection,
)
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
    entry_lower: float = 99.0,
    entry_upper: float = 101.0,
    invalidation: float | None = None,
    target: float | None = None,
    extended: bool = False,
) -> TradeCandidate:
    if invalidation is None:
        invalidation = 98.0 if direction is TradeDirection.LONG else 102.0
    if target is None:
        target = 105.0 if direction is TradeDirection.LONG else 95.0
    preferred = (entry_lower + entry_upper) / 2.0
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_lower,
            upper=entry_upper,
            preferred=preferred,
            current_price=current_price,
            distance_from_current=abs(current_price - preferred),
            atr_distance=abs(current_price - preferred),
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


def _phase5(candidate: TradeCandidate | None = None) -> CandidateSelectionResult:
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=() if candidate is None else (candidate,),
        evaluated_strategies=ORDER,
    )
    return analyze_candidate_selection(phase4)


def _scored(candidate_id: str, candidate: TradeCandidate) -> ScoredCandidate:
    return ScoredCandidate(
        candidate_id=candidate_id,
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points={"base": 85.0},
            penalty_points={},
            base_score=85.0,
            total_penalty=0.0,
            final_score=85.0,
        ),
        normalized_metrics={"quality": 0.85},
    )


def _ranked(candidate_id: str, candidate: TradeCandidate, rank: int) -> RankedCandidate:
    return RankedCandidate(
        scored=_scored(candidate_id, candidate),
        rank=rank,
        outcome=CandidateOutcome.ACCEPTED,
        reasons=(),
        tie_break=(candidate_id,),
    )


def test_long_candidate_receives_controlled_risk_setup() -> None:
    result = analyze_risk(_phase5(_candidate()))
    assert result.decision is RiskDecision.APPROVED
    assert result.setup is not None
    assert result.setup.stop_loss.price < result.setup.entry.lower
    assert result.setup.stop_loss.quality_band in {
        StopQualityBand.STRONG,
        StopQualityBand.ACCEPTABLE,
    }
    assert 0.0 <= result.setup.stop_loss.quality_score <= 1.0
    assert result.setup.take_profits[0].price > result.setup.entry.upper
    assert sum(target.partial_close_pct for target in result.setup.take_profits) == pytest.approx(
        100.0
    )
    assert tuple(policy.kind for policy in result.setup.management_policies) == (
        ManagementPolicyType.BREAKEVEN,
        ManagementPolicyType.TRAILING,
        ManagementPolicyType.TIME_EXIT,
        ManagementPolicyType.MOMENTUM_FAILURE,
    )
    assert result.setup.position_size.risk_amount == pytest.approx(25.0)
    assert result.setup.position_size.required_leverage <= result.setup.leverage.maximum
    assert result.setup.leverage.liquidation_price_at_maximum < result.setup.stop_loss.price


def test_short_candidate_is_directionally_symmetric() -> None:
    result = analyze_risk(_phase5(_candidate(direction=TradeDirection.SHORT)))
    assert result.setup is not None
    assert result.setup.stop_loss.price > result.setup.entry.upper
    assert result.setup.take_profits[0].price < result.setup.entry.lower
    assert result.setup.take_profits[0].partial_close_pct == pytest.approx(100.0)
    assert result.setup.leverage.liquidation_price_at_maximum > result.setup.stop_loss.price


def test_multiple_targets_receive_deterministic_partial_closes() -> None:
    candidate = _candidate(target=104.0)
    candidate = replace(
        candidate,
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.PARTIAL,
                    price=102.5,
                    label="TP1",
                    rationale=("first partial",),
                ),
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=104.0,
                    label="TP2",
                    rationale=("second partial",),
                ),
                TargetLevel(
                    kind=TargetType.EXPANSION,
                    price=106.0,
                    label="TP3",
                    rationale=("runner",),
                ),
            )
        ),
    )

    result = analyze_risk(_phase5(candidate))

    assert result.setup is not None
    assert tuple(target.partial_close_pct for target in result.setup.take_profits) == (
        40.0,
        35.0,
        25.0,
    )


def test_no_selected_candidate_remains_no_trade() -> None:
    result = analyze_risk(_phase5())
    assert result.decision is RiskDecision.REJECTED
    assert result.rejection_codes == (RiskRejectionCode.NO_SELECTED_CANDIDATE,)
    assert result.reasons == ("candidate selection produced no trade candidate",)


def test_extended_entry_is_rejected() -> None:
    result = analyze_risk(_phase5(_candidate(extended=True)))
    assert result.rejection_codes == (RiskRejectionCode.ENTRY_TOO_EXTENDED,)


def test_long_current_price_above_chase_boundary_is_rejected() -> None:
    result = analyze_risk(_phase5(_candidate(current_price=102.0)))
    assert result.rejection_codes == (RiskRejectionCode.ENTRY_TOO_EXTENDED,)


def test_short_current_price_below_chase_boundary_is_rejected() -> None:
    result = analyze_risk(_phase5(_candidate(direction=TradeDirection.SHORT, current_price=98.0)))
    assert result.rejection_codes == (RiskRejectionCode.ENTRY_TOO_EXTENDED,)


def test_stop_outside_configured_bounds_is_rejected() -> None:
    tight = analyze_risk(
        _phase5(
            _candidate(
                entry_lower=99.92,
                entry_upper=100.08,
                invalidation=99.91,
            )
        )
    )
    wide = analyze_risk(_phase5(_candidate(invalidation=90.0)))
    assert tight.rejection_codes == (RiskRejectionCode.STOP_TOO_TIGHT,)
    assert wide.rejection_codes == (RiskRejectionCode.STOP_TOO_WIDE,)


def test_insufficient_target_space_is_rejected() -> None:
    result = analyze_risk(_phase5(_candidate(target=102.0)))
    assert result.rejection_codes == (RiskRejectionCode.INSUFFICIENT_TARGET_SPACE,)


def test_position_size_never_exceeds_configured_account_risk() -> None:
    config = RiskConfig(account_equity=20_000.0, risk_per_trade_pct=0.25)
    result = analyze_risk(_phase5(_candidate()), config=config)
    assert result.setup is not None
    position = result.setup.position_size
    assert position.risk_amount == pytest.approx(50.0)
    structural_loss = position.quantity * result.setup.stop_loss.distance
    execution_cost_fraction = (
        config.entry_fee_pct
        + config.exit_fee_pct
        + config.entry_slippage_pct
        + config.exit_slippage_pct
    ) / 100.0
    execution_costs = position.notional_value * execution_cost_fraction
    assert structural_loss + execution_costs == pytest.approx(position.risk_amount)


def test_required_leverage_above_safe_maximum_is_rejected() -> None:
    config = RiskConfig(
        risk_per_trade_pct=10.0,
        maximum_leverage=2.0,
        maximum_open_risk_pct=20.0,
        maximum_directional_risk_pct=20.0,
        maximum_correlated_risk_pct=20.0,
    )
    result = analyze_risk(_phase5(_candidate()), config=config)
    assert result.rejection_codes == (RiskRejectionCode.LEVERAGE_UNSAFE,)


def test_exposure_limits_reject_new_trade() -> None:
    result = analyze_risk(
        _phase5(_candidate()),
        exposure=ExposureState(open_trades=3, open_risk_amount=100.0),
    )
    assert RiskRejectionCode.MAX_CONCURRENT_TRADES in result.rejection_codes


def test_all_applicable_exposure_limits_are_reported() -> None:
    result = analyze_risk(
        _phase5(_candidate()),
        exposure=ExposureState(
            open_trades=3,
            open_risk_amount=160.0,
            same_direction_risk_amount=110.0,
            correlated_risk_amount=60.0,
            daily_realized_loss=300.0,
            consecutive_losses=4,
        ),
    )
    assert result.rejection_codes == (
        RiskRejectionCode.MAX_CONCURRENT_TRADES,
        RiskRejectionCode.MAX_OPEN_RISK,
        RiskRejectionCode.MAX_DIRECTIONAL_RISK,
        RiskRejectionCode.MAX_CORRELATED_RISK,
        RiskRejectionCode.DAILY_LOSS_LIMIT,
        RiskRejectionCode.CONSECUTIVE_LOSS_LIMIT,
    )


def test_correlated_exposure_limit_rejects_new_trade() -> None:
    result = analyze_risk(
        _phase5(_candidate()),
        exposure=ExposureState(open_risk_amount=60.0, correlated_risk_amount=60.0),
    )
    assert result.rejection_codes == (
        RiskRejectionCode.MAX_OPEN_RISK,
        RiskRejectionCode.MAX_CORRELATED_RISK,
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_configuration_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError):
        RiskConfig(account_equity=value)


def test_exposure_rejects_correlated_risk_above_total_risk() -> None:
    with pytest.raises(ValueError):
        ExposureState(open_risk_amount=10.0, correlated_risk_amount=11.0)


def test_risk_analysis_uses_only_selected_phase5_candidate() -> None:
    selected = _ranked("selected", _candidate(), 1)
    unselected_extended = _ranked("unselected", _candidate(extended=True), 2)
    phase5 = CandidateSelectionResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        all_scored_candidates=(selected.scored, unselected_extended.scored),
        ranked_candidates=(selected, unselected_extended),
        rejected_candidates=(),
        conflict_summary=ConflictSummary(
            directional_consensus=DirectionalConsensus.LONG,
            long_count=2,
            short_count=0,
            duplicate_groups=(),
            warnings=(),
        ),
        directional_consensus=DirectionalConsensus.LONG,
        selected_candidate=selected,
        no_trade_reason=None,
        evaluated_strategy_order=ORDER,
        configuration_id="test",
        metadata={},
    )

    result = analyze_risk(phase5)

    assert result.decision is RiskDecision.APPROVED
    assert result.setup is not None
    assert result.setup.candidate_id == "selected"


def test_approved_setup_rejects_inconsistent_entry_flags() -> None:
    result = analyze_risk(_phase5(_candidate()))
    assert result.setup is not None

    with pytest.raises(ValueError, match="inside-zone flag"):
        replace(
            result.setup,
            entry=replace(result.setup.entry, current_price_inside_zone=False),
        )


def test_approved_setup_rejects_directionally_invalid_chase_price() -> None:
    result = analyze_risk(_phase5(_candidate()))
    assert result.setup is not None

    with pytest.raises(ValueError, match="long chase price"):
        replace(
            result.setup,
            entry=replace(
                result.setup.entry,
                maximum_chase_price=result.setup.entry.upper - 0.01,
            ),
        )


def test_risk_contracts_are_frozen() -> None:
    result = analyze_risk(_phase5(_candidate()))
    assert result.setup is not None

    with pytest.raises(FrozenInstanceError):
        setattr(result.setup.position_size, "risk_amount", 1.0)


def test_risk_config_loads_checked_in_yaml() -> None:
    config = load_risk_config("config/risk.yaml")
    assert config.profile.value == "controlled"
    assert config.account_equity == pytest.approx(10_000.0)
    assert config.maximum_leverage == pytest.approx(5.0)
    assert config.entry_fee_pct == pytest.approx(0.04)
    assert config.exit_fee_pct == pytest.approx(0.04)
    assert config.entry_slippage_pct == pytest.approx(0.03)
    assert config.exit_slippage_pct == pytest.approx(0.03)


def test_loader_and_mode_resolver_use_canonical_execution_costs(
    tmp_path: Path,
) -> None:
    futures_text = Path("config/futures.yaml").read_text(encoding="utf-8")
    futures_text = futures_text.replace("entry_fee_percentage: 0.04", "entry_fee_percentage: 0.11")
    futures_text = futures_text.replace("exit_fee_percentage: 0.04", "exit_fee_percentage: 0.12")
    futures_text = futures_text.replace(
        "entry_slippage_percentage: 0.03", "entry_slippage_percentage: 0.13"
    )
    futures_text = futures_text.replace(
        "exit_slippage_percentage: 0.03", "exit_slippage_percentage: 0.14"
    )
    futures_path = tmp_path / "futures.yaml"
    futures_path.write_text(futures_text, encoding="utf-8")

    loaded = load_risk_config(
        "config/risk.yaml",
        futures_config_path=futures_path,
    )
    resolved = resolve_risk_config_for_mode(
        RiskConfig(),
        RiskMode.STANDARD,
        futures_config_path=futures_path,
    )

    assert (
        loaded.entry_fee_pct,
        loaded.exit_fee_pct,
        loaded.entry_slippage_pct,
        loaded.exit_slippage_pct,
    ) == pytest.approx((0.11, 0.12, 0.13, 0.14))
    assert (
        resolved.entry_fee_pct,
        resolved.exit_fee_pct,
        resolved.entry_slippage_pct,
        resolved.exit_slippage_pct,
    ) == pytest.approx((0.11, 0.12, 0.13, 0.14))


def test_risk_config_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text("unknown: 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown risk configuration fields"):
        load_risk_config(path)
