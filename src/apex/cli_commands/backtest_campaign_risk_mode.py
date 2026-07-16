"""Risk-mode aware chronological backtest campaign CLI overlay."""

# mypy: disable-error-code="attr-defined"

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

from apex.application import BacktestCampaignRequest, MultiSymbolBacktestCampaignRequest
from apex.application.futures_risk_mode import futures_risk_mode_scope
from apex.cli_commands import backtesting as backtesting_cli
from apex.data.providers.errors import MarketDataProviderError
from apex.domain import Candle, RiskMode
from apex.risk import RiskConfig, resolve_risk_config_for_mode


def register_risk_mode_campaign_command(app: typer.Typer) -> None:
    """Register the corrected campaign command after removing the legacy version."""

    @app.command("chronological-backtest-campaign")
    def chronological_backtest_campaign(
        symbol: Annotated[
            str,
            typer.Argument(help="Any provider-supported market symbol."),
        ],
        variants: Annotated[
            str | None,
            typer.Option(
                "--variants",
                help=(
                    "Comma-separated id:timeframe:candles:interval:cooldown entries. "
                    "Defaults to baseline, fast-decisions, and slower-decisions."
                ),
            ),
        ] = None,
        history_limit: Annotated[
            int,
            typer.Option("--history-candles", min=80, max=1500),
        ] = 600,
        risk_mode: Annotated[
            RiskMode,
            typer.Option(
                "--risk-mode",
                case_sensitive=False,
                help="Strategy approval mode: STANDARD.",
            ),
        ] = RiskMode.STANDARD,
        dataset: Annotated[
            Path | None,
            typer.Option(
                "--dataset",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Optional local .json or .csv historical candle dataset.",
            ),
        ] = None,
        report_output: Annotated[
            Path | None,
            typer.Option(
                "--report-output",
                dir_okay=False,
                help="Optional path for the complete JSON campaign report.",
            ),
        ] = None,
        record_db: Annotated[
            Path | None,
            typer.Option(
                "--record-db",
                dir_okay=False,
                help="Optional SQLite database for reproducible campaign reports.",
            ),
        ] = None,
        force: Annotated[
            bool,
            typer.Option("--force", help="Allow replacing report output."),
        ] = False,
    ) -> None:
        """Run chronological variants under one explicit futures risk mode."""

        try:
            symbols = backtesting_cli._parse_campaign_symbols(symbol)
            parsed_variants = backtesting_cli.parse_campaign_variants(variants)
            context = backtesting_cli.bootstrap()
            base_risk_config = backtesting_cli.load_default_risk_config()
            risk_config = (
                resolve_risk_config_for_mode(base_risk_config, risk_mode)
                if isinstance(base_risk_config, RiskConfig)
                else base_risk_config
            )
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            replay_timeframes = tuple(variant.replay_timeframe for variant in parsed_variants)
            required_timeframes = tuple(dict.fromkeys((*analysis_timeframes, *replay_timeframes)))
            candles: Mapping[str, tuple[Candle, ...]]
            candles_by_symbol: Mapping[str, Mapping[str, tuple[Candle, ...]]]
            if dataset is None:
                with backtesting_cli.create_market_data_services(context.settings) as services:
                    candles_by_symbol = {
                        item: {
                            timeframe: tuple(
                                services.candles.fetch_candles(
                                    item,
                                    timeframe,
                                    limit=history_limit,
                                )
                            )
                            for timeframe in required_timeframes
                        }
                        for item in symbols
                    }
                dataset_source = "live-provider"
            else:
                candles = backtesting_cli.load_historical_candles(
                    dataset,
                    required_timeframes=required_timeframes,
                )
                candles_by_symbol = backtesting_cli.split_campaign_candles_by_symbol(
                    candles,
                    symbols,
                )
                dataset_source = str(dataset)

            with futures_risk_mode_scope(risk_mode):
                if len(symbols) == 1:
                    result = backtesting_cli.run_backtest_campaign(
                        BacktestCampaignRequest(
                            symbol=symbols[0],
                            candles_by_timeframe=candles_by_symbol[symbols[0]],
                            analysis_timeframes=analysis_timeframes,
                            variants=parsed_variants,
                            dataset_source=dataset_source,
                            risk_config=risk_config,
                            strategy_routing=getattr(context.settings, "strategy_routing", None),
                        )
                    )
                else:
                    result = backtesting_cli.run_multi_symbol_backtest_campaign(
                        MultiSymbolBacktestCampaignRequest(
                            symbols=symbols,
                            candles_by_symbol=candles_by_symbol,
                            analysis_timeframes=analysis_timeframes,
                            variants=parsed_variants,
                            dataset_source=dataset_source,
                            risk_config=risk_config,
                            strategy_routing=getattr(context.settings, "strategy_routing", None),
                        )
                    )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Chronological campaign market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = backtesting_cli.campaign_result_to_payload(result)
        payload["risk_mode"] = risk_mode.value
        configuration_id = getattr(risk_config, "identifier", None)
        if isinstance(configuration_id, str):
            payload["risk_configuration_id"] = configuration_id
        if report_output is not None:
            try:
                backtesting_cli.write_backtest_report(report_output, payload, force=force)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
        if record_db is not None:
            backtesting_cli.write_backtest_campaign_sqlite(record_db, payload)
        typer.echo(backtesting_cli.dumps_report(payload), nl=False)
