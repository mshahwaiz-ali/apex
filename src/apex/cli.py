"""Apex command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex import __version__
from apex.application import bootstrap, create_market_data_services
from apex.config import load_settings
from apex.data.providers.errors import MarketDataProviderError

app = typer.Typer(help="Apex Trading Agent command line interface.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed Apex version."""

    typer.echo(__version__)


@app.command("validate-config")
def validate_config(
    config_dir: Path = typer.Option(Path("config"), exists=True, file_okay=False),  # noqa: B008
) -> None:
    """Validate the default Apex configuration."""

    settings = load_settings(config_dir)
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command()
def smoke() -> None:
    """Run a minimal end-to-end application bootstrap check."""

    context = bootstrap()
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "version": __version__,
                "environment": context.settings.environment,
            },
            indent=2,
        )
    )


def _exit_for_provider_error(prefix: str, error: MarketDataProviderError) -> None:
    typer.echo(f"{prefix}: {error}", err=True)
    raise typer.Exit(code=1) from error


@app.command("fetch")
def fetch_candles(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    timeframe: str = typer.Option("15m", "--timeframe", "-t"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=1000),
) -> None:
    """Fetch live public OHLCV candles from the configured provider."""

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            candles = services.candles.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Market-data request failed", exc)

    typer.echo(
        json.dumps(
            [candle.model_dump(mode="json") for candle in candles],
            indent=2,
        )
    )


@app.command("ticker")
def ticker(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
) -> None:
    """Fetch the current public market ticker from the configured provider."""

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            snapshot = services.ticker.fetch_ticker(symbol)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Ticker request failed", exc)

    typer.echo(json.dumps(snapshot.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    app()
