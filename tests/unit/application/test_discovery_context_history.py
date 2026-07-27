from __future__ import annotations

from datetime import timedelta

import pytest
from tests.unit.features.test_registry import make_candles

from apex.application import discovery_context
from apex.application.discovery_context import _frame_from_candles
from apex.strategies.context import TimeframeRole


def _build_frame(candle_count: int):
    candles = make_candles(candle_count)
    return _frame_from_candles(
        "BTC/USDT",
        "15m",
        TimeframeRole.SETUP,
        candles,
        received_at=candles[-1].close_time,
        max_staleness_seconds=None,
        ticker_price=None,
        spread_percentage=None,
        order_book_snapshot=None,
        exchange_filter_snapshot=None,
        mark_price=None,
        index_price=None,
    )


def test_canonical_context_accepts_short_history_above_required_feature_floor() -> None:
    frame, _ = _build_frame(117)

    assert frame.features.ema_slow is not None
    assert len(frame.recent_candles) == 117


def test_canonical_context_labels_history_below_required_feature_floor() -> None:
    with pytest.raises(ValueError, match=r"INSUFFICIENT_HISTORY.*49 usable candles"):
        _build_frame(49)


def test_volatility_expansion_preserves_values_above_one() -> None:
    candles = make_candles(117)
    candles[-1] = candles[-1].model_copy(
        update={
            "high": candles[-1].high + 20.0,
            "low": candles[-1].low - 20.0,
        }
    )

    frame, _ = _frame_from_candles(
        "BTC/USDT",
        "15m",
        TimeframeRole.SETUP,
        candles,
        received_at=candles[-1].close_time,
        max_staleness_seconds=None,
        ticker_price=None,
        spread_percentage=None,
        order_book_snapshot=None,
        exchange_filter_snapshot=None,
        mark_price=None,
        index_price=None,
    )

    assert frame.features.volatility_expansion is not None
    assert frame.features.volatility_expansion > 1.8


def test_active_candle_keeps_structure_relative_volume_aligned(monkeypatch) -> None:
    candles = make_candles(118)
    candles[-1] = candles[-1].model_copy(update={"is_closed": False})
    captured: dict[str, object] = {}
    original = discovery_context.analyze_structure_and_liquidity

    def capture_analysis(candles, **kwargs):
        captured["candles"] = tuple(candles)
        captured["relative_volume"] = tuple(kwargs["relative_volume"])
        return original(candles, **kwargs)

    monkeypatch.setattr(
        discovery_context,
        "analyze_structure_and_liquidity",
        capture_analysis,
    )

    frame, _ = _frame_from_candles(
        "BTC/USDT",
        "15m",
        TimeframeRole.SETUP,
        candles,
        received_at=candles[-1].close_time,
        max_staleness_seconds=None,
        ticker_price=None,
        spread_percentage=None,
        order_book_snapshot=None,
        exchange_filter_snapshot=None,
        mark_price=None,
        index_price=None,
    )

    analyzed_candles = captured["candles"]
    relative_volume = captured["relative_volume"]
    assert len(analyzed_candles) == len(relative_volume) == len(candles) - 1
    assert all(candle.is_closed for candle in analyzed_candles)
    assert frame.active_candle is True


def test_context_excludes_future_rows_and_reclassifies_race_close_as_active() -> None:
    candles = make_candles(119)
    decision_time = candles[-2].open_time + timedelta(
        seconds=(candles[-2].close_time - candles[-2].open_time).total_seconds() / 2
    )

    frame, _ = _frame_from_candles(
        "BTC/USDT",
        "15m",
        TimeframeRole.SETUP,
        candles,
        received_at=decision_time,
        max_staleness_seconds=None,
        ticker_price=None,
        spread_percentage=None,
        order_book_snapshot=None,
        exchange_filter_snapshot=None,
        mark_price=None,
        index_price=None,
    )

    assert len(frame.recent_candles) == 118
    assert frame.recent_candles[-1].open_time == candles[-2].open_time
    assert frame.recent_candles[-1].is_closed is False
    assert all(candle.open_time <= decision_time for candle in frame.recent_candles)
