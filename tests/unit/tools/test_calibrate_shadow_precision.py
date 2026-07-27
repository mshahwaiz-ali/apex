from __future__ import annotations

from datetime import UTC, datetime

from tools.calibrate_shadow_precision import (
    PrecisionCandidate,
    PrecisionRule,
    build_abstention_frontier,
    declared_rules,
    metrics,
    select_candidates,
)


def _candidate(*, strategy: str, net_tp1_r: float, realized_r: float) -> PrecisionCandidate:
    return PrecisionCandidate(
        symbol="BTC/USDT",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        net_return_r=realized_r,
        strategy=strategy,
        source="score_or_collision_rejected",
        net_tp1_r=net_tp1_r,
        cost_r=0.2,
        alignment_score=80.0,
        conflict_score=10.0,
        behavior_cohort="high_liquidity_trending",
        volatility_class="normal",
        liquidity_quote_volume_median=1_000_000.0,
        monthly_return_cohort="gainer",
    )


def test_calibration_rule_population_is_predeclared() -> None:
    rules = declared_rules()

    assert len(rules) == 864
    assert len({rule.identity for rule in rules}) == 864


def test_selection_rank_does_not_use_realized_return() -> None:
    rule = PrecisionRule(
        sources=None,
        strategies=None,
        minimum_net_tp1_r=0.0,
        maximum_cost_r=1.0,
        minimum_alignment_score=0.0,
        maximum_conflict_score=100.0,
    )
    lower_pretrade_rank_but_winner = _candidate(
        strategy="momentum_breakout",
        net_tp1_r=1.0,
        realized_r=5.0,
    )
    higher_pretrade_rank_but_loser = _candidate(
        strategy="trend_pullback",
        net_tp1_r=2.0,
        realized_r=-1.0,
    )

    selected = select_candidates(
        (lower_pretrade_rank_but_winner, higher_pretrade_rank_but_loser),
        rule,
        allowed_timestamps={lower_pretrade_rank_but_winner.timestamp},
    )

    assert selected == (higher_pretrade_rank_but_loser,)


def test_abstention_frontier_does_not_promote_unprofitable_precision() -> None:
    attempt = {
        "rule": {"maximum_cost_r": 0.25},
        "rule_identity": "high-win-negative-edge",
        "aggregate_validation": {
            "outcomes": 81,
            "win_rate": 0.73,
            "win_rate_wilson_lower_95": 0.62,
            "net_expectancy_r": -0.05,
            "bootstrap_95_lower_bound_r": -0.19,
            "profit_factor": 0.82,
        },
        "folds": [
            {
                "outcomes": 30,
                "net_expectancy_r": -0.10,
                "profit_factor": 0.70,
            }
        ],
    }

    report = build_abstention_frontier((attempt,))
    selected = report["frontier"]["50"]

    assert selected["aggregate_validation"]["win_rate"] == 0.73
    assert selected["production_eligible"] is False
    assert report["production_behavior_changed"] is False


def test_metrics_explain_when_high_accuracy_is_below_break_even() -> None:
    outcomes = tuple(
        _candidate(
            strategy="trend_pullback",
            net_tp1_r=1.0,
            realized_r=value,
        )
        for value in (0.3, 0.3, 0.3, -1.0)
    )

    report = metrics(outcomes, bootstrap_samples=100)

    assert report["win_rate"] == 0.75
    assert report["net_expectancy_r"] < 0.0
    assert report["break_even_win_rate_at_observed_payoff"] > 0.75
