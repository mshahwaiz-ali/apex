"""CLI command for deterministic historical futures campaign backtesting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting import (
    BacktestConfig,
    HistoricalFuturesCampaignRequest,
    HistoricalFuturesExecutionManifest,
    execute_historical_futures_campaign,
    load_historical_signal_campaign_inputs,
    write_historical_futures_campaign,
)


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
        signal_execution_manifest: Annotated[
            Path,
            typer.Option(
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
    ) -> None:
        """Replay verified historical signals through the canonical backtester."""

        try:
            request = HistoricalFuturesCampaignRequest(
                campaign_id=campaign_id,
                records_path=signal_records,
                signal_manifest_path=signal_execution_manifest,
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
            inputs = load_historical_signal_campaign_inputs(
                plan_path=plan_file,
                execution_manifest_path=dataset_execution_manifest,
            )
            result = execute_historical_futures_campaign(request=request, inputs=inputs)
            manifest = write_historical_futures_campaign(request=request, result=result)
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
    manifest: HistoricalFuturesExecutionManifest,
    result_output: Path,
) -> None:
    typer.echo(
        "HISTORICAL_FUTURES_BACKTEST_COMPLETED "
        f"| campaign_id={manifest.campaign_id} "
        f"| decisions={manifest.total_decisions} "
        f"| trades={manifest.trade_count} "
        f"| result_hash={manifest.result_hash} "
        f"| result={result_output}"
    )
