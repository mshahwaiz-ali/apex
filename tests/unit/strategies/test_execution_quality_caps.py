import pytest

from apex.strategies.execution_quality import (
    ExecutionQualityConstraints,
    ExecutionQualityInputs,
    apply_execution_quality_caps,
    calculate_execution_quality,
)


def _perfect_result():
    return calculate_execution_quality(
        ExecutionQualityInputs(
            location=1.0,
            trigger_completion=1.0,
            freshness=1.0,
            spread_slippage=1.0,
            stop_feasibility=1.0,
            chase_safety=1.0,
            data_quality=1.0,
        )
    )


def test_no_constraints_preserve_uncapped_score() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(),
    )

    assert result.uncapped_score == pytest.approx(1.0)
    assert result.applied_cap == pytest.approx(1.0)
    assert result.final_score == pytest.approx(1.0)
    assert result.cap_reasons == ()


def test_incomplete_confirmation_caps_perfect_components() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(trigger_complete=False),
    )

    assert result.uncapped_score == pytest.approx(1.0)
    assert result.applied_cap == pytest.approx(0.55)
    assert result.final_score == pytest.approx(0.55)
    assert "entry trigger or confirmation is incomplete" in result.cap_reasons


def test_provisional_evidence_cannot_score_as_perfect_execution() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(provisional_evidence=True),
    )

    assert result.applied_cap == pytest.approx(0.65)
    assert result.final_score == pytest.approx(0.65)


def test_stale_data_is_stricter_than_degraded_data() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(
            data_stale=True,
            data_degraded=True,
        ),
    )

    assert result.applied_cap == pytest.approx(0.25)
    assert result.cap_reasons == ("market data is stale",)


def test_chase_violation_is_stricter_than_outside_zone() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(
            inside_entry_zone=False,
            chase_limit_violated=True,
        ),
    )

    assert result.applied_cap == pytest.approx(0.20)
    assert result.cap_reasons == ("current price violated the maximum chase boundary",)


def test_infeasible_stop_forces_zero_execution_quality() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(stop_feasible=False),
    )

    assert result.applied_cap == pytest.approx(0.0)
    assert result.final_score == pytest.approx(0.0)
    assert result.cap_reasons == ("stop geometry is infeasible",)


def test_missing_spread_slippage_evidence_is_not_treated_as_clean() -> None:
    result = apply_execution_quality_caps(
        _perfect_result(),
        ExecutionQualityConstraints(spread_slippage_available=False),
    )

    assert result.applied_cap == pytest.approx(0.75)
    assert result.final_score == pytest.approx(0.75)


def test_cap_never_inflates_a_lower_raw_score() -> None:
    raw = calculate_execution_quality(
        ExecutionQualityInputs(
            location=0.2,
            trigger_completion=0.2,
            freshness=0.2,
            spread_slippage=0.2,
            stop_feasibility=0.2,
            chase_safety=0.2,
            data_quality=0.2,
        )
    )

    result = apply_execution_quality_caps(
        raw,
        ExecutionQualityConstraints(trigger_complete=False),
    )

    assert result.uncapped_score == pytest.approx(0.2)
    assert result.applied_cap == pytest.approx(0.55)
    assert result.final_score == pytest.approx(0.2)
