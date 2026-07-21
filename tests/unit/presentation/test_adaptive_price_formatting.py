from __future__ import annotations

import pytest

from apex.presentation import UNAVAILABLE, format_price


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (153.428191, "153.43"),
        (4.89321, "4.89"),
        (0.928191, "0.9282"),
        (0.0948103, "0.09481"),
        (0.00480923, "0.004809"),
        (0.000047819, "0.00004782"),
        (64230.5, "64,230.50"),
    ),
)
def test_format_price_uses_adaptive_operator_precision(
    value: float,
    expected: str,
) -> None:
    assert format_price(value) == expected


def test_format_price_preserves_explicit_exchange_precision() -> None:
    assert format_price(4.89321, decimals=4) == "4.8932"
    assert format_price(0.00480923, decimals=8) == "0.00480923"


@pytest.mark.parametrize("value", (None, float("nan"), float("inf"), True))
def test_format_price_keeps_invalid_values_unavailable(value: object) -> None:
    assert format_price(value) == UNAVAILABLE
