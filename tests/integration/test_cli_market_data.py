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
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(analysis_timeframes=("5m",))),
    )
    monkeypatch.setattr(
        legacy_cli,
        "create_market_data_services",
        lambda settings: FakeServices(candles=object(), ticker=object()),
    )
    monkeypatch.setattr(legacy_cli, "load_default_risk_config", lambda: object())
    monkeypatch.setattr(legacy_cli, "scan_symbols", lambda *args, **kwargs: fake_scan)
    monkeypatch.setattr(
        legacy_cli,
        "serialize_scan_result",
        lambda result: {"best_overall": None, "failures": {}},
    )
    monkeypatch.setattr(legacy_cli, "format_scan_text", lambda result: "scan text")

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
                gainer_state_thresholds=None,
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
                gainer_state_thresholds=None,
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


def test_optimize_evaluate_command_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = tmp_path / "backtest.json"
    report.write_text(
        '{"metrics":{"total_trades":1,"win_rate":1.0,"expectancy":2.0,'
        '"profit_factor":2.0,"maximum_drawdown":0.0,"net_profit":2.0}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(app, ["optimize", "evaluate", "--input", str(report)])

    assert result.exit_code == 0
    assert "OPTIMIZE_EVALUATE | decision=accepted" in result.output
    assert (tmp_path / "optimization" / "latest-evaluate.json").exists()


def test_optimize_evaluate_command_accepts_campaign_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    report = tmp_path / "campaign.json"
    report.write_text(
        json.dumps(
            {
                "best_variant_id": "candidate",
                "variants": [
                    {
                        "symbol": "BTC/USDT",
                        "variant": {"identifier": "candidate"},
                        "metrics": {
                            "total_trades": 2,
                            "win_rate": 0.5,
                            "gross_profit": 10.0,
                            "gross_loss": -2.0,
                            "net_profit": 8.0,
                            "maximum_drawdown": 1.0,
                        },
                    },
                    {
                        "symbol": "ETH/USDT",
                        "variant": {"identifier": "candidate"},
                        "metrics": {
                            "total_trades": 3,
                            "win_rate": 2 / 3,
                            "gross_profit": 12.0,
                            "gross_loss": -3.0,
                            "net_profit": 9.0,
                            "maximum_drawdown": 2.0,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(
        app,
        ["optimize", "evaluate", "--input", str(report), "--output", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["candidate"]["total_trades"] == 5
    assert payload["candidate"]["net_profit"] == 17.0
    assert (tmp_path / "optimization" / "latest-evaluate.json").exists()


def test_optimize_compare_command_emits_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(
        app,
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


def test_optimize_calibrate_command_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def write_report(
        path: Path,
        *,
        expectancy: float,
        net_profit: float,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "total_trades": 2,
                        "win_rate": 0.5,
                        "expectancy": expectancy,
                        "profit_factor": 1.2,
                        "maximum_drawdown": 1.0,
                        "net_profit": net_profit,
                    }
                }
            ),
            encoding="utf-8",
        )

    train_baseline = tmp_path / "train-baseline.json"
    train_candidate = tmp_path / "train-candidate.json"
    validation_baseline = tmp_path / "validation-baseline.json"
    validation_candidate = tmp_path / "validation-candidate.json"
    final_baseline = tmp_path / "final-baseline.json"
    final_candidate = tmp_path / "final-candidate.json"
    write_report(train_baseline, expectancy=1.0, net_profit=2.0)
    write_report(train_candidate, expectancy=2.0, net_profit=4.0)
    write_report(validation_baseline, expectancy=1.0, net_profit=2.0)
    write_report(validation_candidate, expectancy=2.0, net_profit=4.0)
    write_report(final_baseline, expectancy=1.0, net_profit=2.0)
    write_report(final_candidate, expectancy=10.0, net_profit=20.0)
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(
        app,
        [
            "optimize",
            "calibrate",
            "--train-baseline",
            str(train_baseline),
            "--train-candidate",
            str(train_candidate),
            "--validation-baseline",
            str(validation_baseline),
            "--validation-candidate",
            str(validation_candidate),
            "--final-test-baseline",
            str(final_baseline),
            "--final-test-candidate",
            str(final_candidate),
            "--train-start",
            "2026-01-01",
            "--train-end",
            "2026-02-01",
            "--validation-start",
            "2026-02-02",
            "--validation-end",
            "2026-03-01",
            "--out-of-sample-start",
            "2026-03-02",
            "--out-of-sample-end",
            "2026-04-01",
            "--parameter-name",
            "minimum_score",
            "--parameter-value",
            "65",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"decision": "accepted"' in result.output
    assert '"used_for_selection": false' in result.output
    assert (tmp_path / "optimization" / "latest-calibration.json").exists()


def test_intelligence_summary_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        legacy_cli,
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

    result = runner.invoke(app, ["intelligence", "summary", "--output", "json"])

    assert result.exit_code == 0
    assert '"enabled": false' in result.output


def test_execute_status_reports_local_testnet_simulation_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(app, ["execute", "status"])

    assert result.exit_code == 0
    assert "EXECUTE_STATUS | mode=local_testnet_simulation_only" in result.output


def test_execute_reconcile_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )
    audit = tmp_path / "execution" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    client_order_id = "apex-local_testnet_simulation-BTCUSDT-abc123"
    audit.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "timestamp": "2026-07-13T00:00:00+00:00",
                "environment": "local_testnet_simulation",
                "testnet_only": True,
                "live_fallback": False,
                "adapter_name": "local-simulation",
                "state": "local_testnet_simulated",
                "reasons": [],
                "order": {
                    "order_id": "local-sim-abc123",
                    "client_order_id": client_order_id,
                    "idempotency_key": "exec-abc",
                    "state": "local_testnet_simulated",
                    "created_at": "2026-07-13T00:00:00+00:00",
                    "environment": "local_testnet_simulation",
                    "intent": {
                        "symbol": "BTC/USDT",
                        "direction": "LONG",
                        "quantity": 1.0,
                        "entry_price": 100.0,
                        "stop_price": 98.0,
                        "target_price": 104.0,
                        "notional_value": 100.0,
                        "duplicate_key": "abc123",
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    snapshots = tmp_path / "snapshots.json"
    snapshots.write_text(
        json.dumps(
            [
                {
                    "client_order_id": client_order_id,
                    "order_id": "local-sim-abc123",
                    "state": "local_testnet_simulated",
                    "filled_quantity": 1.0,
                    "average_fill_price": 100.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = tmp_path / "reconcile.json"

    result = runner.invoke(
        app,
        [
            "execute",
            "reconcile",
            "--snapshots",
            str(snapshots),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0
    assert "EXECUTE_RECONCILE | matched=1" in result.output
    assert json.loads(report.read_text(encoding="utf-8"))["matched_count"] == 1


def test_execute_readiness_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )
    audit = tmp_path / "execution" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text("", encoding="utf-8")
    reconciliation = tmp_path / "reconciliation.json"
    reconciliation.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-13T00:00:00+00:00",
                "audit_path": str(audit),
                "adapter_name": "snapshot-file",
                "total_audit_events": 0,
                "matched_count": 0,
                "missing_count": 0,
                "mismatched_count": 0,
                "rejected_local_count": 0,
                "records": [],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "readiness.json"

    result = runner.invoke(
        app,
        [
            "execute",
            "readiness",
            "--reconciliation",
            str(reconciliation),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0
    assert "EXECUTE_READINESS | local_simulation_ready=true" in result.output
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["exchange_ready"] is False
    assert payload["blockers"]


def test_execute_testnet_reports_local_simulation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )
    monkeypatch.setattr(
        legacy_cli,
        "_analysis_for_execution",
        lambda symbol, candle_limit: SimpleNamespace(
            assessment=SimpleNamespace(setup=object(), reasons=())
        ),
    )
    monkeypatch.setattr(
        legacy_cli,
        "intent_from_setup",
        lambda setup: ExecutionIntent(
            symbol="BTC/USDT",
            direction=TradeDirection.LONG,
            quantity=1.0,
            entry_price=100.0,
            stop_price=98.0,
            target_price=104.0,
            notional_value=100.0,
            duplicate_key="abc123",
        ),
    )

    result = runner.invoke(app, ["execute", "testnet", "BTC/USDT", "--confirm"])

    assert result.exit_code == 0
    assert "EXECUTE_LOCAL_TESTNET_SIMULATION" in result.output
    assert "local_testnet_simulated" in result.output


def test_execute_kill_switch_enable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        legacy_cli,
        "bootstrap",
        lambda: SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)),
    )

    result = runner.invoke(app, ["execute", "kill-switch", "enable"])

    assert result.exit_code == 0
    assert "EXECUTION_KILL_SWITCH | enabled" in result.output
    assert (tmp_path / "execution" / "kill_switch.txt").read_text(encoding="utf-8") == "enabled\n"
