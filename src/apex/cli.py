"""Apex command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex import __version__
from apex.application import bootstrap
from apex.config import load_settings
from apex.data.cache.candles import FileCandleCache
from apex.data.providers import (
    BinanceMarketDataProvider,
    CachedMarketDataProvider,
)

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


@app.command("fetch")
def fetch_candles(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    timeframe: str = typer.Option("15m", "--timeframe", "-t"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=1000),
) -> None:
    """Fetch live public OHLCV candles from Binance."""

    try:
        context = bootstrap()
        cache = FileCandleCache(context.settings.data_dir / "cache" / "candles")

        with BinanceMarketDataProvider() as live_provider:
            provider = CachedMarketDataProvider(
                live_provider,
                cache,
            )
            candles = provider.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        typer.echo(f"Market-data request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

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
    """Fetch the current public market ticker from Binance."""

    try:
        with BinanceMarketDataProvider() as provider:
            snapshot = provider.fetch_ticker(symbol)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        typer.echo(f"Ticker request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(snapshot.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    app()
