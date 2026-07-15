"""CLI for deterministic chronological cash-spot backtesting."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from apex.application.spot_historical_backtest import (
    SpotBacktestConfig,
    run_spot_historical_backtest,
    write_spot_historical_backtest,
)
from apex.application.spot_historical_backtest_io import (
    load_and_verify_spot_historical_backtest,
)


def register_spot_historical_backtest_commands(dataset_app: typer.Typer) -> None:
    @dataset_app.command("spot-history-backtest")
    def spot_history_backtest(
        campaign_id: Annotated[str, typer.Option("--campaign-id")],
        dataset_records: Annotated[
            Path, typer.Option("--dataset-records", exists=True, dir_okay=False, readable=True)
        ],
        dataset_manifest: Annotated[
            Path, typer.Option("--dataset-manifest", exists=True, dir_okay=False, readable=True)
        ],
        replay_records: Annotated[
            Path, typer.Option("--replay-records", exists=True, dir_okay=False, readable=True)
        ],
        replay_manifest: Annotated[
            Path, typer.Option("--replay-manifest", exists=True, dir_okay=False, readable=True)
        ],
        result_output: Annotated[
            Path, typer.Option("--result-output", dir_okay=False)
        ] = Path("data/spot/backtest.json"),
        execution_manifest_output: Annotated[
            Path, typer.Option("--execution-manifest-output", dir_okay=False)
        ] = Path("data/spot/backtest.manifest.json"),
        starting_cash: Annotated[float, typer.Option("--starting-cash", min=0.01)] = 10_000.0,
        fee_rate: Annotated[float, typer.Option("--fee-rate", min=0.0, max=0.099999)] = 0.001,
        slippage_rate: Annotated[
            float, typer.Option("--slippage-rate", min=0.0, max=0.099999)
        ] = 0.0005,
        maximum_position_allocation: Annotated[
            float, typer.Option("--maximum-position-allocation", min=0.000001, max=1.0)
        ] = 0.25,
        maximum_total_exposure: Annotated[
            float, typer.Option("--maximum-total-exposure", min=0.000001, max=1.0)
        ] = 0.80,
        maximum_open_positions: Annotated[
            int, typer.Option("--maximum-open-positions", min=1)
        ] = 4,
        quote_reserve: Annotated[
            float, typer.Option("--quote-reserve", min=0.0, max=0.999999)
        ] = 0.10,
        entry_expiry_hours: Annotated[int, typer.Option("--entry-expiry-hours", min=1)] = 48,
        maximum_holding_hours: Annotated[
            int, typer.Option("--maximum-holding-hours", min=1)
        ] = 720,
        ambiguous_candle_policy: Annotated[
            Literal["conservative", "optimistic"],
            typer.Option("--ambiguous-candle-policy"),
        ] = "conservative",
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Backtest verified replay plans with shared cash and no future leakage."""

        try:
            result = run_spot_historical_backtest(
                campaign_id=campaign_id,
                dataset_records_path=dataset_records,
                dataset_manifest_path=dataset_manifest,
                replay_records_path=replay_records,
                replay_manifest_path=replay_manifest,
                config=SpotBacktestConfig(
                    starting_cash=starting_cash,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    maximum_position_allocation=maximum_position_allocation,
                    maximum_total_exposure=maximum_total_exposure,
                    maximum_open_positions=maximum_open_positions,
                    quote_reserve=quote_reserve,
                    entry_expiry_hours=entry_expiry_hours,
                    maximum_holding_hours=maximum_holding_hours,
                    ambiguous_candle_policy=ambiguous_candle_policy,
                ),
            )
            write_spot_historical_backtest(
                result=result,
                result_path=result_output,
                manifest_path=execution_manifest_output,
                force=force,
            )
            verified = load_and_verify_spot_historical_backtest(
                result_path=result_output,
                manifest_path=execution_manifest_output,
            )
        except (FileExistsError, KeyError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "SPOT_HISTORICAL_BACKTEST_COMPLETED "
            f"| campaign_id={verified.manifest.campaign_id} "
            f"| signals={verified.manifest.signal_count} "
            f"| plans={verified.manifest.plan_count} "
            f"| fills={verified.manifest.fill_count} "
            f"| trades={verified.manifest.trade_count} "
            f"| ending_equity={verified.manifest.ending_equity:.8f} "
            f"| result_hash={verified.manifest.result_sha256} "
            f"| result={result_output} "
            f"| manifest={execution_manifest_output}"
        )
