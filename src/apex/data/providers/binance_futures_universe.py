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
        """Fetch and normalize Binance futures exchange metadata."""

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

        contracts = tuple(self._parse_contract(item) for item in symbols)
        return tuple(sorted(contracts, key=lambda item: item.exchange_symbol))

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

            base_asset = str(value["baseAsset"]).upper()
            quote_asset = str(value["quoteAsset"]).upper()
            exchange_symbol = str(value["symbol"]).upper()

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
                status=str(value["status"]).upper(),
                contract_type=str(value["contractType"]).upper(),
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
