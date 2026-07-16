"""Tests for lightweight futures-screening contracts."""

from datetime import UTC, datetime

import pytest

from apex.domain.futures_screening import (
    FuturesScreenerConfig,
    FuturesTickerSnapshot,
)


def test_futures_ticker_snapshot_calculates_market_metrics() -> None:
    ticker = FuturesTickerSnapshot(
        symbol="BTCUSDT",
        exchange_symbol="BTCUSDT",
        last_price=105.0,
        bid_price=100.0,
        ask_price=102.0,
        quote_volume_24h=1_000_000.0,
        price_change_percentage_24h=-12.5,
        high_price_24h=120.0,
        low_price_24h=80.0,
        trade_count_24h=50,
        captured_at=datetime.now(UTC),
        source="test",
    )

    assert ticker.spread == 2.0
    assert ticker.spread_percentage == pytest.approx(1.9801980198)
    assert ticker.absolute_movement_percentage == 12.5
    assert ticker.range_percentage == 50.0


def test_futures_ticker_snapshot_supports_unavailable_optional_fields() -> None:
    ticker = FuturesTickerSnapshot(
        symbol="ETHUSDT",
        exchange_symbol="ETHUSDT",
        last_price=3000.0,
        bid_price=2999.0,
        ask_price=3000.0,
        quote_volume_24h=500_000_000.0,
        price_change_percentage_24h=4.0,
        captured_at=datetime.now(UTC),
        source="test",
    )

    assert ticker.high_price_24h is None
    assert ticker.low_price_24h is None
    assert ticker.trade_count_24h is None
    assert ticker.range_percentage is None


def test_futures_ticker_snapshot_rejects_crossed_bid_and_ask() -> None:
    with pytest.raises(ValueError, match="bid_price cannot exceed ask_price"):
        FuturesTickerSnapshot(
            symbol="BTCUSDT",
            exchange_symbol="BTCUSDT",
            last_price=100.0,
            bid_price=101.0,
            ask_price=100.0,
            quote_volume_24h=1_000_000.0,
            price_change_percentage_24h=2.0,
            captured_at=datetime.now(UTC),
            source="test",
        )


def test_futures_ticker_snapshot_rejects_invalid_high_low_range() -> None:
    with pytest.raises(
        ValueError,
        match="low_price_24h cannot exceed high_price_24h",
    ):
        FuturesTickerSnapshot(
            symbol="BTCUSDT",
            exchange_symbol="BTCUSDT",
            last_price=100.0,
            bid_price=99.0,
            ask_price=100.0,
            quote_volume_24h=1_000_000.0,
            price_change_percentage_24h=2.0,
            high_price_24h=90.0,
            low_price_24h=95.0,
            captured_at=datetime.now(UTC),
            source="test",
        )


def test_futures_screener_config_rejects_negative_liquidity() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_quote_volume_24h cannot be negative",
    ):
        FuturesScreenerConfig(minimum_quote_volume_24h=-1.0)


def test_futures_screener_config_rejects_negative_spread() -> None:
    with pytest.raises(
        ValueError,
        match="maximum_spread_percentage cannot be negative",
    ):
        FuturesScreenerConfig(maximum_spread_percentage=-1.0)


def test_futures_screener_config_rejects_negative_movement() -> None:
    with pytest.raises(
        ValueError,
        match="minimum_absolute_movement_percentage cannot be negative",
    ):
        FuturesScreenerConfig(
            minimum_absolute_movement_percentage=-1.0,
        )


def test_futures_screener_config_rejects_non_positive_shortlist_size() -> None:
    with pytest.raises(ValueError, match="shortlist_size must be positive"):
        FuturesScreenerConfig(shortlist_size=0)
