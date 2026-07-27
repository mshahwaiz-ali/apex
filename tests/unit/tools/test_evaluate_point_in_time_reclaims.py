from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from tools.evaluate_point_in_time_reclaims import (
    ReclaimOutcome,
    _deduplicate,
    _point_in_time_outcome,
)

from apex.domain.models import Candle


def _candle(
    minute: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute * 5)
    return Candle(
        symbol="BTC/USDT",
        timeframe="5m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=5),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        is_closed=True,
        source="test",
    )


def test_point_in_time_reclaim_does_not_use_future_deep_failure_to_select() -> None:
    candles = (
        _candle(0, open_=100.0, high=100.1, low=98.9, close=99.2),
        _candle(1, open_=99.2, high=100.6, low=99.1, close=100.5),
        _candle(2, open_=100.5, high=100.6, low=98.0, close=98.2),
    )
    trade = {
        "decision_time": datetime(2025, 12, 31, tzinfo=UTC).isoformat(),
        "signal": {
            "direction": "long",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "target_price": 102.0,
            "strategy": "trend_pullback",
            "candidate_id": "candidate-1",
        },
        "metadata": {
            "first_stop_touch_time": candles[0].close_time.isoformat(),
            "configured_entry_fee_pct": 0.05,
            "configured_entry_slippage_pct": 0.02,
            "configured_exit_fee_pct": 0.05,
            "configured_exit_slippage_pct": 0.02,
        },
    }

    outcome = _point_in_time_outcome(
        trade,
        symbol="BTC/USDT",
        candles=candles,
        by_close={item.close_time: index for index, item in enumerate(candles)},
        outcome_bars=24,
    )

    assert outcome is not None
    assert outcome.reclaim_time == candles[1].close_time
    assert outcome.outcome == "stop"
    assert outcome.net_r < 0.0


def test_episode_deduplication_uses_pre_outcome_ordering() -> None:
    base = ReclaimOutcome(
        symbol="BTC/USDT",
        direction="long",
        strategy="trend_pullback",
        candidate_id="later",
        decision_time=datetime(2026, 1, 2, tzinfo=UTC),
        reclaim_time=datetime(2026, 1, 3, tzinfo=UTC),
        event_id="event-later",
        episode_id="episode",
        entry_price=100.0,
        stop_price=99.0,
        target_price=102.0,
        outcome="target",
        net_r=2.0,
        bars_to_outcome=1,
        same_candle_ambiguous=False,
    )
    earlier = replace(
        base,
        candidate_id="earlier",
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        event_id="event-earlier",
        outcome="stop",
        net_r=-1.0,
    )

    selected = _deduplicate((base, earlier), key_name="episode_id")

    assert selected == (earlier,)
