"""Mode-aware market scanner CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    bootstrap,
    build_analysis_record,
    create_market_data_services,
    load_default_risk_config,
    scan_symbols,
    select_futures_scan_symbols,
    serialize_futures_screening,
    serialize_scan_result,
    write_analysis_record,
    write_analysis_record_sqlite,
    write_json_report,
)
from apex.application.futures_risk_mode import futures_risk_mode_scope
from apex.data.providers.errors import MarketDataProviderError
from apex.domain import RiskMode
from apex.presentation import normalize_output_mode
from apex.presentation.scanner import render_futures_scan


def register_scanner_commands(app: typer.Typer) -> None:
    @app.command("scan")
    def scan(
        symbols_file: Path | None = typer.Option(
            None,
            "--symbols-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Optional static symbol override. Defaults to live Binance futures discovery.",
        ),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="text, json, verbose, or debug",
        ),
        report: Path | None = typer.Option(None, "--report"),
        record: Path | None = typer.Option(None, "--record"),
        record_db: Path | None = typer.Option(None, "--record-db"),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=999),
        risk_mode: RiskMode = typer.Option(RiskMode.STANDARD, "--risk-mode"),
    ) -> None:
        """Discover, analyze, and rank the active futures symbol universe."""

        try:
            output_mode = normalize_output_mode(output)
            context = bootstrap()
            risk_config = load_default_risk_config()
            with (
                futures_risk_mode_scope(risk_mode),
                create_market_data_services(context.settings) as services,
            ):
                selection = select_futures_scan_symbols(
                    services.futures_universe,
                    services.futures_screener,
                    config=(
                        context.settings
                        .futures_screener
                        .to_domain()
                    ),
                    symbols_file=symbols_file,
                )
                result = scan_symbols(
                    selection.symbols,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings,
                        "timeframe_max_staleness_seconds",
                        None,
                    ),
                    candle_limit=candle_limit + 1,
                    risk_config=risk_config,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Scanner market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_scan_result(result)
        payload["risk_mode"] = risk_mode.value
        if selection.screening is not None:
            payload["screening"] = serialize_futures_screening(
                selection.screening
            )
        if report is not None:
            write_json_report(payload, report)
        if record is not None or record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if record_db is not None:
                write_analysis_record_sqlite(record_db, analysis_record)

        if output_mode.value == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        typer.echo(render_futures_scan(payload, mode=output_mode))
