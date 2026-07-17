from datetime import UTC, datetime, timedelta

from apex.domain.models import Candle
from apex.features import ActiveCandlePolicy, average_true_range
from apex.liquidity import analyze_liquidity
from apex.scoring import CandidateSelectionResult, analyze_candidate_selection
from apex.strategies import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    analyze_strategies,
)
from apex.structure import analyze_structure

_START = datetime(2026, 7, 1, tzinfo=UTC)


def _candles(count: int) -> tuple[Candle, ...]:
    candles: list[Candle] = []
    previous = 100.0
    for index in range(count):
        drift = 0.45 if (index // 6) % 2 == 0 else -0.25
        close = previous + drift + (0.15 if index % 3 == 0 else -0.05)
        high = max(previous, close) + 0.6
        low = min(previous, close) - 0.6
        open_time = _START + timedelta(minutes=5 * index)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="5m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=5),
                open=previous,
                high=high,
                low=low,
                close=close,
                volume=1_000.0 + index * 10.0,
                is_closed=True,
                source="fixture",
            )
        )
        previous = close
    return tuple(candles)


def _context(candles: tuple[Candle, ...]) -> StrategyContext:
    atr_result = average_true_range(
        candles,
        period=5,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    atr = atr_result.values[-1]
    assert atr is not None

    structure = analyze_structure(
        candles,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    liquidity = analyze_liquidity(
        candles,
        structure,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    return StrategyContext(
        symbol="BTC/USDT",
        frames=(
            TimeframeContext(
                timeframe="5m",
                role=TimeframeRole.ENTRY,
                current_price=candles[-1].close,
                features=FeatureSnapshot(atr=atr),
                structure=structure,
                liquidity=liquidity,
            ),
        ),
    )


def _phase5(candles: tuple[Candle, ...]) -> CandidateSelectionResult:
    decision_time = candles[-1].close_time
    phase4 = analyze_strategies(_context(candles), decision_time=decision_time)
    return analyze_candidate_selection(phase4)


def test_phase5_historical_prefix_is_invariant_after_future_candles() -> None:
    historical = _candles(28)
    extended = _candles(40)

    before_append = _phase5(historical)
    replayed_prefix = _phase5(extended[: len(historical)])

    assert before_append == replayed_prefix
    assert before_append.all_scored_candidates == replayed_prefix.all_scored_candidates
    assert before_append.ranked_candidates == replayed_prefix.ranked_candidates
    assert before_append.selected_candidate == replayed_prefix.selected_candidate


def test_phase5_candle_derived_replay_is_deterministic() -> None:
    candles = _candles(32)

    first = _phase5(candles)
    second = _phase5(candles)

    assert first == second
    assert tuple(item.breakdown for item in first.all_scored_candidates) == tuple(
        item.breakdown for item in second.all_scored_candidates
    )
