from __future__ import annotations

import pytest
from tests.unit.features.test_registry import make_candles

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
