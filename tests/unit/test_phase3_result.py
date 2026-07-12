from datetime import UTC, datetime, timedelta

from apex.domain import Candle
from apex.phase3 import analyze_phase3
from apex.structure import MarketRegime


def _candles() -> tuple[Candle, ...]:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index in range(25):
        center = 100.0 + (index % 4)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=opened + timedelta(minutes=index),
                close_time=opened + timedelta(minutes=index + 1),
                open=center,
                high=center + 2.0,
                low=center - 2.0,
                close=center + 0.5,
                volume=10.0,
                is_closed=True,
                source="fixture",
            )
        )
    return tuple(candles)


def test_combined_result_exposes_deterministic_market_regime() -> None:
    first = analyze_phase3(_candles())
    second = analyze_phase3(_candles())

    assert isinstance(first.regime, MarketRegime)
    assert first.regime is second.regime
