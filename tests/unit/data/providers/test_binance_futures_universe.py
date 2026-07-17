"""Tests for Binance futures universe metadata."""

import httpx
import pytest

from apex.data.providers.binance_futures_universe import (
    BinanceFuturesUniverseProvider,
)
from apex.data.providers.errors import ProviderResponseError


def _symbol(
    symbol: str,
    base_asset: str,
    *,
    quote_asset: str = "USDT",