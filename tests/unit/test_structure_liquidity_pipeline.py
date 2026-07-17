from datetime import UTC, datetime, timedelta

import pytest

from apex.domain import Candle
from apex.features import ActiveCandlePolicy
from apex.market_analysis import MarketAnalysisResult, analyze_structure_and_liquidity
from apex.structure import SwingPoint, SwingType
from apex.structure.contracts import PivotStatus


def _candles(count: int = 25, *, active_final: bool = False) -> tuple[Candle, ...]:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index in range(count):
        center = 100.0 + (index % 6) - 2.5
        high = center + 2.0
        low = center - 2.0
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=opened + timedelta(minutes=index),
                close_time=opened + timedelta(minutes=index + 1),
                open=center - 0.25,
                high=high,
                low=low,
                close=center + 0.25,
                volume=10.0 + index,
                is_closed=not (active_final and index == count - 1),
                source="fixture",
            )
        )
    return tuple(candles)


def test_phase3_pipeline_is_deterministic_and_does_not_mutate_input() -> None:
    candles = _candles()
    original = tuple(candles)

    first = analyze_structure_and_liquidity(candles)
    second = analyze_structure_and_liquidity(candles)

    assert isinstance(first, MarketAnalysisResult)
    assert first == second
    assert candles == original


def test_default_pipeline_drops_active_final_candle() -> None:
    active = _candles(active_final=True)
    closed_prefix = active[:-1]

    active_result = analyze_structure_and_liquidity(active)
    closed_result = analyze_structure_and_liquidity(closed_prefix)

    assert active_result == closed_result


def test_pipeline_can_explicitly_include_active_final_candle() -> None:
    candles = _candles(active_final=True)

    result = analyze_structure_and_liquidity(
        candles,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )

    assert isinstance(result, MarketAnalysisResult)


def test_pipeline_rejects_empty_and_insufficient_sequences() -> None:
    with pytest.raises(ValueError, match="candle series cannot be empty"):
        analyze_structure_and_liquidity(())

    with pytest.raises(ValueError, match="requires at least"):
        analyze_structure_and_liquidity(_candles(1))


def test_phase3_contract_rejects_non_finite_price() -> None:
    with pytest.raises(ValueError, match="swing price must be finite"):
        SwingPoint(
            index=1,
            time=datetime(2026, 1, 1, tzinfo=UTC),
            price=float("nan"),
            kind=SwingType.HIGH,
            status=PivotStatus.CONFIRMED,
            left_window=1,
            right_window=1,
        )


def test_pipeline_outputs_are_chronologically_ordered() -> None:
    result = analyze_structure_and_liquidity(_candles())

    assert result.structure.swings == tuple(
        sorted(result.structure.swings, key=lambda item: (item.index, item.kind.value))
    )
    assert result.structure.breaks == tuple(
        sorted(
            result.structure.breaks,
            key=lambda item: (item.candle_index, item.direction.value),
        )
    )
    assert result.liquidity.sweeps == tuple(
        sorted(
            result.liquidity.sweeps,
            key=lambda item: (item.candle_index, item.zone.side.value),
        )
    )


def test_pipeline_accepts_aligned_relative_volume() -> None:
    candles = _candles()
    relative_volume = tuple(1.5 for _ in candles)

    result = analyze_structure_and_liquidity(candles, relative_volume=relative_volume)

    assert isinstance(result, MarketAnalysisResult)


def test_pipeline_rejects_misaligned_relative_volume() -> None:
    candles = _candles()

    with pytest.raises(ValueError, match="length must match candle count"):
        analyze_structure_and_liquidity(candles, relative_volume=(1.0,))


def test_pipeline_rejects_non_finite_relative_volume() -> None:
    candles = _candles()
    relative_volume = [1.0 for _ in candles]
    relative_volume[5] = float("nan")

    with pytest.raises(ValueError, match="finite and non-negative"):
        analyze_structure_and_liquidity(candles, relative_volume=relative_volume)
