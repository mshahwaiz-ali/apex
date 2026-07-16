"""CLI command for deterministic multi-symbol live spot scanning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.application import bootstrap, create_market_data_services
from apex.application.spot_live import load_spot_live_account
from apex.application.spot_live_scanner import scan_live_spot, spot_live_scan_result_to_payload
from apex.application.spot_orchestration_io import (
    DEFAULT_SPOT_CONFIG_PATH,
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
)
from apex.cli_commands.spot_output import emit_spot_scan, output_mode
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain.spot_market import SpotScannerMode


def register_spot_live_scanner_commands(app: typer.Typer) -> None:
    """Register live spot universe scanning."""

    @app.command("spot-scan-live")
    def spot_scan_live(
        symbols: Annotated[
            str,
            typer.Option("--symbols", help="Comma-separated spot symbols."),
        ],
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
        mode: Annotated[
            SpotScannerMode,
            typer.Option(
                "--mode",
                case_sensitive=False,
                help="Eligibility mode: eligible, watchlist, or all.",
            ),
        ] = SpotScannerMode.ELIGIBLE,
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
        """Evaluate eligibility, then scan selected cash-spot symbols."""

        selected_output_mode = output_mode(output_format)
        try:
            context = bootstrap()
            account_input = load_spot_live_account(account)
            product_config = load_spot_product_config(config)
            strategies = load_spot_strategy_config(strategy_config)
            requested_symbols = tuple(item for item in symbols.split(","))
            with create_market_data_services(context.settings) as services:
                result = scan_live_spot(
                    symbols=requested_symbols,
                    account_input=account_input,
                    candle_provider=services.candles,
                    ticker_provider=services.ticker,
                    product_config=product_config,
                    strategy_config=strategies,
                    mode=mode,
                    candle_limit=candles,
                )
            payload = spot_live_scan_result_to_payload(result)
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        emit_spot_scan(payload, mode=selected_output_mode)
