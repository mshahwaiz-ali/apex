"""CLI command for live public-data spot orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.application import bootstrap, create_market_data_services
from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_live import analyze_live_spot, load_spot_live_account
from apex.application.spot_orchestration_io import (
    DEFAULT_SPOT_CONFIG_PATH,
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
    write_spot_orchestration_result,
)
from apex.cli_commands.spot_output import emit_spot_analysis, output_mode
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.data.providers.errors import MarketDataProviderError


def register_spot_live_commands(app: typer.Typer) -> None:
    """Register live public-data spot analysis."""

    @app.command("spot-live")
    def spot_live(
        symbol: Annotated[str, typer.Argument(help="Spot symbol, for example BTCUSDT.")],
        account: Annotated[
            Path,
            typer.Option("--account", exists=True, dir_okay=False, readable=True),
        ],
        config: Annotated[
            Path,
            typer.Option("--config", exists=True, dir_okay=False, readable=True),
        ] = DEFAULT_SPOT_CONFIG_PATH,
        strategy_config: Annotated[
            Path,
            typer.Option(
                "--strategy-config",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ] = DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
        output: Annotated[
            Path | None,
            typer.Option("--output", dir_okay=False, help="Optional JSON file destination."),
        ] = None,
        output_format: Annotated[
            str,
            typer.Option("--format", help="text, json, verbose, or debug"),
        ] = "text",
        candles: Annotated[
            int,
            typer.Option("--candles", min=60, max=1000),
        ] = 200,
    ) -> None:
        """Fetch public candles and run canonical long-only cash spot analysis."""

        mode = output_mode(output_format)
        try:
            context = bootstrap()
            account_input = load_spot_live_account(account)
            product_config = load_spot_product_config(config)
            strategies = load_spot_strategy_config(strategy_config)
            with create_market_data_services(context.settings) as services:
                result = analyze_live_spot(
                    symbol=symbol,
                    account_input=account_input,
                    candle_provider=services.candles,
                    ticker_provider=services.ticker,
                    product_config=product_config,
                    strategy_config=strategies,
                    candle_limit=candles,
                )
            payload = spot_analysis_result_to_payload(result)
            if output is not None:
                write_spot_orchestration_result(output, result)
        except MarketDataProviderError as exc:
            typer.echo(f"Spot market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        emit_spot_analysis(payload, mode=mode, title="Live Spot Analysis")
