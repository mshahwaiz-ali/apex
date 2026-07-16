import json
from contextlib import AbstractContextManager
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest
from typer.testing import CliRunner

from apex.application import (
    BacktestCampaignRequest,
    MultiSymbolBacktestCampaignRequest,
)
import apex.cli as legacy_cli
import apex.cli_commands.analysis as analysis_cli
import apex.cli_commands.backtesting as backtesting_cli
import apex.cli_commands.paper_trading as paper_trading_cli
import apex.cli_commands.scanner as scanner_cli
import apex.cli_commands.system as system_cli
from apex.cli_app import app
from apex.data.providers.errors import ProviderRequestError
from apex.execution.contracts import ExecutionIntent
from apex.strategies import TradeDirection

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
        self.futures_universe = object()
        self.futures_screener = object()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_fetch_reports_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        system_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=FakeCandleProvider(), ticker=object()),
    )

    result = runner.invoke(app, ["fetch", "BTC/USDT"])

    assert result.exit_code == 1
    assert "Market-data request failed: temporary provider failure" in result.output


def test_ticker_reports_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        system_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=FakeTickerProvider()),
    )

    result = runner.invoke(app, ["ticker", "BTC/USDT"])

    assert result.exit_code == 1
    assert "Ticker request failed: ticker unavailable" in result.output


def test_ticker_does_not_mask_programming_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_cli, "bootstrap", lambda: SimpleNamespace(settings=object()))
    monkeypatch.setattr(
        system_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=BuggyTickerProvider()),
    )

    result = runner.invoke(app, ["ticker", "BTC/USDT"])

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert "Ticker request failed" not in result.output


