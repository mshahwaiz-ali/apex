"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    build_analysis_record,
    configuration_metadata,
    create_market_data_services,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.enriched_public_output import serialize_symbol_analysis
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import normalize_cli_output_mode
from apex.presentation.methodology_semantics_output import render_discovery_analysis


def register_analysis_commands(app: typer.Typer) -> None:
    """Register focused manual futures analysis."""

    @app.command("analyze")
    def analyze(
        symbol: str = typer.Argument(..., help="Any provider-supported futures market symbol."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        record: Path | None = typer.Option(
            None,
            "--record",
            help="Optional append-only JSONL analysis record path.",
        ),
        record_db: Path | None = typer.Option(
            None,
            "--record-db",
            help="Optional SQLite analysis record database path.",
        ),
        config_dir: Path = typer.Option(
            Path("config"),
            "--config-dir",
            exists=True,
            file_okay=False,
            help="Configuration directory containing Apex YAML settings.",
        ),
    ) -> None:
        """Analyze one futures symbol and produce a trade-discovery plan."""

        try:
            output_mode = normalize_cli_output_mode(output)
            context = bootstrap(config_dir)
            with create_market_data_services(context.settings) as services:
                result = analyze_selected_symbol(
                    symbol,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings,
                        "timeframe_max_staleness_seconds",
                        None,
                    ),
                    candle_limit=candle_limit,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    methodology_gate_mode=context.settings.methodology_gate_mode,
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Analysis market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_symbol_analysis(result)
        payload.update(configuration_metadata(context.settings.model_dump(mode="json")))
        if record is not None or record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if record_db is not None:
                write_analysis_record_sqlite(record_db, analysis_record)

        if output_mode.value == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        typer.echo(render_discovery_analysis(payload, mode=output_mode))


__all__ = ["register_analysis_commands"]
