"""Explicit historical-range support for Binance Spot candles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Self

from apex.data.providers.binance import BinanceMarketDataProvider
from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import request_json
from apex.domain.models import Candle


class BinanceHistoricalRangeMarketDataProvider(BinanceMarketDataProvider):