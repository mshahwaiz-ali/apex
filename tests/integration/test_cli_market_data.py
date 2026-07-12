from contextlib import AbstractContextManager
from types import SimpleNamespace
from typing import Self

from typer.testing import CliRunner

import apex.cli as cli
from apex.data.providers.errors import ProviderRequestError

runner = CliRunner()


class FakeCandleProvider:
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[object]:
        raise ProviderRequestError(
            "temporary provider failure",
            provider="fake",
            operation="fetch candles",
            retryable=True,
            status_code=503,
        )


class FakeTickerProvider:
    def fetch_ticker(self, symbol: str) -> object:
        raise ProviderRequestError(
            "ticker unavailable",
            provider="fake",
            operation="fetch ticker",
            retryable=True,
            status_code=503,
        )


class BuggyTickerProvider:
    def fetch_ticker(self, symbol: str) -> object:
        raise RuntimeError("unexpected programming defect")


class FakeServices(AbstractContextManager["FakeServices"]):
    def __init__(self, *, candles: object, ticker: object) -> None:
        self.candles = candles
        self.ticker = ticker

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_fetch_reports_provider_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=FakeCandleProvider(), ticker=object()),
    )

    result = runner.invoke(cli.app, ["fetch", "BTC/USDT"])

    assert result.exit_code == 1
    assert "Market-data request failed: temporary provider failure" in result.output


def test_ticker_reports_provider_failure(monkeypatch) -> None:
    monkeypatch.setattr(cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=FakeTickerProvider()),
    )

    result = runner.invoke(cli.app, ["ticker", "BTC/USDT"])

    assert result.exit_code == 1
    assert "Ticker request failed: ticker unavailable" in result.output


def test_ticker_does_not_mask_programming_error(monkeypatch) -> None:
    monkeypatch.setattr(cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=BuggyTickerProvider()),
    )

    result = runner.invoke(cli.app, ["ticker", "BTC/USDT"])

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert "Ticker request failed" not in result.output
