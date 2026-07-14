from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from apex.backtesting import BacktestReport
from apex.paper_trading import PaperPerformance
from apex.validation import (
    ForwardValidationEvidence,
    ForwardValidationThresholds,
    ProductionEligibility,
    ValidationReason,
    evaluate_forward_validation,
)


def _backtest() -> BacktestReport:
    return cast(
        BacktestReport,
        SimpleNamespace(
            total_trades=100,
            win_rate=0.60,
            expectancy=0.40,
            maximum_drawdown=10.0,
        ),
    )


def _paper(*, closed_trades: int = 40, win_rate: float = 0.58) -> PaperPerformance:
    return PaperPerformance(
        total_trades=closed_trades,
        open_trades=0,
        closed_trades=closed_trades,
        net_pnl=10.0,
        win_rate=win_rate,
        average_r_multiple=0.35,
        by_state={"target_hit": closed_trades},
    )


def test_forward_validation_can_reach_funded_review() -> None:
    report = evaluate_forward_validation(
        backtest=_backtest(),
        paper=_paper(),
        evidence=ForwardValidationEvidence(
            paper_expectancy=0.35,
            paper_maximum_drawdown=11.0,
        ),
        thresholds=ForwardValidationThresholds(),
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.eligibility is ProductionEligibility.READY_FOR_FUNDED_REVIEW
    assert report.reasons == ()


def test_forward_validation_rejects_critical_failures() -> None:
    report = evaluate_forward_validation(
        backtest=_backtest(),
        paper=_paper(),
        evidence=ForwardValidationEvidence(
            critical_lifecycle_failures=1,
            paper_expectancy=0.35,
            paper_maximum_drawdown=11.0,
        ),
        thresholds=ForwardValidationThresholds(),
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.eligibility is ProductionEligibility.REJECTED
    assert ValidationReason.CRITICAL_LIFECYCLE_FAILURE in report.reasons


def test_forward_validation_requires_minimum_sample() -> None:
    report = evaluate_forward_validation(
        backtest=_backtest(),
        paper=_paper(closed_trades=10),
        evidence=ForwardValidationEvidence(
            paper_expectancy=0.35,
            paper_maximum_drawdown=11.0,
        ),
        thresholds=ForwardValidationThresholds(minimum_closed_trades=30),
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
    )

    assert report.eligibility is ProductionEligibility.INSUFFICIENT_SAMPLE
    assert ValidationReason.MINIMUM_SAMPLE_NOT_MET in report.reasons
