"""Professional system and public market-data CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from apex import __version__
from apex.application import bootstrap, create_market_data_services, normalize_market_symbol
from apex.config import load_settings
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.system import (
    render_candles,
    render_config,
    render_smoke,
    render_ticker,
    render_version,
)


def register_system_commands(app: typer.Typer) -> None:
    """Register human-readable system and market-data commands."""

    @app.command("fetch")
    def fetch_candles(
        symbol: Annotated[
            str,
            typer.Argument(help="Trading pair, including compact BTCUSDT form."),
        ],
        timeframe: Annotated[str, typer.Option("--timeframe", "-t")] = "15m",
        limit: Annotated[int, typer.Option("--limit", "-l", min=1, max=1000)] = 10,
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Fetch recent public candles and summarize the returned market data."""

        output_mode = _output_mode(output)
        canonical = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                candles = services.candles.fetch_candles(
                    symbol=canonical,
                    timeframe=timeframe,
                    limit=limit,
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            _provider_error("Market-data request failed", exc)
        payload = [candle.model_dump(mode="json") for candle in candles]
        _emit(payload, render_candles(payload, mode=output_mode), output_mode)

    @app.command("ticker")
    def ticker(
        symbol: Annotated[
            str,
            typer.Argument(help="Trading pair, including compact BTCUSDT form."),
        ],
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Fetch and explain the current public ticker snapshot."""

        output_mode = _output_mode(output)
        canonical = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                snapshot = services.ticker.fetch_ticker(canonical)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            _provider_error("Ticker request failed", exc)
        payload = snapshot.model_dump(mode="json")
        _emit(payload, render_ticker(payload, mode=output_mode), output_mode)

    @app.command("validate-config")
    def validate_config(
        config_dir: Annotated[
            Path,
            typer.Option("--config-dir", exists=True, file_okay=False),
        ] = Path("config"),
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Validate and summarize the resolved Apex configuration."""

        output_mode = _output_mode(output)
        settings = load_settings(config_dir)
        payload = settings.model_dump(mode="json")
        _emit(payload, render_config(payload, mode=output_mode), output_mode)

    @app.command("smoke")
    def smoke(
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Run a minimal bootstrap check and report application readiness."""

        output_mode = _output_mode(output)
        context = bootstrap()
        payload = {
            "status": "ok",
            "version": __version__,
            "environment": context.settings.environment,
        }
        _emit(payload, render_smoke(payload), output_mode)

    @app.command("version")
    def version(
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Show the installed Apex version."""

        output_mode = _output_mode(output)
        payload = {"version": __version__}
        _emit(payload, render_version(__version__), output_mode)


def _output_mode(value: str) -> OutputMode:
    try:
        return normalize_cli_output_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(text)


def _provider_error(prefix: str, error: MarketDataProviderError) -> NoReturn:
    typer.echo(f"{prefix}: {error}", err=True)
    raise typer.Exit(code=1) from error


__all__ = ["register_system_commands"]
