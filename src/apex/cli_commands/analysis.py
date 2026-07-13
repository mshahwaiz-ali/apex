"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    create_market_data_services,
    format_symbol_text,
    load_default_risk_config,
    serialize_symbol_analysis,
)
from apex.data.providers.errors import MarketDataProviderError


def register_analysis_commands(app: typer.Typer) -> None:
    @app.command("analyze")
    def analyze(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
    ) -> None:
        try:
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                result = analyze_selected_symbol(
                    symbol,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings, "timeframe_max_staleness_seconds", None
                    ),
                    candle_limit=candle_limit,
                    risk_config=load_default_risk_config(),
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Analysis market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_symbol_analysis(result)
        if output == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
        else:
            typer.echo(format_symbol_text(result))
