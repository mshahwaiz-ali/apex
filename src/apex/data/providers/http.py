"""Shared HTTP behavior for market-data providers."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from apex.data.providers.errors import ProviderRequestError, ProviderResponseError

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_PROVIDER_ERROR_DETAIL_LENGTH = 240


def _provider_error_detail(response: httpx.Response) -> str | None:
    """Return a short, safe provider error detail when one is available."""

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    raw_message = payload.get("msg") or payload.get("message")
    if not isinstance(raw_message, str):
        return None
    message = " ".join(raw_message.split()).strip()
    if not message:
        return None

    raw_code = payload.get("code")
    code = str(raw_code).strip() if isinstance(raw_code, (int, str)) else ""
    detail = f"code {code}: {message}" if code else message
    if len(detail) > MAX_PROVIDER_ERROR_DETAIL_LENGTH:
        return f"{detail[: MAX_PROVIDER_ERROR_DETAIL_LENGTH - 1].rstrip()}…"
    return detail


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Configuration for bounded provider request retries."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds cannot be negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be lower than base_delay_seconds")

    def delay_before_attempt(self, attempt: int) -> float:
        """Return exponential delay before the next attempt."""

        if attempt < 1:
            raise ValueError("attempt must be at least 1")

        delay: float = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)

    def retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        """Return a bounded delay using Retry-After when it is valid."""

        fallback = self.delay_before_attempt(attempt)
        if retry_after is None:
            return fallback

        try:
            header_delay = int(retry_after.strip())
        except (TypeError, ValueError):
            return fallback

        if header_delay < 0:
            return fallback

        return min(max(fallback, float(header_delay)), self.max_delay_seconds)


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    provider: str,
    operation: str,
    retry_policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    **request_kwargs: Any,
) -> Any:
    """Perform an HTTP request with bounded retries and normalized errors."""

    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            response = client.request(method, path, **request_kwargs)
        except httpx.RequestError as exc:
            if attempt < retry_policy.max_attempts:
                sleep(retry_policy.delay_before_attempt(attempt))
                continue

            raise ProviderRequestError(
                f"{provider} request failed during {operation}: {exc}",
                provider=provider,
                operation=operation,
                retryable=True,
            ) from exc

        status_code = response.status_code
        retryable = status_code in RETRYABLE_STATUS_CODES

        if retryable and attempt < retry_policy.max_attempts:
            retry_after = response.headers.get("Retry-After") if status_code == 429 else None
            sleep(retry_policy.retry_delay(attempt, retry_after))
            continue

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _provider_error_detail(response)
            detail_suffix = f" ({detail})" if detail is not None else ""
            raise ProviderRequestError(
                f"{provider} returned HTTP {status_code} during {operation}{detail_suffix}",
                provider=provider,
                operation=operation,
                retryable=retryable,
                status_code=status_code,
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                f"{provider} returned invalid JSON during {operation}",
                provider=provider,
                operation=operation,
            ) from exc

    raise AssertionError("request retry loop exited unexpectedly")
