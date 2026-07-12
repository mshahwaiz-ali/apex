from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features.registry import FeatureRegistry, create_default_feature_registry

START = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)


def make_candles(count: int = 40) -> list[Candle]:
    return [
        Candle(
            symbol="BTC/USDT",
            timeframe="15m",
            open_time=START + timedelta(minutes=15 * index),
            close_time=START + timedelta(minutes=15 * (index + 1)),
            open=100.0 + index,
            high=102.0 + index,
            low=99.0 + index,
            close=101.0 + index,
            volume=1000.0 + index,
            is_closed=True,
            source="test",
        )
        for index in range(count)
    ]


def test_registry_rejects_duplicate_names() -> None:
    registry = FeatureRegistry()
    registry.register("sample", lambda candles: ())

    with pytest.raises(ValueError, match="already registered"):
        registry.register("sample", lambda candles: ())


def test_registry_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown feature"):
        FeatureRegistry().calculate("missing", make_candles())


def test_default_registry_is_ordered_and_deterministic() -> None:
    registry = create_default_feature_registry()
    candles = make_candles()

    first = registry.calculate_all(candles)
    second = registry.calculate_all(candles)

    assert tuple(first) == registry.names
    assert first == second
    assert first["macd"][2].spec.name == "macd_histogram_12_26_9"
    assert first["bollinger_20"][3].spec.name == "bollinger_width_20"
