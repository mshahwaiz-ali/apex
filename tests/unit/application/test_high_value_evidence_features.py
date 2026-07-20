from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.high_value_evidence_features import (
    ChangeDirection,
    PriceOpenInterestState,
    derive_price_open_interest_relationship,
    derive_taker_flow_imbalance_proxy,
)
from apex.domain.futures_evidence import OpenInterestSnapshot, TakerFlowSnapshot
from apex.domain.models import Candle

NOW = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)


def _candle(index: int, close: float, *, closed: bool = True) -> Candle:
    opened = NOW - timedelta(minutes=25 - index * 5)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=100.0,
        is_closed=closed,
        source="fixture",
    )


def _oi(index: int, value: float, *, skew_seconds: int = 0) -> OpenInterestSnapshot:
    captured = NOW - timedelta(minutes=20 - index * 5) + timedelta(seconds=skew_seconds)
    return OpenInterestSnapshot(
        symbol="BTCUSDT",
        period="5m",
        open_interest=value,
        open_interest_value=value * 100.0,
        captured_at=captured,
        source="fixture",
    )


def test_taker_flow_proxy_is_fresh_cumulative_and_directional() -> None:
    values = (
        TakerFlowSnapshot(
            symbol="BTCUSDT",
            period="5m",
            buy_volume=70.0,
            sell_volume=30.0,
            buy_sell_ratio=70.0 / 30.0,
            captured_at=NOW - timedelta(minutes=10),
            source="fixture",
        ),
        TakerFlowSnapshot(
            symbol="BTCUSDT",
            period="5m",
            buy_volume=80.0,
            sell_volume=20.0,
            buy_sell_ratio=4.0,
            captured_at=NOW - timedelta(minutes=5),
            source="fixture",
        ),
    )

    proxy = derive_taker_flow_imbalance_proxy(values, as_of=NOW)

    assert proxy is not None
    assert proxy.buy_volume == 150.0
    assert proxy.sell_volume == 50.0
    assert proxy.imbalance == 0.5
    assert proxy.sample_count == 2
    assert proxy.source_label == "taker_flow_history_proxy"


def test_taker_flow_proxy_rejects_stale_or_empty_evidence() -> None:
    stale = (
        TakerFlowSnapshot(
            symbol="BTCUSDT",
            period="5m",
            buy_volume=10.0,
            sell_volume=5.0,
            buy_sell_ratio=2.0,
            captured_at=NOW - timedelta(hours=1),
            source="fixture",
        ),
    )

    assert derive_taker_flow_imbalance_proxy((), as_of=NOW) is None
    assert derive_taker_flow_imbalance_proxy(stale, as_of=NOW) is None


def test_price_open_interest_relationship_requires_timestamp_alignment() -> None:
    relationship = derive_price_open_interest_relationship(
        (_candle(0, 100.0), _candle(1, 102.0), _candle(2, 105.0), _candle(3, 110.0)),
        (_oi(0, 1000.0, skew_seconds=10), _oi(3, 1200.0, skew_seconds=-10)),
        as_of=NOW,
    )

    assert relationship is not None
    assert relationship.price_direction is ChangeDirection.RISING
    assert relationship.open_interest_direction is ChangeDirection.RISING
    assert relationship.state is PriceOpenInterestState.LONG_BUILDUP
    assert relationship.price_change_pct == 10.0
    assert relationship.open_interest_change_pct == 20.0
    assert relationship.maximum_alignment_skew_seconds == 10.0


def test_price_open_interest_relationship_rejects_unsynchronized_inputs() -> None:
    relationship = derive_price_open_interest_relationship(
        (_candle(0, 100.0), _candle(1, 101.0)),
        (_oi(0, 1000.0, skew_seconds=400), _oi(1, 1100.0, skew_seconds=400)),
        as_of=NOW,
        max_alignment_skew=timedelta(seconds=30),
    )

    assert relationship is None


def test_price_open_interest_relationship_classifies_short_covering() -> None:
    relationship = derive_price_open_interest_relationship(
        (_candle(0, 100.0), _candle(1, 104.0)),
        (_oi(0, 1000.0), _oi(1, 900.0)),
        as_of=NOW,
    )

    assert relationship is not None
    assert relationship.state is PriceOpenInterestState.SHORT_COVERING
