"""Mode-aware market scanner CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    bootstrap,
    build_analysis_record,
    create_market_data_services,
    format_scan_text,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
    write_analysis_record,
    write_analysis_record_sqlite,
    write_json_report,
)
from apex.application.futures_risk_mode import futures_risk_mode_scope
from apex.data.providers.errors import MarketDataProviderError
from apex.domain import RiskMode


def register_scanner_commands(app: typer.Typer) -> None:
    @app.command("scan")
    def scan(
        symbols_file: Path = typer.Option(Path("config/symbols.yaml"), "--symbols-file"),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        report: Path | None = typer.Option(None, "--report"),
        record: Path | None = typer.Option(None, "--record"),
        record_db: Path | None = typer.Option(None, "--record-db"),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        mode: str = typer.Option("normal", "--mode", help="normal, gainers, or all"),
        risk_mode: RiskMode = typer.Option(RiskMode.STANDARD, "--risk-mode"),
    ) -> None:
        """Analyze and rank the configured futures symbol universe."""

        try:
            symbols = load_symbols(symbols_file)
            context = bootstrap()
            risk_config = load_default_risk_config()
            with futures_risk_mode_scope(risk_mode):
                with create_market_data_services(context.settings) as services:
                    result = scan_symbols(
                        symbols,
                        services.candles,
                        timeframes=context.settings.analysis_timeframes,
                        timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                        timeframe_max_staleness_seconds=getattr(
                            context.settings,
                            "timeframe_max_staleness_seconds",
                            None,
                        ),
                        candle_limit=candle_limit,
                        risk_config=risk_config,
                        scanner_mode=mode,
                        strategy_routing=getattr(context.settings, "strategy_routing", None),
                        gainer_state_thresholds=getattr(
                            context.settings,
                            "gainer_state_thresholds",
                            None,
                        ),
                    )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Scanner market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_scan_result(result)
        payload["risk_mode"] = risk_mode.value
        if report is not None:
            write_json_report(payload, report)
        if record is not None or record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if record_db is not None:
                write_analysis_record_sqlite(record_db, analysis_record)

        if output == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        typer.echo(format_scan_text(result))
