import math

import pytest

from apex.features.numerical import finite_values, rolling_mean, validate_period


def test_validate_period_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError, match="period must be at least 1"):
        validate_period(0)


def test_finite_values_normalizes_numeric_input() -> None:
    assert finite_values([1, 2.5, 3], name="prices") == (1.0, 2.5, 3.0)


def test_finite_values_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="prices cannot be empty"):
        finite_values([], name="prices")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_finite_values_rejects_non_finite_input(value: float) -> None:
    with pytest.raises(ValueError, match="cannot contain NaN or infinite"):
        finite_values([1.0, value])


def test_rolling_mean_returns_aligned_warmup_values() -> None:
    assert rolling_mean([1.0, 2.0, 3.0, 4.0], 3) == (None, None, 2.0, 3.0)


def test_rolling_mean_supports_period_one() -> None:
    assert rolling_mean([1.0, 2.0, 3.0], 1) == (1.0, 2.0, 3.0)


def test_rolling_mean_rejects_period_larger_than_input() -> None:
    with pytest.raises(ValueError, match="exceeds available values"):
        rolling_mean([1.0, 2.0], 3)
