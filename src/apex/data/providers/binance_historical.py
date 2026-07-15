"""Explicit historical-range support for Binance Spot candles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Self

from apex.data.providers.binance import BinanceMarketDataProvider
from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import request_json
from apex.domain.models import Candle


class BinanceHistoricalRangeMarketDataProvider(BinanceMarketDataProvider):
    """Read-only Binance Spot adapter with forward range pagination."""

    _TIMEFRAME_MILLISECONDS: ClassVar[dict[str, int]] = {
        "1m": 60_000,
        "3m": 180_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
    }

    def __enter__(self) -> Self:
        """Preserve the historical provider type inside context-manager blocks."""

        return self

    def fetch_candles_range(
        self,
        symbol: str,
        timeframe: str,
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Candle]:
        """Fetch closed candles whose open times fall in ``[start_time, end_time)``."""

        self._validate_range(timeframe, start_time, end_time)
        normalized_symbol = self._normalize_symbol(symbol)
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        interval_ms = self._TIMEFRAME_MILLISECONDS[timeframe]
        now = datetime.now(UTC)
        candles_by_open_time: dict[datetime, Candle] = {}
        cursor_ms = start_ms

        while cursor_ms < end_ms:
            payload = request_json(
                self._client,
                "GET",
                "/api/v3/klines",
                provider=self.name,
                operation="fetch historical candle range",
                retry_policy=self._retry_policy,
                sleep=self._sleep,
                params={
                    "symbol": normalized_symbol,
                    "interval": timeframe,
                    "startTime": cursor_ms,
                    "endTime": end_ms - 1,
                    "limit": 1000,
                },
            )
            if not isinstance(payload, list):
                raise ProviderResponseError(
                    "Binance historical candle response must be a list",
                    provider=self.name,
                    operation="fetch historical candle range",
                )
            if not payload:
                break

            page = [
                self._parse_candle(
                    row=row,
                    display_symbol=symbol.upper(),
                    timeframe=timeframe,
                    now=now,
                )
                for row in payload
            ]
            page.sort(key=lambda candle: candle.open_time)
            for candle in page:
                if start_time <= candle.open_time < end_time and candle.is_closed:
                    candles_by_open_time[candle.open_time] = candle

            next_cursor_ms = int(page[-1].open_time.timestamp() * 1000) + interval_ms
            if next_cursor_ms <= cursor_ms:
                break
            cursor_ms = next_cursor_ms
            if len(payload) < 1000:
                break

        candles = sorted(candles_by_open_time.values(), key=lambda candle: candle.open_time)
        if not candles:
            raise ProviderResponseError(
                "Binance returned no closed candles for the requested range",
                provider=self.name,
                operation="fetch historical candle range",
            )
        return candles

    @classmethod
    def _validate_range(
        cls,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        if timeframe not in cls._TIMEFRAME_MILLISECONDS:
            supported = ", ".join(sorted(cls._TIMEFRAME_MILLISECONDS))
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {supported}")
        for label, value in (("start", start_time), ("end", end_time)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"historical range {label} time must be timezone-aware")
        if start_time >= end_time:
            raise ValueError("historical range start time must be before end time")
        if end_time > datetime.now(UTC):
            raise ValueError("historical range end time cannot be in the future")
