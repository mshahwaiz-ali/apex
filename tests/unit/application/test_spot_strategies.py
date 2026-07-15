from apex.application.spot_strategies import evaluate_spot_strategies
from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_strategy import (
    SpotStrategy,
    SpotStrategyCandidate,
    SpotStrategyDecision,
    SpotStrategyEligibility,
    SpotStrategyInput,
    SpotStrategyRoutingResult,
)
from apex.domain.spot_structure import SpotExtensionState, SpotTrendState


def _input(**overrides: object) -> SpotStrategyInput:
    values: dict[str, object] = {
        "symbol": "ETHUSDT",
        "current_price": 101.0,
        "market_regime": SpotMarketRegime.RISK_ON,
        "allow_new_entries": True,
        "structure_trend": SpotTrendState.STRONG_UPTREND,
        "extension": SpotExtensionState.NORMAL,
        "support_price": 95.0,
        "resistance_price": 110.0,
        "demand_lower": 99.0,
        "demand_upper": 103.0,
        "relative_strength_percentage": 5.0,
        "volume_ratio": 1.8,
        "pullback_depth_percentage": 5.0,
        "range_width_percentage": 10.0,
    }
    values.update(overrides)
    return SpotStrategyInput.model_validate(values)


def _candidate(
    result: SpotStrategyRoutingResult,
    strategy: SpotStrategy,
) -> SpotStrategyCandidate:
    return next(item for item in result.candidates if item.strategy is strategy)


def test_trend_pullback_is_selected_first() -> None:
    result = evaluate_spot_strategies(_input())

    assert result.selected is not None
    assert result.selected.strategy is SpotStrategy.HIGHER_TIMEFRAME_TREND_PULLBACK
    assert result.selected.decision is SpotStrategyDecision.APPROVE
    assert result.selected.thesis
    assert result.selected.invalidation_price < 95.0


def test_breakout_retest_approves_independently() -> None:
    result = evaluate_spot_strategies(
        _input(
            current_price=111.0,
            demand_lower=99.0,
            demand_upper=103.0,
            breakout_confirmed=True,
            retest_held=True,
        )
    )
    candidate = _candidate(result, SpotStrategy.BREAKOUT_RETEST)

    assert candidate.decision is SpotStrategyDecision.APPROVE
    assert candidate.invalidation_price < 110.0


def test_accumulation_breakout_approves_independently() -> None:
    result = evaluate_spot_strategies(
        _input(
            current_price=111.0,
            accumulation_confirmed=True,
            breakout_confirmed=True,
        )
    )
    candidate = _candidate(result, SpotStrategy.ACCUMULATION_RANGE_BREAKOUT)

    assert candidate.decision is SpotStrategyDecision.APPROVE


def test_liquidity_sweep_recovery_approves_independently() -> None:
    result = evaluate_spot_strategies(
        _input(
            current_price=105.0,
            liquidity_sweep_confirmed=True,
            daily_recovery_confirmed=True,
        )
    )
    candidate = _candidate(result, SpotStrategy.LIQUIDITY_SWEEP_DAILY_RECOVERY)

    assert candidate.decision is SpotStrategyDecision.APPROVE


def test_relative_strength_leader_pullback_approves() -> None:
    result = evaluate_spot_strategies(_input(relative_strength_percentage=6.0))
    candidate = _candidate(result, SpotStrategy.RELATIVE_STRENGTH_LEADER_PULLBACK)

    assert candidate.decision is SpotStrategyDecision.APPROVE


def test_risk_off_rejects_standard_strategies() -> None:
    result = evaluate_spot_strategies(
        _input(
            market_regime=SpotMarketRegime.RISK_OFF,
            allow_new_entries=False,
            structure_trend=SpotTrendState.DOWNTREND,
            extension=SpotExtensionState.DOWNSIDE_RISK,
        )
    )

    standard = result.candidates[:-1]
    assert all(item.decision is not SpotStrategyDecision.APPROVE for item in standard)
    assert result.selected is None


def test_terminal_extension_rejects_standard_entries() -> None:
    result = evaluate_spot_strategies(_input(extension=SpotExtensionState.TERMINAL))

    assert all(item.decision is not SpotStrategyDecision.APPROVE for item in result.candidates[:-1])


def test_post_capitulation_recovery_is_paper_only() -> None:
    result = evaluate_spot_strategies(
        _input(
            market_regime=SpotMarketRegime.CAPITULATION,
            allow_new_entries=False,
            structure_trend=SpotTrendState.RANGE,
            capitulation_recovery_confirmed=True,
            daily_recovery_confirmed=True,
        )
    )
    candidate = _candidate(result, SpotStrategy.POST_CAPITULATION_RECOVERY)

    assert candidate.decision is SpotStrategyDecision.APPROVE
    assert candidate.eligibility is SpotStrategyEligibility.PAPER_ONLY
    assert candidate.warnings


def test_candidates_do_not_contain_position_sizing() -> None:
    result = evaluate_spot_strategies(_input())
    payload = result.model_dump(mode="json")

    serialized = str(payload).lower()
    assert "quantity" not in serialized
    assert "allocation" not in serialized
    assert "position_size" not in serialized
