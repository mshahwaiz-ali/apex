import pytest

from apex.strategies.execution_quality import (
    ExecutionQualityInputs,
    calculate_execution_quality,
    execution_quality_weights,
)


def _inputs(**overrides: float) -> ExecutionQualityInputs:
    values = {
        "location": 1.0,
        "trigger_completion": 1.0,
        "freshness": 1.0,
        "spread_slippage": 1.0,
        "stop_feasibility": 1.0,
        "chase_safety": 1.0,
        "data_quality": 1.0,
    }
    values.update(overrides)
    return ExecutionQualityInputs(**values)


def test_perfect_components_produce_one_without_conflating_setup_quality() -> None:
    result = calculate_execution_quality(_inputs())

    assert result.score == pytest.approx(1.0)
    assert result.breakdown.total == pytest.approx(1.0)
    assert "setup_quality" not in result.breakdown.as_mapping()


def test_perfect_location_alone_cannot_create_perfect_execution_score() -> None:
    result = calculate_execution_quality(
        _inputs(
            trigger_completion=0.0,
            freshness=0.0,
            spread_slippage=0.0,
            stop_feasibility=0.0,
            chase_safety=0.0,
            data_quality=0.0,
        )
    )

    assert result.score == pytest.approx(0.20)
    assert result.breakdown.location == pytest.approx(0.20)


def test_component_breakdown_explains_exact_weighted_score() -> None:
    result = calculate_execution_quality(
        _inputs(
            location=0.8,
            trigger_completion=0.5,
            freshness=0.6,
            spread_slippage=0.7,
            stop_feasibility=0.9,
            chase_safety=0.4,
            data_quality=0.95,
        )
    )

    assert result.breakdown.location == pytest.approx(0.16)
    assert result.breakdown.trigger_completion == pytest.approx(0.10)
    assert result.breakdown.freshness == pytest.approx(0.09)
    assert result.breakdown.spread_slippage == pytest.approx(0.07)
    assert result.breakdown.stop_feasibility == pytest.approx(0.135)
    assert result.breakdown.chase_safety == pytest.approx(0.04)
    assert result.breakdown.data_quality == pytest.approx(0.095)
    assert result.score == pytest.approx(0.69)


def test_weights_are_complete_and_sum_to_one() -> None:
    weights = execution_quality_weights()

    assert set(weights) == {
        "location",
        "trigger_completion",
        "freshness",
        "spread_slippage",
        "stop_feasibility",
        "chase_safety",
        "data_quality",
    }
    assert sum(weights.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("location", -0.01),
        ("trigger_completion", 1.01),
        ("freshness", float("nan")),
        ("spread_slippage", float("inf")),
    ],
)
def test_inputs_reject_invalid_normalized_components(
    field: str,
    value: float,
) -> None:
    with pytest.raises(ValueError):
        _inputs(**{field: value})
