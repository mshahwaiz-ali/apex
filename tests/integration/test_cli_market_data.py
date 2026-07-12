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


def test_optimize_evaluate_command_writes_report(monkeypatch, tmp_path) -> None:
    report = tmp_path / "backtest.json"
    report.write_text(
        '{"metrics":{"total_trades":1,"win_rate":1.0,"expectancy":2.0,'
        '"profit_factor":2.0,"maximum_drawdown":0.0,"net_profit":2.0}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(cli.app, ["optimize", "evaluate", "--input", str(report)])

    assert result.exit_code == 0
    assert "OPTIMIZE_EVALUATE | decision=accepted" in result.output
    assert (tmp_path / "optimization" / "latest-evaluate.json").exists()


def test_optimize_compare_command_emits_json(monkeypatch, tmp_path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        '{"metrics":{"total_trades":2,"win_rate":0.5,"expectancy":1.0,'
        '"profit_factor":1.0,"maximum_drawdown":1.0,"net_profit":2.0}}',
        encoding="utf-8",
    )
    candidate.write_text(
        '{"metrics":{"total_trades":2,"win_rate":0.5,"expectancy":2.0,'
        '"profit_factor":1.2,"maximum_drawdown":1.0,"net_profit":4.0}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(
        cli.app,
        [
            "optimize",
            "compare",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"decision": "accepted"' in result.output


def test_intelligence_summary_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(
                advanced_intelligence_enabled=False,
                intelligence_funding_enabled=False,
                intelligence_open_interest_enabled=False,
                intelligence_correlation_enabled=False,
            )
        ),
    )

    result = runner.invoke(cli.app, ["intelligence", "summary", "--output", "json"])

    assert result.exit_code == 0
    assert '"enabled": false' in result.output


def test_execute_status_reports_testnet_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(cli.app, ["execute", "status"])

    assert result.exit_code == 0
    assert "EXECUTE_STATUS | mode=testnet_only" in result.output


def test_execute_kill_switch_enable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(cli.app, ["execute", "kill-switch", "enable"])

    assert result.exit_code == 0
    assert "EXECUTION_KILL_SWITCH | enabled" in result.output
    assert (tmp_path / "execution" / "kill_switch.txt").read_text(encoding="utf-8") == "enabled\n"
