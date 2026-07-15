"""Provider-independent live spot eligibility metadata construction."""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from apex.domain.models import Candle, TickerSnapshot
from apex.domain.spot_market import SpotMarketMetadata


def build_spot_market_metadata(
    *,
    symbol: str,
    quote_asset: str,
    ticker: TickerSnapshot,
    candles: Sequence[Candle],