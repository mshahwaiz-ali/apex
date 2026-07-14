"""Deterministic multi-timeframe dataset campaign commands."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from apex.application import bootstrap, create_market_data_services, load_symbols
from apex.backtesting import (
    MAXIMUM_DATASET_CANDLES,
    FuturesDatasetCampaignExecutionError,
    FuturesDatasetSplitRatios,
    execute_futures_dataset_campaign,
    load_futures_dataset_campaign_execution_result,
    load_futures_dataset_campaign_plan,
    plan_futures_dataset_campaign,
    verify_futures_dataset_campaign_execution,
    write_futures_dataset_campaign_execution_result,
    write_futures_dataset_campaign_plan,
)
from apex.backtesting.dataset_campaign import verify_futures_dataset_campaign_matrix
from apex.cli_overlay import remove_commands
from apex.data.providers.errors import MarketDataProviderError


def register_dataset_campaign_commands(dataset_app: typer.Typer) -> None:
    """Replace legacy singular-timeframe campaign commands."""

    remove_commands(dataset_app, {"campaign-plan", "campaign-execute"})

    @dataset_app.command("campaign-plan")
    def dataset_campaign_plan(
        campaign_id: Annotated[str, typer.Option("--campaign-id")],
        manifest_output: Annotated[
            Path,
            typer.Option("--manifest-output", dir_okay=False),
        ],
        timeframes: Annotated[
            list[str] | None,
            typer.Option(
                "--timeframe",
                "-t",
                help="Repeat for each historical candle timeframe.",
            ),
        ] = None,
        symbols_file: Annotated[
            Path,
            typer.Option(
                "--symbols-file",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ] = Path("config/symbols.yaml"),
        candle_count: Annotated[
            int,
            typer.Option("--candles", "-c", min=1, max=MAXIMUM_DATASET_CANDLES),
        ] = 1_000,
        provider: Annotated[str, typer.Option("--provider")] = "binance",
        output_directory: Annotated[
            Path,
            typer.Option("--output-dir", file_okay=False),
        ] = Path("data/datasets/futures"),
        train_ratio: Annotated[float, typer.Option("--train-ratio")] = 0.60,
        validation_ratio: Annotated[float, typer.Option("--validation-ratio")] = 0.20,
        test_ratio: Annotated[float, typer.Option("--test-ratio")] = 0.20,
    ) -> None:
        """Plan and verify a deterministic symbol x timeframe campaign."""

        try:
            plan = plan_futures_dataset_campaign(
                campaign_id=campaign_id,
                symbols=tuple(load_symbols(symbols_file)),
                timeframes=tuple(timeframes or ("5m",)),
                provider=provider,
                candle_count=candle_count,
                output_directory=output_directory,
                split_ratios=FuturesDatasetSplitRatios(
                    train=train_ratio,
                    validation=validation_ratio,
                    final_test=test_ratio,
                ),
                reserved_output_paths=(manifest_output,),
            )
            write_futures_dataset_campaign_plan(manifest_output, plan)
            verified = load_futures_dataset_campaign_plan(manifest_output)
            verify_futures_dataset_campaign_matrix(verified)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "DATASET_CAMPAIGN_PLANNED "
            f"| campaign_id={verified.campaign_id} "
            f"| symbols={len(verified.symbols)} "
            f"| timeframes={','.join(verified.timeframes)} "
            f"| jobs={len(verified.jobs)} "
            f"| candles={verified.candle_count} "
            f"| provider={verified.provider} "
            f"| manifest={manifest_output}"
        )

    @dataset_app.command("campaign-execute")
    def dataset_campaign_execute(
        plan_file: Annotated[
            Path,
            typer.Option("--plan", exists=True, dir_okay=False, readable=True),
        ],
        execution_manifest_output: Annotated[
            Path,
            typer.Option("--execution-manifest-output", dir_okay=False),
        ],
    ) -> None:
        """Execute and verify one frozen historical dataset campaign."""

        try:
            plan = load_futures_dataset_campaign_plan(plan_file)
            verify_futures_dataset_campaign_matrix(plan)
            configured_provider = "binance"
            if plan.provider != configured_provider:
                raise ValueError(
                    "campaign provider does not match configured provider: "
                    f"plan={plan.provider}, configured={configured_provider}"
                )
            context = bootstrap()
            with create_market_data_services(
                context.settings,
                provider_name=configured_provider,
            ) as services:
                result = execute_futures_dataset_campaign(
                    plan=plan,
                    provider=services.candles,
                    configured_provider=configured_provider,
                    extracted_at=datetime.now(UTC),
                    execution_manifest_path=execution_manifest_output,
                )
            verify_futures_dataset_campaign_matrix(plan, result.jobs)
            verify_futures_dataset_campaign_execution(plan=plan, result=result)
            write_futures_dataset_campaign_execution_result(
                execution_manifest_output,
                result,
            )
            verified = load_futures_dataset_campaign_execution_result(execution_manifest_output)
            verify_futures_dataset_campaign_matrix(plan, verified.jobs)
            verify_futures_dataset_campaign_execution(plan=plan, result=verified)
        except FuturesDatasetCampaignExecutionError as exc:
            typer.echo(
                "DATASET_CAMPAIGN_EXECUTION_FAILED "
                f"| campaign_id={exc.result.campaign_id} "
                f"| completed_jobs={exc.result.completed_jobs} "
                f"| failed_jobs={exc.result.failed_jobs} "
                f"| reason={exc}",
                err=True,
            )
            raise typer.Exit(code=1) from exc
        except MarketDataProviderError as exc:
            _provider_failure(exc)
        except (FileExistsError, KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "DATASET_CAMPAIGN_EXECUTED "
            f"| campaign_id={verified.campaign_id} "
            f"| provider={verified.provider} "
            f"| symbols={len(plan.symbols)} "
            f"| timeframes={','.join(plan.timeframes)} "
            f"| planned_jobs={verified.total_planned_jobs} "
            f"| completed_jobs={verified.completed_jobs} "
            f"| failed_jobs={verified.failed_jobs} "
            f"| status={verified.status.value} "
            f"| manifest={execution_manifest_output}"
        )


def _provider_failure(error: MarketDataProviderError) -> NoReturn:
    typer.echo(f"Dataset campaign execution failed: {error}", err=True)
    raise typer.Exit(code=1) from error
