from datetime import UTC, datetime, timedelta

from apex.domain.models import Candle
from apex.features import ActiveCandlePolicy, average_true_range
from apex.liquidity import analyze_liquidity
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


def test_historical_prefix_is_invariant_after_future_candles_are_appended() -> None:
    historical = _candles(28)
    extended = _candles(40)
    decision_time = historical[-1].close_time

    before_append = analyze_strategies(
        _context(historical),
        decision_time=decision_time,
    )
    replayed_prefix = analyze_strategies(
        _context(extended[: len(historical)]),
        decision_time=decision_time,
    )

    assert before_append == replayed_prefix


def test_candle_derived_context_replay_is_deterministic() -> None:
    candles = _candles(32)
    first = _context(candles)
    second = _context(candles)

    assert first == second
    assert analyze_strategies(first, decision_time=candles[-1].close_time) == analyze_strategies(
        second,
        decision_time=candles[-1].close_time,
    )
