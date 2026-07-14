"""Explicit date-range Binance candle acquisition."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import RetryPolicy, request_json
from apex.domain.models import Candle


class BinanceHistoricalRangeProvider:
    """Read-only Binance adapter for closed candles in explicit UTC ranges."""

    BASE_URL = "https://api.binance.com"
    SUPPORTED_TIMEFRAMES: ClassVar[frozenset[str]] = frozenset(
        {"1m", "3m", "5m", "15m", "30m", "1h", "4h"}
    )

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._owns_client = client is None
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "Apex-Trading-Agent/0.1"},
        )

    @property
    def name(self) -> str:
        return "binance"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> BinanceHistoricalRangeProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_candles_range(
        self,
        symbol: str,
        timeframe: str,
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> list[Candle]:
        """Fetch closed candles whose open times fall in ``[start_time, end_time)``."""

        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            supported = ", ".join(sorted(self.SUPPORTED_TIMEFRAMES))
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {supported}")
        _require_aware(start_time, "start time")
        _require_aware(end_time, "end time")
        if start_time >= end_time:
            raise ValueError("historical range start time must be before end time")

        display_symbol = symbol.strip().upper()
        normalized_symbol = display_symbol.replace("/", "").replace("-", "")
        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000) - 1
        cursor_ms = start_ms
        now = datetime.now(UTC)
        candles_by_open_time: dict[datetime, Candle] = {}

        while cursor_ms <= end_ms:
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
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            if not isinstance(payload, list):
                raise ProviderResponseError(
                    "Binance candle-range response must be a list",
                    provider=self.name,
                    operation="fetch historical candle range",
                )
            if not payload:
                break

            last_open_ms: int | None = None
            for row in payload:
                candle = self._parse_candle(
                    row=row,
                    display_symbol=display_symbol,
                    timeframe=timeframe,
                    now=now,
                )
                if start_time <= candle.open_time < end_time and candle.is_closed:
                    candles_by_open_time[candle.open_time] = candle
                last_open_ms = int(candle.open_time.timestamp() * 1000)

            if last_open_ms is None or last_open_ms < cursor_ms:
                break
            next_cursor_ms = last_open_ms + 1
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

    def _parse_candle(
        self,
        *,
        row: Any,
        display_symbol: str,
        timeframe: str,
        now: datetime,
    ) -> Candle:
        if not isinstance(row, list) or len(row) < 7:
            raise ProviderResponseError(
                "Invalid Binance candle row",
                provider=self.name,
                operation="parse historical candle range",
            )
        try:
            open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            close_time = datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC)
            return Candle(
                symbol=display_symbol,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                is_closed=close_time <= now,
                source=self.name,
            )
        except (IndexError, OSError, OverflowError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance candle-range values",
                provider=self.name,
                operation="parse historical candle range",
            ) from exc


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"historical range {name} must be timezone-aware")
