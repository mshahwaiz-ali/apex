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


def test_analyze_command_emits_text_result(monkeypatch) -> None:
    fake_analysis = object()
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(analysis_timeframes=("5m",))),
    )
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(cli, "analyze_symbol", lambda *args, **kwargs: fake_analysis)
    monkeypatch.setattr(cli, "serialize_symbol_analysis", lambda analysis: {"decision": "NO_TRADE"})
    monkeypatch.setattr(cli, "format_symbol_text", lambda analysis: "BTC/USDT: NO_TRADE")

    result = runner.invoke(cli.app, ["analyze", "BTC/USDT"])

    assert result.exit_code == 0
    assert "BTC/USDT: NO_TRADE" in result.output


def test_scan_command_emits_json_result(monkeypatch, tmp_path) -> None:
    symbols = tmp_path / "symbols.yaml"
    symbols.write_text("symbols:\n  - BTC/USDT\n", encoding="utf-8")
    fake_scan = object()
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(analysis_timeframes=("5m",))),
    )
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(cli, "scan_symbols", lambda *args, **kwargs: fake_scan)
    monkeypatch.setattr(
        cli,
        "serialize_scan_result",
        lambda result: {"best_overall": None, "failures": {}},
    )
    monkeypatch.setattr(cli, "format_scan_text", lambda result: "scan text")

    result = runner.invoke(cli.app, ["scan", "--symbols-file", str(symbols), "--output", "json"])

    assert result.exit_code == 0
    assert '"best_overall": null' in result.output


def test_backtest_command_returns_no_backtest_without_setup(monkeypatch) -> None:
    analysis = SimpleNamespace(
        assessment=SimpleNamespace(
            setup=None,
            reasons=("Phase 5 selected no trade candidate",),
        )
    )
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(analysis_timeframes=("5m",))),
    )
    monkeypatch.setattr(
        cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(cli, "analyze_symbol", lambda *args, **kwargs: analysis)

    result = runner.invoke(cli.app, ["backtest", "BTC/USDT"])

    assert result.exit_code == 0
    assert "BTC/USDT: NO_BACKTEST" in result.output


def test_paper_report_command_emits_metrics(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(cli.app, ["paper", "report"])

    assert result.exit_code == 0
    assert "PAPER_REPORT | total=0" in result.output
