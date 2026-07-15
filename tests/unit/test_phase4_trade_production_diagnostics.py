from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apex.domain.futures import EntryState
from apex.strategies.analysis import _strategy_eligibility
from apex.strategies.context import TimeframeRole
from apex.strategies.contracts import StrategyType
from apex.strategies.diagnostics import (
    Phase4RejectionCode,
    build_phase4_diagnostics,
    has_higher_timeframe_breakout,
)
from apex.structure.contracts import TrendDirection
from apex.structure.regime import MarketRegime


def _context() -> SimpleNamespace:
    decision = SimpleNamespace(
        role=TimeframeRole.ENTRY,
        features=SimpleNamespace(
            rsi_slope=0.1,
            macd_histogram=0.2,
            rate_of_change=0.3,
        ),
        structure=SimpleNamespace(
            trend=SimpleNamespace(direction=TrendDirection.BULLISH),
            breaks=(),
            levels=(),
        ),
    )
    higher = SimpleNamespace(
        role=TimeframeRole.INTERMEDIATE,
        structure=SimpleNamespace(breaks=()),
    )
    return SimpleNamespace(
        decision_frame=decision,
        frames=(higher, decision),
        atr=2.0,
        current_price=100.0,
    )


def test_higher_breakout_keeps_continuation_eligible() -> None:
    eligible, skipped = _strategy_eligibility(
        MarketRegime.REVERSAL_TRANSITION,
        tuple(StrategyType),
        higher_timeframe_breakout=True,
    )

    assert StrategyType.BREAKOUT_CONTINUATION in eligible
    assert StrategyType.MOMENTUM_CONTINUATION in eligible
    assert StrategyType.BREAKOUT_CONTINUATION not in skipped


def test_unstable_regime_routes_only_continuation() -> None:
    eligible, skipped = _strategy_eligibility(
        MarketRegime.HIGH_VOLATILITY_CHAOS,
        tuple(StrategyType),
        higher_timeframe_breakout=True,
    )

    assert eligible == (
        StrategyType.BREAKOUT_CONTINUATION,
        StrategyType.MOMENTUM_CONTINUATION,
    )
    assert StrategyType.TREND_PULLBACK in skipped


def test_breakout_near_miss_reports_retest(monkeypatch: Any) -> None:
    context = _context()
    monkeypatch.setattr(
        "apex.strategies.diagnostics.classify_market_regime",
        lambda unused: MarketRegime.BREAKOUT_EXPANSION,
    )

    diagnostics = build_phase4_diagnostics(
        context,
        evaluated=(StrategyType.BREAKOUT_CONTINUATION,),
        eligible=(StrategyType.BREAKOUT_CONTINUATION,),
        skipped={},
        candidates=(),
    )

    diagnostic = diagnostics[StrategyType.BREAKOUT_CONTINUATION]
    assert diagnostic.candidate_count == 0
    assert diagnostic.higher_timeframe_breakout is True
    assert diagnostic.near_miss_state is EntryState.WAIT_FOR_RETEST
    assert Phase4RejectionCode.MISSING_ENTRY_REFERENCES in diagnostic.rejection_codes


def test_higher_breakout_detector_uses_context_regime(monkeypatch: Any) -> None:
    context = _context()
    monkeypatch.setattr(
        "apex.strategies.diagnostics.classify_market_regime",
        lambda unused: MarketRegime.BREAKOUT_EXPANSION,
    )

    assert has_higher_timeframe_breakout(context) is True
