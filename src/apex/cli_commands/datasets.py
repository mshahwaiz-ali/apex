"""Historical dataset export CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apex.application import bootstrap, create_market_data_services, normalize_market_symbol
from apex.application.historical_dataset_export import build_dataset_payload, write_dataset
from apex.data.providers.errors import MarketDataProviderError


def register_dataset_commands(app: typer.Typer) -> None:
    @app.command("export-dataset")
    def export_dataset(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        timeframes: str = typer.Option(..., "--timeframes", help="Comma-separated timeframes."),
        candles: int = typer.Option(1000, "--candles", min=1, max=1000),
        output: Path = typer.Option(..., "--output", dir_okay=False),
        force: bool = typer.Option(False, "--force", help="Allow replacing an existing file."),
    ) -> None:
        canonical = normalize_market_symbol(symbol)
        requested = _parse_timeframes(timeframes)
        try:
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                grouped = {
                    timeframe: tuple(
                        services.candles.fetch_candles(canonical, timeframe, limit=candles)
                    )
                    for timeframe in requested
                }
            sources = sorted(
                {candle.source for values in grouped.values() for candle in values if candle.source}
            )
            payload = build_dataset_payload(
                symbol=canonical,
                candles_by_timeframe=grouped,
                source=",".join(sources) or "configured-provider",
            )
            write_dataset(output, payload, force=force)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Dataset export market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Exported {len(payload['candles'])} closed candles to {output}")


def _parse_timeframes(value: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise ValueError("at least one timeframe is required")
    if len(set(items)) != len(items):
        raise ValueError("timeframes must not contain duplicates")
    return items
