"""Normalized market-data provider errors."""

from __future__ import annotations


class MarketDataProviderError(RuntimeError):
    """Base error raised by market-data provider integrations."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        operation: str,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation


class ProviderRequestError(MarketDataProviderError):
    """Raised when a provider request cannot complete successfully."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        operation: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            operation=operation,
        )
        self.retryable = retryable
        self.status_code = status_code


class ProviderResponseError(MarketDataProviderError):
    """Raised when a provider returns malformed or unexpected data."""
