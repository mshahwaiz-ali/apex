from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apex.application.market_intelligence import (
    CoinArchetype,
    EarlyWarningState,
    RegimeHysteresis,
    assess_early_warning,
    classify_coin_archetype,
)
from apex.domain.futures_evidence import (
    MarketEvidenceBundle,
    OpenInterestSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.models import Candle
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _context(
    *, final_close: float, oi_values: tuple[float, float], taker_ratio: float
) -> StrategyContext:
    candles = tuple(
        Candle(
            symbol="ALTUSDT",
            timeframe="5m",
            open_time=NOW - timedelta(minutes=5 * (101 - index)),
            close_time=NOW - timedelta(minutes=5 * (100 - index)),
            open=100,
            high=max(100, final_close if index == 99 else 100) + 0.1,
            low=min(100, final_close if index == 99 else 100) - 0.1,
            close=final_close if index == 99 else 100,
            volume=1000,
            is_closed=True,
            source="fixture",
        )
        for index in range(100)
    )
    evidence = MarketEvidenceBundle(
        symbol="ALTUSDT",
        as_of=NOW,
        open_interest=tuple(
            OpenInterestSnapshot(
                "ALTUSDT", "5m", value, value, NOW - timedelta(minutes=5 * (1 - index)), "fixture"
            )
            for index, value in enumerate(oi_values)
        ),
        taker_flow=(
            TakerFlowSnapshot("ALTUSDT", "5m", taker_ratio * 100, 100, taker_ratio, NOW, "fixture"),
        ),
        source="fixture",
    )
    frame = TimeframeContext(
        timeframe="5m",
        role=TimeframeRole.ENTRY,
        current_price=final_close,
        features=FeatureSnapshot(atr=1, range_position=0.8, volatility_expansion=1.0),
        structure=SimpleNamespace(),
        liquidity=SimpleNamespace(),
        recent_candles=candles,
    )
    return StrategyContext("ALTUSDT", (frame,), market_evidence=evidence)


def test_price_oi_flow_matrix_detects_bullish_participation() -> None:
    context = _context(final_close=101, oi_values=(100, 102), taker_ratio=1.2)
    warning = assess_early_warning(context, context.market_evidence)
    assert warning.state is EarlyWarningState.BULLISH_PARTICIPATION
    assert warning.direction == "long"


def test_rising_price_with_contracting_oi_is_short_covering() -> None:
    context = _context(final_close=101, oi_values=(100, 98), taker_ratio=1.0)
    warning = assess_early_warning(context, context.market_evidence)
    assert warning.state is EarlyWarningState.SHORT_COVERING


def test_derivatives_flow_alone_never_creates_direction() -> None:
    context = _context(final_close=100, oi_values=(100, 105), taker_ratio=1.5)
    warning = assess_early_warning(context, context.market_evidence)
    assert warning.direction is None


def test_archetype_and_hysteresis_are_deterministic() -> None:
    context = _context(final_close=100, oi_values=(100, 101), taker_ratio=1.0)
    assert classify_coin_archetype(context) is CoinArchetype.LIQUID_ALT
    guard = RegimeHysteresis()
    assert guard.select("trend", "range", 0.60) == "trend"
    assert guard.select("trend", "range", 0.75) == "range"


def test_major_archetype_accepts_display_symbol_separator() -> None:
    context = _context(final_close=100, oi_values=(100, 101), taker_ratio=1.0)
    major = StrategyContext("BTC/USDT", context.frames, market_evidence=context.market_evidence)
    assert classify_coin_archetype(major) is CoinArchetype.MAJOR
