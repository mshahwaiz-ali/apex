from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.calibration_acceptance import (
    AcceptanceState,
    CalibrationAcceptancePolicy,
)
from apex.backtesting.calibration_metrics import (
    AlignmentClass,
    CalibratedTradeOutcome,
    OutcomeState,
    build_calibration_report,
)
from apex.backtesting.calibration_protocol import (
    CalibrationProtocol,
    ChronologicalSplit,
    EquityObservation,
    MethodologyAcceptancePolicy,
    PartialTargetModel,
    TriggerHandling,
    calculate_maximum_drawdown_r,
    evaluate_methodology_acceptance,
    validate_calibration_protocol,
)

BASE = datetime(2024, 1, 1, tzinfo=UTC)


def _split() -> ChronologicalSplit:
    return ChronologicalSplit(
        train_start=BASE,
        train_end=BASE + timedelta(days=100),
        validation_start=BASE + timedelta(days=101),
        validation_end=BASE + timedelta(days=150),
        test_start=BASE + timedelta(days=151),
        test_end=BASE + timedelta(days=200),
    )


def _protocol(**changes: object) -> CalibrationProtocol:
    values: dict[str, object] = {
        "split": _split(),
        "future_data_access_disabled": True,
        "trigger_handling": TriggerHandling.INTRABAR_CONSERVATIVE,
        "entry_zone_respected": True,
        "maximum_chase_respected": True,
        "fees_included": True,
        "slippage_included": True,
        "partial_target_model": PartialTargetModel.FIXED_FRACTIONS,
        "missed_trades_preserved": True,
        "stale_and_developing_preserved": True,
        "sample_size_reported": True,
    }
    values.update(changes)
    return CalibrationProtocol(**values)  # type: ignore[arg-type]


def _outcomes(count: int = 20) -> tuple[CalibratedTradeOutcome, ...]:
    return tuple(
        CalibratedTradeOutcome(
            strategy="breakout",
            regime="trend" if index < count // 2 else "range",
            confidence_band="high",
            actionability_state="ready_now",
            alignment=AlignmentClass.ALIGNED,
            outcome_state=OutcomeState.WIN,
            realized_r=1.2,
            mfe_r=1.8,
            mae_r=0.3,
            tp1_hit=True,
            tp2_hit=True,
            runner_success=True,
            stop_hit=False,
            false_cmp_signal=False,
            fees_r=0.05,
            slippage_r=0.02,
        )
        for index in range(count)
    )


def _equity(values: tuple[float, ...]) -> tuple[EquityObservation, ...]:
    return tuple(
        EquityObservation(
            timestamp=BASE + timedelta(minutes=index),
            cumulative_r=value,
        )
        for index, value in enumerate(values)
    )


def _policy(maximum_drawdown_r: float = 3.0) -> MethodologyAcceptancePolicy:
    return MethodologyAcceptancePolicy(
        calibration=CalibrationAcceptancePolicy(
            minimum_counted_trades=20,
            minimum_regime_trades=10,
            minimum_stable_regime_fraction=1.0,
        ),
        maximum_drawdown_r=maximum_drawdown_r,
    )


def test_chronological_split_rejects_overlap_or_reversal() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        ChronologicalSplit(
            train_start=BASE,
            train_end=BASE + timedelta(days=100),
            validation_start=BASE + timedelta(days=99),
            validation_end=BASE + timedelta(days=150),
            test_start=BASE + timedelta(days=151),
            test_end=BASE + timedelta(days=200),
        )


def test_protocol_lists_every_failed_realism_rule() -> None:
    result = validate_calibration_protocol(
        _protocol(
            future_data_access_disabled=False,
            entry_zone_respected=False,
            maximum_chase_respected=False,
            fees_included=False,
            slippage_included=False,
            missed_trades_preserved=False,
            stale_and_developing_preserved=False,
            sample_size_reported=False,
        )
    )

    assert result.valid is False
    assert len(result.reasons) == 8
    assert any("future-data" in reason for reason in result.reasons)
    assert any("maximum-chase" in reason for reason in result.reasons)
    assert any("sample size" in reason for reason in result.reasons)


def test_maximum_drawdown_uses_peak_to_trough_equity() -> None:
    drawdown = calculate_maximum_drawdown_r(_equity((0.0, 2.0, 3.0, 1.5, 2.5, -1.0, 4.0)))

    assert drawdown == pytest.approx(4.0)


def test_drawdown_rejects_non_chronological_equity() -> None:
    observations = (
        EquityObservation(timestamp=BASE + timedelta(minutes=1), cumulative_r=1.0),
        EquityObservation(timestamp=BASE, cumulative_r=2.0),
    )

    with pytest.raises(ValueError, match="strictly chronological"):
        calculate_maximum_drawdown_r(observations)


def test_final_acceptance_rejects_excessive_drawdown() -> None:
    report = build_calibration_report(_outcomes())

    result = evaluate_methodology_acceptance(
        report,
        protocol=_protocol(),
        equity_curve=_equity((0.0, 2.0, 4.0, -1.0, 5.0)),
        policy=_policy(maximum_drawdown_r=3.0),
    )

    assert result.state is AcceptanceState.REJECTED
    assert result.maximum_drawdown_r == pytest.approx(5.0)
    assert result.confidence_claims_allowed is False
    assert any("drawdown" in reason for reason in result.reasons)


def test_final_acceptance_rejects_invalid_protocol() -> None:
    report = build_calibration_report(_outcomes())

    result = evaluate_methodology_acceptance(
        report,
        protocol=_protocol(future_data_access_disabled=False),
        equity_curve=_equity((0.0, 1.0, 2.0)),
        policy=_policy(),
    )

    assert result.state is AcceptanceState.REJECTED
    assert result.protocol_valid is False
    assert result.confidence_claims_allowed is False


def test_final_acceptance_requires_equity_curve() -> None:
    report = build_calibration_report(_outcomes())

    result = evaluate_methodology_acceptance(
        report,
        protocol=_protocol(),
        equity_curve=(),
        policy=_policy(),
    )

    assert result.state is AcceptanceState.REJECTED
    assert result.maximum_drawdown_r is None
    assert any("equity curve" in reason for reason in result.reasons)


def test_final_acceptance_allows_claims_only_when_every_gate_passes() -> None:
    report = build_calibration_report(_outcomes())

    result = evaluate_methodology_acceptance(
        report,
        protocol=_protocol(),
        equity_curve=_equity((0.0, 1.0, 2.0, 1.5, 3.0)),
        policy=_policy(),
    )

    assert result.state is AcceptanceState.ACCEPTED
    assert result.protocol_valid is True
    assert result.maximum_drawdown_r == pytest.approx(0.5)
    assert result.confidence_claims_allowed is True
    assert result.reasons == ()