def test_analyze_command_emits_text_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_analysis = object()
    monkeypatch.setattr(
        analysis_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(analysis_timeframes=("5m",))),
    )
    monkeypatch.setattr(
        analysis_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(analysis_cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(
        analysis_cli,
        "analyze_selected_symbol",
        lambda *args, **kwargs: fake_analysis,
    )
    monkeypatch.setattr(
        analysis_cli,
        "serialize_symbol_analysis",
        lambda analysis: {"decision": "NO_TRADE"},
    )
    result = runner.invoke(app, ["analyze", "BTC/USDT", "--output", "json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["decision"] == "NO_TRADE"


def test_scan_command_emits_json_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    symbols = tmp_path / "symbols.yaml"
    symbols.write_text("symbols:\n  - BTC/USDT\n", encoding="utf-8")
    fake_scan = object()
    settings = SimpleNamespace(
        analysis_timeframes=("5m",),
        futures_screener=SimpleNamespace(
            to_domain=lambda: object(),
            quote_asset="USDT",
            blacklist=(),
            allowlist=None,
        ),
    )

    monkeypatch.setattr(
        scanner_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=settings),
    )
    monkeypatch.setattr(
        scanner_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(scanner_cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(
        scanner_cli,
        "select_futures_scan_symbols",
        lambda *args, **kwargs: SimpleNamespace(
            symbols=("BTC/USDT",),
            screening=None,
        ),
    )
    monkeypatch.setattr(scanner_cli, "scan_symbols", lambda *args, **kwargs: fake_scan)
    monkeypatch.setattr(
        scanner_cli,
        "serialize_scan_result",
        lambda result: {"best_overall": None, "failures": {}},
    )

    result = runner.invoke(app, ["scan", "--symbols-file", str(symbols), "--output", "json"])

    assert result.exit_code == 0
    assert '"best_overall": null' in result.output


def test_analysis_and_scan_help_expose_record_option() -> None:
    analyze = runner.invoke(app, ["analyze", "--help"])
    scan = runner.invoke(app, ["scan", "--help"])
    chronological = runner.invoke(app, ["chronological-backtest", "--help"])
    campaign = runner.invoke(app, ["chronological-backtest-campaign", "--help"])

    assert analyze.exit_code == 0
    assert scan.exit_code == 0
    assert chronological.exit_code == 0
    assert campaign.exit_code == 0
    assert "--record" in analyze.output
    assert "--record" in scan.output
    assert "--record-db" in analyze.output
    assert "--record-db" in scan.output
    assert "--record-db" in chronological.output
    assert "--variants" in campaign.output
    assert "--record-db" in campaign.output


def test_simulate_current_setup_help_exposes_current_options() -> None:
    result = runner.invoke(app, ["simulate-current-setup", "--help"])

    assert result.exit_code == 0
    assert "--output" in result.output
    assert "--candles" in result.output
    assert "--replay-timeframe" in result.output

def test_chronological_campaign_command_runs_application_layer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        backtesting_cli,
        "bootstrap",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(
                analysis_timeframes=("5m",),
                strategy_routing=None,
            )
        ),
    )
    monkeypatch.setattr(backtesting_cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(
        backtesting_cli,
        "load_historical_candles",
        lambda *args, **kwargs: {"5m": ()},
    )
    monkeypatch.setattr(
        backtesting_cli,
        "split_campaign_candles_by_symbol",
        lambda candles, symbols: {"BTC/USDT": {"5m": ()}},
    )

    def fake_run_campaign(request: BacktestCampaignRequest) -> object:
        captured["symbol"] = request.symbol
        captured["dataset_source"] = request.dataset_source
        captured["variant_ids"] = tuple(variant.identifier for variant in request.variants)
        return object()

    monkeypatch.setattr(backtesting_cli, "run_backtest_campaign", fake_run_campaign)
    monkeypatch.setattr(
        backtesting_cli,
        "campaign_result_to_payload",
        lambda result: {
            "campaign_id": "btc-usdt-campaign-fixture",
            "symbol": "BTC/USDT",
            "variant_count": 2,
            "rankings": [],
            "variants": [],
        },
    )

    result = runner.invoke(
        app,
        [
            "chronological-backtest-campaign",
            "BTCUSDT",
            "--dataset",
            str(dataset),
            "--variants",
            "base:5m:200:1:3,candidate:5m:120:2:1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"campaign_id": "btc-usdt-campaign-fixture"' in result.output
    assert captured["symbol"] == "BTC/USDT"
    assert captured["dataset_source"] == str(dataset)
    assert captured["variant_ids"] == ("base", "candidate")


def test_chronological_campaign_command_supports_multi_symbol_dataset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        backtesting_cli,
        "bootstrap",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(
                analysis_timeframes=("5m",),
                strategy_routing=None,
            )
        ),
    )
    monkeypatch.setattr(backtesting_cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(
        backtesting_cli,
        "load_historical_candles",
        lambda *args, **kwargs: {"5m": ()},
    )
    monkeypatch.setattr(
        backtesting_cli,
        "split_campaign_candles_by_symbol",
        lambda candles, symbols: {
            "BTC/USDT": {"5m": ()},
            "ETH/USDT": {"5m": ()},
        },
    )

    def fake_run_multi_campaign(
        request: MultiSymbolBacktestCampaignRequest,
    ) -> object:
        captured["symbols"] = request.symbols
        captured["variant_ids"] = tuple(variant.identifier for variant in request.variants)
        return object()

    monkeypatch.setattr(
        backtesting_cli,
        "run_multi_symbol_backtest_campaign",
        fake_run_multi_campaign,
    )
    monkeypatch.setattr(
        backtesting_cli,
        "campaign_result_to_payload",
        lambda result: {
            "campaign_id": "multi-campaign-fixture",
            "symbol": "MULTI",
            "symbol_count": 2,
            "variant_count": 2,
            "rankings": [],
            "variants": [],
        },
    )

    result = runner.invoke(
        app,
        [
            "chronological-backtest-campaign",
            "BTCUSDT,ETHUSDT",
            "--dataset",
            str(dataset),
            "--variants",
            "base:5m:200:1:3,candidate:5m:120:2:1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"symbol": "MULTI"' in result.output
    assert captured["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert captured["variant_ids"] == ("base", "candidate")


def test_paper_report_command_emits_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        paper_trading_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(app, ["paper", "report"])

    assert result.exit_code == 0
    assert "Paper Trading Report" in result.output
    assert "Total trades" in result.output


def test_paper_replay_report_command_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        paper_trading_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )
    report = tmp_path / "paper-replay.json"

    result = runner.invoke(app, ["paper", "replay-report", "--report", str(report)])

    assert result.exit_code == 0
    assert "Paper Trading Replay Report" in result.output
    assert "Total trades" in result.output
    assert report.exists()
