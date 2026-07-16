"""Futures exchange-contract metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FuturesContractMetadata:
    """Normalized metadata for one exchange futures contract."""

    symbol: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    status: str
    contract_type: str
    tick_size: float
    step_size: float
    minimum_quantity: float
    minimum_notional: float

    def __post_init__(self) -> None:
        required_text = {
            "symbol": self.symbol,
            "exchange_symbol": self.exchange_symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "status": self.status,
            "contract_type": self.contract_type,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty")

        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.step_size <= 0:
            raise ValueError("step_size must be positive")
        if self.minimum_quantity < 0:
            raise ValueError("minimum_quantity cannot be negative")
        if self.minimum_notional < 0:
            raise ValueError("minimum_notional cannot be negative")
