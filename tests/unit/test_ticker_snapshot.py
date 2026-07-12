from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apex.domain.models import TickerSnapshot


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
