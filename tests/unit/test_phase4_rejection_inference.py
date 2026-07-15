from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apex.domain.futures import EntryState
from apex.strategies.context import TimeframeRole
from apex.strategies.contracts import StrategyType
from apex.strategies.diagnostics import Phase4RejectionCode, build_phase4_diagnostics
from apex.structure.contracts import TrendDirection
from apex.structure.regime import MarketRegime


def _context(
    *,
    trend: TrendDirection,
    momentum: tuple[float, float, float],
    higher_contradiction: bool = False,
    level_price: float = 100.0,
) -> SimpleNamespace:
    levels = (SimpleNamespace(representative_price=level_price),)
    decision = SimpleNamespace(
        role=TimeframeRole.ENTRY,
        features=SimpleNamespace(
            rsi_slope=momentum[0],
            macd_histogram=momentum[1],
            rate_of_change=momentum[2],
        ),
        structure=SimpleNamespace(
            trend=SimpleNamespace(direction=trend),
            breaks=(),
            levels=levels,
        ),
    )
    higher = SimpleNamespace(
        role=TimeframeRole.INTERMEDIATE,
        structure=SimpleNamespace(
            trend=SimpleNamespace(direction=TrendDirection.RANGE),
            breaks=(),
        ),
    )
    return SimpleNamespace(
        decision_frame=decision,
        frames=(higher, decision),
        atr=2.0,
        current_price=100.0,
        higher_timeframe_contradiction=lambda *, bullish: higher_contradiction,
    )


def _diagnostic(context: SimpleNamespace, monkeypatch: Any):
    monkeypatch.setattr(
        "apex.strategies.diagnostics.classify_market_regime",
        lambda unused: MarketRegime.STABLE_RANGE,
    )
    diagnostics = build_phase4_diagnostics(
        context,
        evaluated=(StrategyType.TREND_PULLBACK,),
        eligible=(StrategyType.TREND_PULLBACK,),
        skipped={},
        candidates=(),
    )
    return diagnostics[StrategyType.TREND_PULLBACK]


def test_bullish_structure_rejects_uniformly_bearish_momentum(monkeypatch: Any) -> None:
    diagnostic = _diagnostic(
        _context(
            trend=TrendDirection.BULLISH,
            momentum=(-0.1, -0.2, -0.3),
        ),
        monkeypatch,
    )

    assert Phase4RejectionCode.MOMENTUM_MISMATCH in diagnostic.rejection_codes
    assert Phase4RejectionCode.MISSING_ENTRY_REFERENCES not in diagnostic.rejection_codes
    assert diagnostic.near_miss_state is EntryState.APPROACHING_ENTRY


def test_bearish_structure_rejects_higher_timeframe_contradiction(monkeypatch: Any) -> None:
    diagnostic = _diagnostic(
        _context(
            trend=TrendDirection.BEARISH,
            momentum=(-0.1, -0.2, -0.3),
            higher_contradiction=True,
        ),
        monkeypatch,
    )

    assert (
        Phase4RejectionCode.HIGHER_TIMEFRAME_CONTRADICTION
        in diagnostic.rejection_codes
    )


def test_far_structural_reference_marks_entry_as_missed(monkeypatch: Any) -> None:
    diagnostic = _diagnostic(
        _context(
            trend=TrendDirection.BULLISH,
            momentum=(0.1, 0.2, 0.3),
            level_price=110.0,
        ),
        monkeypatch,
    )

    assert (
        Phase4RejectionCode.EXCESSIVE_DISTANCE_FROM_CURRENT
        in diagnostic.rejection_codes
    )
    assert diagnostic.near_miss_state is EntryState.MISSED_ENTRY
