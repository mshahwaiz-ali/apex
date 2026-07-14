"""Tests for bundled V2 baseline campaign evaluation."""

from __future__ import annotations

from apex.application import BaselineCampaignPlan, BaselineDatasetRef
from apex.backtesting import EvidenceQuality, HistoricalEdgeProfile
from apex.baseline import (
    BaselineEvaluationPolicy,
    BaselineReason,
    BaselineScenario,
    BaselineVerdict,
    evaluate_baseline_campaigns,
)
from apex.domain import RiskMode
from apex.strategies import StrategyType


def _plan() -> BaselineCampaignPlan:
    return BaselineCampaignPlan(
        identifier="baseline-v2",
        datasets=(
            BaselineDatasetRef(
                dataset_id="curated-v1",
                content_hash="hash-v1",
                symbols=("BTCUSDT", "ETHUSDT"),
                market_regimes=("trend", "range"),
            ),
        ),
        strategies=(StrategyType.TREND_PULLBACK, StrategyType.BREAKOUT_CONTINUATION),
        risk_modes=(RiskMode.STANDARD,),
        variant_ids=("base", "stress"),
        fee_pct=0.04,
        slippage_pct=0.02,
    )


def _profile(
    strategy: StrategyType,
    symbol: str,
    regime: str,
    score_band: str,
    *,
    sample_size: int = 30,
    expectancy: float = 0.4,
    profit_factor: float = 1.4,
    drawdown: float = 5.0,
) -> HistoricalEdgeProfile:
    return HistoricalEdgeProfile(
        dimensions={
            "strategy": strategy.value,
            "symbol": symbol,
            "market_regime": regime,
            "score_band": score_band,
        },
        sample_size=sample_size,
        win_rate=0.55,
        loss_rate=0.45,
        breakeven_rate=0.0,
        average_r=expectancy,
        median_r=expectancy,
        expectancy=expectancy,
        profit_factor=profit_factor,
        maximum_drawdown_r=drawdown,
        maximum_losing_streak=3,
        average_holding_candles=8.0,
        average_execution_cost_r=0.05,
        evidence_quality=EvidenceQuality.RESEARCH_ONLY,
    )


def _scenario(identifier: str, *, multiplier: float = 1.0) -> BaselineScenario:
    profiles = (
        _profile(
            StrategyType.TREND_PULLBACK,
            "BTCUSDT",
            "trend",
            "70_79",
            expectancy=0.5 * multiplier,
        ),
        _profile(
            StrategyType.TREND_PULLBACK,
            "ETHUSDT",
            "range",
            "80_89",
            expectancy=0.3 * multiplier,
        ),
        _profile(
            StrategyType.BREAKOUT_CONTINUATION,
            "BTCUSDT",
            "trend",
            "80_89",
            expectancy=0.2 * multiplier,
        ),
        _profile(
            StrategyType.BREAKOUT_CONTINUATION,
            "ETHUSDT",
            "range",
            "90_99",
            expectancy=0.1 * multiplier,
        ),
    )
    return BaselineScenario(
        identifier=identifier,
        fee_pct=0.04 if identifier == "base" else 0.10,
        slippage_pct=0.02 if identifier == "base" else 0.08,
        profiles=profiles,
    )


def _policy() -> BaselineEvaluationPolicy:
    return BaselineEvaluationPolicy(minimum_strategy_trades=60)


def test_accepts_strategies_with_positive_stable_multi_market_edge() -> None:
    report = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"), _scenario("stress", multiplier=0.7)),
        baseline_scenario_id="base",
        policy=_policy(),
    )

    assert all(item.verdict is BaselineVerdict.ACCEPT for item in report.assessments)
    assert all(item.reasons == (BaselineReason.BASELINE_ACCEPTED,) for item in report.assessments)
    assert report.assessments[0].symbols == ("BTCUSDT", "ETHUSDT")
    assert report.assessments[0].regimes == ("range", "trend")
    assert report.assessments[0].score_bands == {"70_79": 0.5, "80_89": 0.3}


def test_cost_collapse_restricts_strategy() -> None:
    report = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"), _scenario("stress", multiplier=0.1)),
        baseline_scenario_id="base",
        policy=_policy(),
    )

    assert all(item.verdict is BaselineVerdict.RESTRICT for item in report.assessments)
    assert all(BaselineReason.COST_SENSITIVITY_EXCESSIVE in item.reasons for item in report.assessments)


def test_non_positive_expectancy_rejects_strategy() -> None:
    weak_profiles = list(_scenario("base").profiles)
    weak_profiles[0] = _profile(
        StrategyType.TREND_PULLBACK,
        "BTCUSDT",
        "trend",
        "70_79",
        expectancy=-0.5,
        profit_factor=0.8,
    )
    weak_profiles[1] = _profile(
        StrategyType.TREND_PULLBACK,
        "ETHUSDT",
        "range",
        "80_89",
        expectancy=-0.3,
        profit_factor=0.9,
    )
    scenario = BaselineScenario(
        identifier="base",
        fee_pct=0.04,
        slippage_pct=0.02,
        profiles=tuple(weak_profiles),
    )

    report = evaluate_baseline_campaigns(
        _plan(),
        (scenario,),
        baseline_scenario_id="base",
        policy=_policy(),
    )
    trend = next(item for item in report.assessments if item.strategy == "trend_pullback")

    assert trend.verdict is BaselineVerdict.REJECT
    assert BaselineReason.EXPECTANCY_NOT_POSITIVE in trend.reasons
    assert BaselineReason.PROFIT_FACTOR_INADEQUATE in trend.reasons


def test_insufficient_sample_has_distinct_verdict() -> None:
    report = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"),),
        baseline_scenario_id="base",
        policy=BaselineEvaluationPolicy(minimum_strategy_trades=100),
    )

    assert all(item.verdict is BaselineVerdict.INSUFFICIENT_EVIDENCE for item in report.assessments)


def test_report_identity_is_deterministic_and_changes_with_results() -> None:
    first = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"), _scenario("stress", multiplier=0.7)),
        baseline_scenario_id="base",
        policy=_policy(),
    )
    second = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"), _scenario("stress", multiplier=0.7)),
        baseline_scenario_id="base",
        policy=_policy(),
    )
    changed = evaluate_baseline_campaigns(
        _plan(),
        (_scenario("base"), _scenario("stress", multiplier=0.5)),
        baseline_scenario_id="base",
        policy=_policy(),
    )

    assert first.report_id == second.report_id
    assert first.report_id != changed.report_id
    assert len(first.report_id) == 64


def test_missing_planned_strategy_is_rejected() -> None:
    scenario = BaselineScenario(
        identifier="base",
        fee_pct=0.04,
        slippage_pct=0.02,
        profiles=tuple(
            profile
            for profile in _scenario("base").profiles
            if profile.dimensions["strategy"] == StrategyType.TREND_PULLBACK.value
        ),
    )

    try:
        evaluate_baseline_campaigns(_plan(), (scenario,), baseline_scenario_id="base")
    except ValueError as exc:
        assert "missing planned strategies" in str(exc)
    else:
        raise AssertionError("missing planned strategy should fail validation")
