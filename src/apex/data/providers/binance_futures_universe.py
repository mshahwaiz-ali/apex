"""Binance USDT-margined futures contract-universe provider."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from apex.data.providers.errors import ProviderResponseError
from apex.data.providers.http import RetryPolicy, request_json
from apex.domain.futures_market import FuturesContractMetadata


class BinanceFuturesUniverseProvider:
    """Read-only adapter for Binance futures exchange metadata."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        metadata_cache_ttl_seconds: float = 3_600.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if metadata_cache_ttl_seconds < 0:
            raise ValueError("metadata cache TTL cannot be negative")
        self._owns_client = client is None
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._monotonic = monotonic
        self._metadata_cache_ttl_seconds = metadata_cache_ttl_seconds
        self._cached_contracts: tuple[FuturesContractMetadata, ...] | None = None
        self._cache_expires_at = 0.0
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "Apex-Trading-Agent/0.1"},
        )

    @property
    def name(self) -> str:
        return "binance-futures"

    def close(self) -> None:
        """Close the internally managed HTTP client."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> BinanceFuturesUniverseProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_futures_contracts(self) -> tuple[FuturesContractMetadata, ...]:
        """Fetch, normalize, and temporarily cache Binance futures metadata."""

        now = self._monotonic()
        if self._cached_contracts is not None and now < self._cache_expires_at:
            return self._cached_contracts

        payload = request_json(
            self._client,
            "GET",
            "/fapi/v1/exchangeInfo",
            provider=self.name,
            operation="fetch futures exchange metadata",
            retry_policy=self._retry_policy,
            sleep=self._sleep,
        )

        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Binance futures exchange info response must be an object",
                provider=self.name,
                operation="fetch futures exchange metadata",
            )

        symbols = payload.get("symbols")
        if not isinstance(symbols, list):
            raise ProviderResponseError(
                "Binance futures exchange info must contain a symbol list",
                provider=self.name,
                operation="fetch futures exchange metadata",
            )

        contracts: list[FuturesContractMetadata] = []
        for item in symbols:
            try:
                contracts.append(self._parse_contract(item))
            except ProviderResponseError:
                continue

        if symbols and not contracts:
            raise ProviderResponseError(
                "Binance futures exchange info contained no valid contracts",
                provider=self.name,
                operation="parse futures exchange metadata",
            )

        normalized = tuple(sorted(contracts, key=lambda item: item.exchange_symbol))
        self._cached_contracts = normalized
        self._cache_expires_at = now + self._metadata_cache_ttl_seconds
        return normalized

    def clear_metadata_cache(self) -> None:
        """Invalidate cached exchange metadata."""

        self._cached_contracts = None
        self._cache_expires_at = 0.0

    def _parse_contract(self, value: Any) -> FuturesContractMetadata:
        if not isinstance(value, dict):
            raise ProviderResponseError(
                "Invalid Binance futures contract metadata",
                provider=self.name,
                operation="parse futures exchange metadata",
            )

        try:
            filters_raw = value["filters"]
            if not isinstance(filters_raw, list):
                raise TypeError("filters must be a list")

            filters = {
                item["filterType"]: item
                for item in filters_raw
                if isinstance(item, dict) and "filterType" in item
            }

            price_filter = filters["PRICE_FILTER"]
            lot_filter = filters["LOT_SIZE"]
            notional_filter = filters.get("MIN_NOTIONAL") or filters["NOTIONAL"]

            base_asset = self._required_identifier(value["baseAsset"], "baseAsset")
            quote_asset = self._required_identifier(value["quoteAsset"], "quoteAsset")
            exchange_symbol = self._required_identifier(value["symbol"], "symbol")

            notional_value = notional_filter.get(
                "notional",
                notional_filter.get("minNotional"),
            )
            if notional_value is None:
                raise KeyError("notional")

            return FuturesContractMetadata(
                symbol=f"{base_asset}/{quote_asset}",
                exchange_symbol=exchange_symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                status=self._required_identifier(value["status"], "status"),
                contract_type=self._required_identifier(
                    value["contractType"],
                    "contractType",
                ),
                tick_size=float(price_filter["tickSize"]),
                step_size=float(lot_filter["stepSize"]),
                minimum_quantity=float(lot_filter["minQty"]),
                minimum_notional=float(notional_value),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Invalid Binance futures contract metadata fields",
                provider=self.name,
                operation="parse futures exchange metadata",
            ) from exc

    @staticmethod
    def _required_identifier(value: Any, field: str) -> str:
        normalized = str(value).strip().upper()
        if not normalized:
            raise ValueError(f"{field} cannot be empty")
        return normalized
