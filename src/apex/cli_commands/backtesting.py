"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer

from apex.application import (
    ChronologicalBacktestRequest,
    bootstrap,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    run_chronological_pipeline_backtest,
)
from apex.application.backtest_comparison import compare_backtest_reports
from apex.application.backtest_report_io import (
    dumps_report,
    make_run_id,
    to_json_value,
    write_backtest_report,
)
from apex.application.chronological_metadata import build_chronological_metadata
from apex.application.historical_dataset import load_historical_candles
from apex.cli import backtest as legacy_simulate_current_setup
from apex.data.providers.errors import MarketDataProviderError


def register_backtesting_commands(app: typer.Typer) -> None:
    @app.command("simulate-current-setup")
    def simulate_current_setup(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(240, "--candles", min=80, max=1000),
        replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
    ) -> None:
        """Simulate one currently approved setup using a canonical market symbol."""
        canonical = normalize_market_symbol(symbol)
        legacy_simulate_current_setup(
            symbol=canonical,
            output=output,
            candle_limit=candle_limit,
            replay_timeframe=replay_timeframe,
        )

    @app.command("chronological-backtest")
    def chronological_backtest(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
        history_limit: int = typer.Option(500, "--history-candles", min=80, max=1000),
        candle_limit: int = typer.Option(200, "--analysis-candles", min=40, max=500),
        decision_interval: int = typer.Option(1, "--decision-interval", min=1),
        candidate_cooldown: int = typer.Option(3, "--candidate-cooldown", min=0),
        dataset: Path | None = typer.Option(
            None,
            "--dataset",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Optional local .json or .csv historical candle dataset.",
        ),
        report_output: Path | None = typer.Option(
            None,
            "--report-output",
            dir_okay=False,
            help="Optional path for the complete JSON backtest report.",
        ),
        force: bool = typer.Option(False, "--force", help="Allow replacing report output."),
    ) -> None:
        canonical = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            risk_config = load_default_risk_config()
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            required_timeframes = tuple(dict.fromkeys((*analysis_timeframes, replay_timeframe)))
            if dataset is None:
                with create_market_data_services(context.settings) as services:
                    candles = {
                        timeframe: tuple(
                            services.candles.fetch_candles(
                                canonical,
                                timeframe,
                                limit=history_limit,
                            )
                        )
                        for timeframe in required_timeframes
                    }
                dataset_source = "live-provider"
            else:
                candles = load_historical_candles(
                    dataset,
                    expected_symbol=canonical,
                    required_timeframes=required_timeframes,
                )
                dataset_source = str(dataset)

            request = ChronologicalBacktestRequest(
                symbol=canonical,
                candles_by_timeframe=candles,
                analysis_timeframes=analysis_timeframes,
                replay_timeframe=replay_timeframe,
                candle_limit=candle_limit,
                decision_interval_candles=decision_interval,
                candidate_cooldown_candles=candidate_cooldown,
                risk_config=risk_config,
            )
            result = run_chronological_pipeline_backtest(request)
            metadata = build_chronological_metadata(
                symbol=canonical,
                candles_by_timeframe=candles,
                analysis_timeframes=request.analysis_timeframes,
                replay_timeframe=replay_timeframe,
                candle_limit=candle_limit,
                decision_interval_candles=decision_interval,
                candidate_cooldown_candles=candidate_cooldown,
                risk_config=risk_config,
                backtest_config=request.backtest_config,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Chronological backtest market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        metadata_payload = to_json_value(metadata)
        metadata_payload["run_id"] = make_run_id(
            symbol=canonical,
            replay_timeframe=replay_timeframe,
            dataset_hash=metadata.dataset_hash,
            config_hash=metadata.config_hash,
        )
        payload = {
            "symbol": canonical,
            "dataset_source": dataset_source,
            "metadata": metadata_payload,
            "decision_count": result.decision_count,
            "approved_count": result.approved_count,
            "skipped_count": result.skipped_count,
            "cooldown_skipped_count": result.cooldown_skipped_count,
            "overlap_skipped_count": result.overlap_skipped_count,
            "failure_count": result.failure_count,
            "failures": dict(result.failures),
            "metrics": asdict(result.report),
            "trades": [asdict(trade) for trade in result.trades],
        }
        if report_output is not None:
            try:
                write_backtest_report(report_output, payload, force=force)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
        typer.echo(dumps_report(payload), nl=False)

    @app.command("compare-backtests")
    def compare_backtests(
        left: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
        right: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    ) -> None:
        """Compare identities and aggregate metrics from two saved reports."""
        try:
            comparison = compare_backtest_reports(left, right)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(dumps_report(comparison), nl=False)
