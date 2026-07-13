"""Tests for deterministic top-gainer state classification."""

import pytest
from pydantic import ValidationError

from apex.domain import (
    GainerState,
    GainerStateInput,
    GainerStateThresholds,
    classify_gainer_state,
)


@pytest.mark.parametrize(
    ("case_id", "inputs", "expected"),
    [
        (
            "acceleration",
            GainerStateInput(
                return_24h_pct=18,
                recent_return_pct=4,
                relative_volume=3,
                range_expansion=2,
                close_location=0.8,
                ema_extension_pct=8,
            ),
            GainerState.ACCELERATION,
        ),
        (
            "fresh_breakout",
            GainerStateInput(
                return_24h_pct=6,
                recent_return_pct=1.5,
                relative_volume=1.8,
                range_expansion=1.1,
                close_location=0.75,
                ema_extension_pct=3,
            ),
            GainerState.FRESH_BREAKOUT,
        ),
        (
            "distribution",
            GainerStateInput(
                return_24h_pct=14,
                recent_return_pct=-1,
                relative_volume=2.5,
                range_expansion=1.3,
                close_location=0.3,
                ema_extension_pct=5,
            ),
            GainerState.DISTRIBUTION,
        ),
        (
            "breakdown",
            GainerStateInput(recent_return_pct=-2, support_break=True),
            GainerState.BREAKDOWN,
        ),
        (
            "terminal_extension",
            GainerStateInput(return_24h_pct=30, recent_return_pct=2, ema_extension_pct=40),
            GainerState.TERMINAL_EXTENSION,
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_gainer_state_classification(
    case_id: str,
    inputs: GainerStateInput,
    expected: GainerState,
) -> None:
    assert case_id
    assert classify_gainer_state(inputs).state is expected


def test_high_rsi_style_extension_alone_does_not_force_breakdown() -> None:
    result = classify_gainer_state(
        GainerStateInput(return_24h_pct=12, recent_return_pct=2, ema_extension_pct=8)
    )

    assert result.state is GainerState.CONTROLLED_CONTINUATION


def test_gainer_state_honors_configured_thresholds() -> None:
    inputs = GainerStateInput(
        return_24h_pct=7,
        recent_return_pct=1.2,
        relative_volume=1.6,
    )

    assert classify_gainer_state(inputs).state is GainerState.FRESH_BREAKOUT
    result = classify_gainer_state(
        inputs,
        thresholds=GainerStateThresholds(fresh_total_return_pct=8.0),
    )

    assert result.state is GainerState.CHAOTIC


def test_gainer_state_reports_missing_optional_inputs() -> None:
    result = classify_gainer_state(GainerStateInput(recent_return_pct=-2, support_break=True))

    assert "return_24h_pct" in result.missing_optional_data


def test_gainer_state_requires_measurable_input() -> None:
    with pytest.raises(ValidationError, match="at least one measurable input"):
        GainerStateInput()
