from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from apex.application.methodology_geometry_runtime import (
    GeometryExecutionCosts,
    build_geometry_runtime_context,
    geometry_execution_costs_from_settings,
)
from apex.config.settings import GeometryExecutionSettings
from apex.strategies.context import StrategyContext


@dataclass(frozen=True)
class _Features:
    atr: float


@dataclass(frozen=True)
class _Frame:
    current_price: float
    spread_percentage: float | None
    order_book_spread_percentage: float | None
    features: _Features


@dataclass(frozen=True)
class _Context:
    decision_frame: _Frame


def _context(
    *,
    atr: float = 2.0,
    ticker_spread: float | None = 0.10,
    book_spread: float | None = 0.15,
) -> StrategyContext:
    return cast(
        StrategyContext,
        _Context(
            _Frame(
                current_price=100.0,
                spread_percentage=ticker_spread,
                order_book_spread_percentage=book_spread,
                features=_Features(atr=atr),
            )
        ),
    )


def test_runtime_context_uses_worst_observed_spread_and_shared_buffer_policy() -> None:
    result = build_geometry_runtime_context(_context())

    assert result.observed_spread_pct == 0.15
    assert result.spread_source == "order_book"
    assert result.execution_buffer == pytest.approx(0.5)
    assert result.expected_cost_pct is None


def test_runtime_context_exposes_only_explicit_round_trip_costs() -> None:
    result = build_geometry_runtime_context(
        _context(),
        execution_costs=GeometryExecutionCosts(
            entry_fee_pct=0.02,
            exit_fee_pct=0.02,
            entry_slippage_pct=0.03,
            exit_slippage_pct=0.03,
        ),
    )

    assert result.expected_cost_pct == pytest.approx(0.25)


def test_missing_spread_does_not_fabricate_execution_costs() -> None:
    result = build_geometry_runtime_context(
        _context(ticker_spread=None, book_spread=None),
    )

    assert result.observed_spread_pct == 0.0
    assert result.spread_source == "unavailable"
    assert result.execution_buffer == pytest.approx(0.5)
    assert result.expected_cost_pct is None


def test_execution_costs_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        GeometryExecutionCosts(
            entry_fee_pct=-0.01,
            exit_fee_pct=0.02,
            entry_slippage_pct=0.03,
            exit_slippage_pct=0.03,
        )


def test_disabled_execution_cost_settings_remain_unavailable() -> None:
    settings = GeometryExecutionSettings(
        enabled=False,
        entry_fee_pct=0.02,
        exit_fee_pct=0.02,
        entry_slippage_pct=0.03,
        exit_slippage_pct=0.03,
    )

    assert geometry_execution_costs_from_settings(settings) is None


def test_enabled_execution_cost_settings_require_complete_values() -> None:
    with pytest.raises(ValueError, match="require entry/exit fees and slippage"):
        GeometryExecutionSettings(enabled=True, entry_fee_pct=0.02)


def test_enabled_execution_cost_settings_resolve_explicit_costs() -> None:
    costs = geometry_execution_costs_from_settings(
        GeometryExecutionSettings(
            enabled=True,
            entry_fee_pct=0.02,
            exit_fee_pct=0.02,
            entry_slippage_pct=0.03,
            exit_slippage_pct=0.03,
        )
    )

    assert costs is not None
    assert costs.total_pct == pytest.approx(0.10)
