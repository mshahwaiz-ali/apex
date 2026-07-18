"""Persistent TTL cache for slow-changing futures contract metadata."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apex.data.providers.base import FuturesUniverseProvider
from apex.domain.futures_market import FuturesContractMetadata


class CachedFuturesUniverseProvider:
    """Cache futures exchange metadata while preserving live-provider ownership."""

    def __init__(
        self,
        provider: FuturesUniverseProvider,
        cache_path: Path,
        *,
        time_to_live: timedelta,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if time_to_live <= timedelta(0):
            raise ValueError("futures universe cache TTL must be positive")

        self._provider = provider
        self._cache_path = cache_path
        self._time_to_live = time_to_live
        self._now = now or (lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return self._provider.name

    def close(self) -> None:
        """Close the wrapped provider when it owns runtime resources."""

        close = getattr(self._provider, "close", None)
        if callable(close):
            close()

    def fetch_futures_contracts(self) -> tuple[FuturesContractMetadata, ...]:
        """Return fresh cached metadata or refresh it from the live provider."""

        cached = self._load()
        if cached is not None:
            return cached

        contracts = self._provider.fetch_futures_contracts()
        with contextlib.suppress(OSError):
            self._save(contracts)
        return contracts

    def _load(self) -> tuple[FuturesContractMetadata, ...] | None:
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None

            captured_at = _parse_datetime(payload.get("captured_at"))
            if self._now().astimezone(UTC) - captured_at > self._time_to_live:
                return None

            raw_contracts = payload.get("contracts")
            if not isinstance(raw_contracts, list):
                return None

            contracts = tuple(_parse_contract(item) for item in raw_contracts)
            return tuple(
                sorted(
                    contracts,
                    key=lambda contract: contract.exchange_symbol,
                )
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _save(
        self,
        contracts: tuple[FuturesContractMetadata, ...],
    ) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "captured_at": self._now().astimezone(UTC).isoformat(),
            "provider": self.name,
            "contracts": [
                asdict(contract)
                for contract in sorted(
                    contracts,
                    key=lambda item: item.exchange_symbol,
                )
            ],
        }
        temporary = self._cache_path.with_suffix(f"{self._cache_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._cache_path)


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("cache timestamp must be a string")

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("cache timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _parse_contract(value: Any) -> FuturesContractMetadata:
    if not isinstance(value, dict):
        raise TypeError("cached contract must be an object")

    return FuturesContractMetadata(
        symbol=str(value["symbol"]),
        exchange_symbol=str(value["exchange_symbol"]),
        base_asset=str(value["base_asset"]),
        quote_asset=str(value["quote_asset"]),
        status=str(value["status"]),
        contract_type=str(value["contract_type"]),
        tick_size=float(value["tick_size"]),
        step_size=float(value["step_size"]),
        minimum_quantity=float(value["minimum_quantity"]),
        minimum_notional=float(value["minimum_notional"]),
    )
