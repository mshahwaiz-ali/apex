from __future__ import annotations

from dataclasses import fields

import pytest

from apex.application.paper_lifecycle_analytics import PaperLifecycleAnalytics
from apex.application.paper_lifecycle_health import (
    PaperLifecycleHealthPolicy,
    PaperLifecycleHealthReason,
    PaperLifecycleHealthStatus,
    evaluate_paper_lifecycle_health,
    paper_lifecycle_health_payload,
)


def _analytics(**overrides: object) -> PaperLifecycleAnalytics:
    values: dict[str, object] = {
        "intake_candidates_observed": 25,
        "intake_accepted": 22,
        "intake_rejected": 3,
        "duplicates_skipped": 0,
        "persistence_failures": 0,
        "intake_reason_counts": {},
        "loaded_trades": 22,
        "eligible_trades": 22,
        "advanced_trades": 20,
        "unchanged_trades": 2,
        "missing_candle_trades": 1,
        "requested_symbols": 20,
        "successful_symbols": 19,
        "provider_failure_count": 1,
        "provider_failures_by_symbol": {"BADUSDT": 1},
        "state_counts": {"target_hit": 12, "stopped": 8},
        "entry_state_counts": {},
        "waiting_for_entry": 2,
        "entered_trades": 20,
        "unfilled_terminal_trades": 1,
        "partial_target_fills": 8,
        "full_target_completions": 12,
        "stop_loss_exits": 8,
        "expired_trades": 0,
        "invalidations": 1,
        "cancelled_trades": 0,
        "transition_counts": {},
        "transition_reason_counts": {},
        "realized_net_pnl": 14.0,
        "average_realized_r_multiple": 0.35,
        "risk_multiple_distribution": {},
        "leverage_distribution": {},
        "holding_time_distribution": {},
        "average_margin": 12.0,
        "average_wallet_exposure_pct": 10.0,
        "total_fees": 1.0,
        "total_slippage": 0.5,
        "trades": (),
    }
    values.update(overrides)
    expected = {field.name for field in fields(PaperLifecycleAnalytics)}
    assert values.keys() == expected
    return PaperLifecycleAnalytics(**values)  # type: ignore[arg-type]


def test_health_report_is_healthy_at_sufficient_reliable_sample() -> None:
    report = evaluate_paper_lifecycle_health(_analytics())

    assert report.status is PaperLifecycleHealthStatus.HEALTHY
    assert report.reasons == ()
    assert report.terminal_trade_count == 20
    assert report.provider_failure_rate == pytest.approx(0.05)
    assert report.missing_candle_rate == pytest.approx(1 / 22)
    assert report.invalidation_rate == pytest.approx(0.05)
    assert report.unfilled_terminal_rate == pytest.approx(0.05)
    assert report.sample_shortfall == 0
    assert report.ready_for_forward_viability_review is True


def test_negative_performance_is_degraded_not_operationally_failed() -> None:
    report = evaluate_paper_lifecycle_health(
        _analytics(realized_net_pnl=-2.0, average_realized_r_multiple=-0.1)
    )

    assert report.status is PaperLifecycleHealthStatus.DEGRADED
    assert report.reasons == (
        PaperLifecycleHealthReason.AVERAGE_R_BELOW_MINIMUM,
        PaperLifecycleHealthReason.NET_PNL_BELOW_MINIMUM,
    )
    assert report.ready_for_forward_viability_review is True


def test_operational_failure_takes_precedence_over_sample_shortfall() -> None:
    report = evaluate_paper_lifecycle_health(
        _analytics(
            requested_symbols=4,
            provider_failure_count=2,
            state_counts={"target_hit": 2},
        )
    )

    assert report.status is PaperLifecycleHealthStatus.FAILED
    assert PaperLifecycleHealthReason.PROVIDER_FAILURE_RATE_EXCEEDED in report.reasons
    assert PaperLifecycleHealthReason.INSUFFICIENT_TERMINAL_SAMPLE in report.reasons
    assert report.ready_for_forward_viability_review is False


def test_small_clean_sample_is_insufficient_not_degraded() -> None:
    report = evaluate_paper_lifecycle_health(
        _analytics(
            state_counts={"target_hit": 4, "stopped": 2},
            invalidations=0,
            unfilled_terminal_trades=0,
        )
    )

    assert report.status is PaperLifecycleHealthStatus.INSUFFICIENT_SAMPLE
    assert report.reasons == (
        PaperLifecycleHealthReason.INSUFFICIENT_TERMINAL_SAMPLE,
    )
    assert report.sample_shortfall == 14


def test_missing_realized_performance_is_explicit() -> None:
    report = evaluate_paper_lifecycle_health(
        _analytics(realized_net_pnl=None, average_realized_r_multiple=None)
    )

    assert report.status is PaperLifecycleHealthStatus.DEGRADED
    assert report.reasons == (
        PaperLifecycleHealthReason.REALIZED_PERFORMANCE_UNAVAILABLE,
    )
    assert report.realized_net_pnl is None
    assert report.average_realized_r_multiple is None


def test_thresholds_are_inclusive_and_zero_denominators_are_safe() -> None:
    policy = PaperLifecycleHealthPolicy(
        minimum_terminal_trades=1,
        maximum_provider_failure_rate=0.5,
        maximum_missing_candle_rate=0.5,
        maximum_persistence_failure_rate=0.5,
        maximum_invalidation_rate=0.5,
        maximum_unfilled_terminal_rate=0.5,
        require_realized_performance=False,
    )
    report = evaluate_paper_lifecycle_health(
        _analytics(
            intake_accepted=0,
            persistence_failures=0,
            loaded_trades=0,
            missing_candle_trades=0,
            requested_symbols=0,
            provider_failure_count=0,
            state_counts={"invalidated": 1},
            invalidations=0,
            unfilled_terminal_trades=0,
            realized_net_pnl=None,
            average_realized_r_multiple=None,
        ),
        policy=policy,
    )

    assert report.status is PaperLifecycleHealthStatus.HEALTHY
    assert report.provider_failure_rate == 0.0
    assert report.missing_candle_rate == 0.0
    assert report.persistence_failure_rate == 0.0


def test_policy_rejects_invalid_boundaries() -> None:
    with pytest.raises(ValueError, match="minimum terminal trades"):
        PaperLifecycleHealthPolicy(minimum_terminal_trades=0)
    with pytest.raises(ValueError, match="between zero and one"):
        PaperLifecycleHealthPolicy(maximum_provider_failure_rate=1.1)
    with pytest.raises(ValueError, match="must be finite"):
        PaperLifecycleHealthPolicy(minimum_average_realized_r=float("nan"))


def test_payload_is_stable_and_json_ready() -> None:
    report = evaluate_paper_lifecycle_health(_analytics())

    payload = paper_lifecycle_health_payload(report)

    assert payload["status"] == PaperLifecycleHealthStatus.HEALTHY
    assert payload["reasons"] == ()
    assert payload["terminal_trade_count"] == 20
    assert payload["sample_shortfall"] == 0
