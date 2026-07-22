from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features import FeatureOutputShape
from apex.features.registry import (
    FeatureAuditEntry,
    FeatureRegistry,
    IndicatorPeriods,
    create_default_feature_registry,
)

START = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)


def make_candles(count: int = 220) -> list[Candle]:
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


def test_default_registry_exposes_explicit_ema_time_horizons() -> None:
    registry = create_default_feature_registry()
    results = registry.calculate_all(make_candles())

    assert results["ema_20"][0].spec.name == "ema_close_20"
    assert results["ema_50"][0].spec.name == "ema_close_50"
    assert results["ema_200"][0].spec.name == "ema_close_200"
    assert results["ema_20"][0].latest is not None
    assert results["ema_50"][0].latest is not None
    assert results["ema_200"][0].latest is not None


def test_role_profile_changes_fast_indicator_periods_without_changing_group_contract() -> None:
    registry = create_default_feature_registry(
        IndicatorPeriods(
            ema_fast=9,
            ema_slow=21,
            rsi=9,
            roc=6,
            macd_fast=5,
            macd_slow=13,
            macd_signal=4,
        )
    )
    results = registry.calculate_all(make_candles())

    assert results["ema_20"][0].spec.name == "ema_close_9"
    assert results["ema_50"][0].spec.name == "ema_close_21"
    assert results["rsi_14"][0].spec.name == "rsi_9"
    assert results["macd"][2].spec.name == "macd_histogram_5_13_4"


def test_registry_audit_exposes_feature_contract_metadata() -> None:
    registry = create_default_feature_registry()
    first = registry.audit(make_candles())
    second = registry.audit(make_candles())

    assert first == second
    assert all(isinstance(entry, FeatureAuditEntry) for entry in first)
    assert any(
        entry.group_name == "atr_14"
        and entry.feature_name == "atr_14"
        and entry.minimum_candles == 14
        and entry.output_shape is FeatureOutputShape.SERIES
        for entry in first
    )
    assert all(entry.finite_values + entry.missing_values == entry.output_length for entry in first)
