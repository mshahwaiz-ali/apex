"""CLI command for deterministic historical futures campaign backtesting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting import (
    BacktestConfig,
    HistoricalFuturesCampaignRequest,
    load_historical_signal_campaign_inputs,
)
from apex.backtesting.historical_futures_shared_campaign import (
    SharedHistoricalFuturesExecutionManifest,
    execute_shared_historical_futures_campaign,
    write_shared_historical_futures_campaign,
)
from apex.backtesting.shared_wallet_replay import SharedWalletConfig


def register_historical_futures_backtest_commands(dataset_app: typer.Typer) -> None:
    """Register the N4.8 historical futures backtest command."""

    @dataset_app.command("historical-futures-backtest")
    def historical_futures_backtest(
        campaign_id: Annotated[str, typer.Option("--campaign-id")],
        plan_file: Annotated[
            Path,
            typer.Option("--plan", exists=True, dir_okay=False, readable=True),
        ],
        dataset_execution_manifest: Annotated[
            Path,
            typer.Option(
                "--dataset-execution-manifest",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        signal_records: Annotated[
            Path,
            typer.Option("--signal-records", exists=True, dir_okay=False, readable=True),
        ],
        signal_manifest: Annotated[
            Path,
            typer.Option(
                "--signal-manifest",
                "--signal-execution-manifest",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        result_output: Annotated[
            Path,
            typer.Option("--result-output", dir_okay=False),
        ],
        execution_manifest_output: Annotated[
            Path,
            typer.Option("--execution-manifest-output", dir_okay=False),
        ],
        starting_equity: Annotated[
            float,
            typer.Option("--starting-equity", min=0.01),
        ] = 10_000.0,
        fee_pct: Annotated[
            float,
            typer.Option("--fee-pct", min=0.0),
        ] = 0.04,
        slippage_pct: Annotated[
            float,
            typer.Option("--slippage-pct", min=0.0),
        ] = 0.02,
        maximum_holding_candles: Annotated[
            int,
            typer.Option("--maximum-holding-candles", min=1),
        ] = 24,
        conservative_intrabar: Annotated[
            bool,
            typer.Option("--conservative-intrabar/--optimistic-intrabar"),
        ] = True,
        maximum_concurrent_positions: Annotated[
            int,
            typer.Option("--maximum-concurrent-positions", min=1),
        ] = 3,
        maximum_wallet_exposure_pct: Annotated[
            float,
            typer.Option("--maximum-wallet-exposure-pct", min=0.01, max=100.0),
        ] = 50.0,
        daily_loss_limit_pct: Annotated[
            float,
            typer.Option("--daily-loss-limit-pct", min=0.01, max=100.0),
        ] = 10.0,
        consecutive_loss_limit: Annotated[
            int,
            typer.Option("--consecutive-loss-limit", min=1),
        ] = 4,
    ) -> None:
        """Replay verified signals through one chronological shared wallet."""

        try:
            request = HistoricalFuturesCampaignRequest(
                campaign_id=campaign_id,
                records_path=signal_records,
                signal_manifest_path=signal_manifest,
                result_path=result_output,
                execution_manifest_path=execution_manifest_output,
                starting_equity=starting_equity,
                backtest_config=BacktestConfig(
                    fee_pct=fee_pct,
                    slippage_pct=slippage_pct,
                    maximum_holding_candles=maximum_holding_candles,
                    conservative_intrabar=conservative_intrabar,
                ),
            )
            wallet_config = SharedWalletConfig(
                maximum_concurrent_positions=maximum_concurrent_positions,
                maximum_wallet_exposure_pct=maximum_wallet_exposure_pct,
                daily_loss_limit_pct=daily_loss_limit_pct,
                consecutive_loss_limit=consecutive_loss_limit,
            )
            inputs = load_historical_signal_campaign_inputs(
                plan_path=plan_file,
                execution_manifest_path=dataset_execution_manifest,
            )
            result = execute_shared_historical_futures_campaign(
                request=request,
                inputs=inputs,
                wallet_config=wallet_config,
            )
            manifest = write_shared_historical_futures_campaign(
                request=request,
                result=result,
            )
        except (
            FileExistsError,
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise typer.BadParameter(str(exc)) from exc

        _echo_completion(manifest=manifest, result_output=result_output)


def _echo_completion(
    *,
    manifest: SharedHistoricalFuturesExecutionManifest,
    result_output: Path,
) -> None:
    typer.echo(
        "HISTORICAL_FUTURES_BACKTEST_COMPLETED "
        f"| campaign_id={manifest.base.campaign_id} "
        f"| decisions={manifest.base.total_decisions} "
        f"| trades={manifest.base.trade_count} "
        f"| wallet_config_hash={manifest.wallet_configuration_hash} "
        f"| result_hash={manifest.base.result_hash} "
        f"| result={result_output}"
    )
