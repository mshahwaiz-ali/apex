"""Focused shadow replay entry-zone parity tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apex.backtesting.contracts import BacktestConfig
from apex.backtesting.engine import simulate_trade
from apex.cli_commands.backtesting import (
    _build_shadow_signal,
    _shadow_source_distribution,
    _signal_from_geometry_audit,
)
from apex.domain.models import Candle

DECISION_TIME = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _candle(*, low: float, high: float, close: float) -> Candle:
    return Candle(
        symbol="SUIUSDT",
        timeframe="5m",
        source="test",
        open_time=DECISION_TIME,
        close_time=datetime(2026, 7, 23, 12, 5, tzinfo=UTC),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
    )


def test_geometry_rejected_shadow_signal_preserves_real_entry_zone() -> None:
    analysis = SimpleNamespace(symbol="SUIUSDT", generated_at=DECISION_TIME)
    audit = {
        "state": "reject",
        "candidate_id": "momentum_breakout:long:test",
        "diagnostics": {
            "selected_entry": 0.7465543876,
            "entry_zone_low": 0.7464831743,
            "entry_zone_high": 0.7466256008,
            "executable_stop": 0.742,
            "tp1_price": 0.752,
        },
    }

    signal = _signal_from_geometry_audit(analysis, audit)

    assert signal is not None
    assert signal.entry_price == pytest.approx(0.7465543876)
    assert signal.entry_zone_low == pytest.approx(0.7464831743)
    assert signal.entry_zone_high == pytest.approx(0.7466256008)
    assert signal.replay_source == "geometry_rejected"


def test_shadow_signal_uses_point_entry_fallback_when_range_is_missing() -> None:
    signal = _build_shadow_signal(
        symbol="SUIUSDT",
        decision_time=DECISION_TIME,
        candidate_id="momentum_breakout:long:test",
        strategy="momentum_breakout",
        direction="long",
        entry=0.74655,
        stop=0.742,
        target=0.752,
        confidence=50.0,
        source="score_or_collision_rejected",
    )

    assert signal is not None
    assert signal.entry_price == pytest.approx(0.74655)
    assert signal.entry_zone_low == pytest.approx(0.74655)
    assert signal.entry_zone_high == pytest.approx(0.74655)


def test_conservative_fill_consumes_preserved_shadow_zone() -> None:
    signal = _build_shadow_signal(
        symbol="SUIUSDT",
        decision_time=DECISION_TIME,
        candidate_id="momentum_breakout:long:test",
        strategy="momentum_breakout",
        direction="long",
        entry=0.74655,
        entry_zone_low=0.74648,
        entry_zone_high=0.74663,
        stop=0.742,
        target=0.752,
        confidence=50.0,
        source="geometry_rejected",
    )
    assert signal is not None

    trade = simulate_trade(
        signal,
        (_candle(low=0.74650, high=0.74660, close=0.74658),),
        config=BacktestConfig(
            maximum_holding_candles=1,
            fee_pct=0.0,
            slippage_pct=0.0,
        ),
    )

    assert trade.metadata["entry_raw_fill_price"] == pytest.approx(0.74660)
    assert trade.metadata["entry_zone_low"] == pytest.approx(0.74648)
    assert trade.metadata["entry_zone_high"] == pytest.approx(0.74663)


def test_shadow_source_labels_and_metric_partition_remain_unchanged() -> None:
    geometry = _build_shadow_signal(
        symbol="SUIUSDT",
        decision_time=DECISION_TIME,
        candidate_id="momentum_breakout:long:geometry",
        strategy="momentum_breakout",
        direction="long",
        entry=0.74655,
        entry_zone_low=0.74648,
        entry_zone_high=0.74663,
        stop=0.742,
        target=0.752,
        confidence=0.0,
        source="geometry_rejected",
    )
    rejected = _build_shadow_signal(
        symbol="SUIUSDT",
        decision_time=DECISION_TIME,
        candidate_id="momentum_breakout:long:rejected",
        strategy="momentum_breakout",
        direction="long",
        entry=0.74655,
        stop=0.742,
        target=0.752,
        confidence=0.0,
        source="score_or_collision_rejected",
    )
    assert geometry is not None
    assert rejected is not None

    geometry_trade = simulate_trade(
        geometry,
        (_candle(low=0.74650, high=0.74660, close=0.74658),),
        config=BacktestConfig(maximum_holding_candles=1, fee_pct=0.0, slippage_pct=0.0),
    )
    rejected_trade = simulate_trade(
        rejected,
        (_candle(low=0.74650, high=0.74660, close=0.74658),),
        config=BacktestConfig(maximum_holding_candles=1, fee_pct=0.0, slippage_pct=0.0),
    )

    assert _shadow_source_distribution((geometry_trade, rejected_trade)) == {
        "geometry_rejected": 1,
        "score_or_collision_rejected": 1,
    }
    assert geometry_trade.signal.replay_source != "production"
    assert rejected_trade.signal.replay_source != "production"
