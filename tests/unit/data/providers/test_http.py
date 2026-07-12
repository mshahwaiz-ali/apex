from collections.abc import Callable

import httpx
import pytest

from apex.data.providers.errors import ProviderRequestError, ProviderResponseError
from apex.data.providers.http import RetryPolicy, request_json


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://example.test",
    )


def test_retries_retryable_status_until_success() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            return httpx.Response(503, request=request)

        return httpx.Response(200, json={"ok": True}, request=request)

    with make_client(handler) as client:
        payload = request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=0.1,
                max_delay_seconds=1.0,
            ),
            sleep=delays.append,
        )

    assert payload == {"ok": True}
    assert attempts == 3
    assert delays == [0.1, 0.2]


def test_uses_valid_retry_after_for_http_429() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "1"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    with make_client(handler) as client:
        payload = request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0.1,
                max_delay_seconds=2.0,
            ),
            sleep=delays.append,
        )

    assert payload == {"ok": True}
    assert attempts == 2
    assert delays == [1.0]


def test_malformed_retry_after_falls_back_to_exponential_delay() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "not-a-delay"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    with make_client(handler) as client:
        request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0.25,
                max_delay_seconds=2.0,
            ),
            sleep=delays.append,
        )

    assert attempts == 2
    assert delays == [0.25]


def test_oversized_retry_after_is_bounded_by_max_delay() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "999999"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    with make_client(handler) as client:
        request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0.25,
                max_delay_seconds=1.5,
            ),
            sleep=delays.append,
        )

    assert attempts == 2
    assert delays == [1.5]


def test_does_not_retry_non_retryable_client_error() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, request=request)

    with (
        make_client(handler) as client,
        pytest.raises(ProviderRequestError) as exc_info,
    ):
        request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(max_attempts=3),
            sleep=delays.append,
        )

    error = exc_info.value
    assert attempts == 1
    assert delays == []
    assert error.provider == "test"
    assert error.operation == "fetch market data"
    assert error.status_code == 400
    assert error.retryable is False


def test_normalizes_exhausted_retryable_status() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "1"},
            request=request,
        )

    with (
        make_client(handler) as client,
        pytest.raises(ProviderRequestError) as exc_info,
    ):
        request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=2,
            ),
            sleep=delays.append,
        )

    error = exc_info.value
    assert attempts == 2
    assert delays == [1.0]
    assert error.status_code == 429
    assert error.retryable is True


def test_retries_transport_error_until_success() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            raise httpx.ConnectError("connection failed", request=request)

        return httpx.Response(200, json={"ok": True}, request=request)

    with make_client(handler) as client:
        payload = request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(
                max_attempts=2,
                base_delay_seconds=0,
            ),
            sleep=lambda _: None,
        )

    assert payload == {"ok": True}
    assert attempts == 2


def test_normalizes_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            request=request,
        )

    with (
        make_client(handler) as client,
        pytest.raises(
            ProviderResponseError,
            match="returned invalid JSON",
        ) as exc_info,
    ):
        request_json(
            client,
            "GET",
            "/market",
            provider="test",
            operation="fetch market data",
            retry_policy=RetryPolicy(max_attempts=1),
        )

    assert exc_info.value.provider == "test"
    assert exc_info.value.operation == "fetch market data"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"base_delay_seconds": -1}, "base_delay_seconds"),
        ({"max_delay_seconds": -1}, "max_delay_seconds"),
        (
            {"base_delay_seconds": 2, "max_delay_seconds": 1},
            "max_delay_seconds must not be lower",
        ),
    ],
)
def test_rejects_invalid_retry_policy(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**kwargs)
