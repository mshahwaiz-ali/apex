from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apex.domain.models import (
    ExchangeFilterSnapshot,
    LiquidationCluster,
    LiquidationClusterSide,
    LiquidationClusterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)


def test_ticker_snapshot_calculates_spread() -> None:
    ticker = TickerSnapshot(
        symbol="BTC/USDT",
        last_price=64_200,
        bid_price=64_199,
        ask_price=64_201,
        quote_volume_24h=1_500_000_000,
        captured_at=datetime.now(UTC),
        source="binance",
    )

    assert ticker.spread == 2
    assert ticker.spread_percentage == pytest.approx((2 / 64_200) * 100)


def test_ticker_snapshot_rejects_inverted_market() -> None:
    with pytest.raises(
        ValidationError,
        match="bid price cannot exceed ask price",
    ):
        TickerSnapshot(
            symbol="BTC/USDT",
            last_price=64_200,
            bid_price=64_202,
            ask_price=64_201,
            quote_volume_24h=1_500_000_000,
            captured_at=datetime.now(UTC),
            source="binance",
        )


def test_order_book_snapshot_calculates_spread_and_depth_imbalance() -> None:
    book = OrderBookSnapshot(
        symbol="BTC/USDT",
        bids=(
            OrderBookLevel(price=99.0, quantity=2.0),
            OrderBookLevel(price=98.5, quantity=1.0),
        ),
        asks=(
            OrderBookLevel(price=100.0, quantity=1.0),
            OrderBookLevel(price=101.0, quantity=0.5),
        ),
        captured_at=datetime.now(UTC),
        source="fixture",
    )

    assert book.best_bid.price == 99.0
    assert book.best_ask.price == 100.0
    assert book.spread_percentage == pytest.approx((1.0 / 99.5) * 100)
    assert book.depth_imbalance > 0


def test_order_book_snapshot_rejects_unsorted_levels() -> None:
    with pytest.raises(ValidationError, match="bids must be sorted"):
        OrderBookSnapshot(
            symbol="BTC/USDT",
            bids=(
                OrderBookLevel(price=98.0, quantity=1.0),
                OrderBookLevel(price=99.0, quantity=1.0),
            ),
            asks=(OrderBookLevel(price=100.0, quantity=1.0),),
            captured_at=datetime.now(UTC),
            source="fixture",
        )


def test_exchange_filter_snapshot_validates_precision_filters() -> None:
    filters = ExchangeFilterSnapshot(
        symbol="BTC/USDT",
        tick_size=0.1,
        step_size=0.001,
        min_quantity=0.001,
        min_notional=5.0,
        captured_at=datetime.now(UTC),
        source="fixture",
    )

    assert filters.min_notional == 5.0


def test_liquidation_cluster_snapshot_requires_clusters() -> None:
    snapshot = LiquidationClusterSnapshot(
        symbol="BTC/USDT",
        clusters=(
            LiquidationCluster(
                side=LiquidationClusterSide.LONG,
                price=63_800,
                notional=2_000_000,
            ),
        ),
        captured_at=datetime.now(UTC),
        source="fixture",
    )

    assert snapshot.clusters[0].side is LiquidationClusterSide.LONG

    with pytest.raises(ValidationError, match="at least one cluster"):
        LiquidationClusterSnapshot(
            symbol="BTC/USDT",
            clusters=(),
            captured_at=datetime.now(UTC),
            source="fixture",
        )
