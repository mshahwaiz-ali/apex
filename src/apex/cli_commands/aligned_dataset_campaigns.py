"""CLI commands for timestamp-aligned historical dataset campaigns."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.application import load_symbols
from apex.backtesting.aligned_dataset_campaign import (
    load_aligned_dataset_campaign_plan,
    plan_aligned_dataset_campaign,
    write_aligned_dataset_campaign_plan,
)
from apex.backtesting.aligned_dataset_campaign_execution import (
    execute_aligned_dataset_campaign,
    load_aligned_dataset_campaign_execution_result,
    verify_aligned_dataset_campaign_execution,
)
from apex.backtesting.dataset_split import FuturesDatasetSplitRatios
from apex.data.providers.binance_range import BinanceHistoricalRangeProvider


def register_aligned_dataset_campaign_commands(dataset_app: typer.Typer) -> None:
    """Register explicit aligned-coverage planning and execution commands."""

    @dataset_app.command("aligned-campaign-plan")
    def aligned_campaign_plan(
        campaign_id: Annotated[str, typer.Option("--campaign-id")],
        analysis_start: Annotated[str, typer.Option("--analysis-start")],
        analysis_end: Annotated[str, typer.Option("--analysis-end")],
        manifest_output: Annotated[Path, typer.Option("--manifest-output", dir_okay=False)],
        timeframes: Annotated[
            list[str] | None,
            typer.Option("--timeframe", "-t", help="Repeat for every required timeframe."),
        ] = None,
        symbols_file: Annotated[
            Path,
            typer.Option("--symbols-file", exists=True, dir_okay=False, readable=True),
        ] = Path("config/symbols.yaml"),
        output_directory: Annotated[
            Path,
            typer.Option("--output-dir", file_okay=False),
        ] = Path("data/datasets/futures/aligned"),
        warmup_candles: Annotated[int, typer.Option("--warmup-candles", min=40)] = 200,
        provider: Annotated[str, typer.Option("--provider")] = "binance",
        train_ratio: Annotated[float, typer.Option("--train-ratio")] = 0.60,
        validation_ratio: Annotated[float, typer.Option("--validation-ratio")] = 0.20,
        test_ratio: Annotated[float, typer.Option("--test-ratio")] = 0.20,
    ) -> None:
        """Plan one common-period multi-timeframe dataset campaign."""

        try:
            plan = plan_aligned_dataset_campaign(
                campaign_id=campaign_id,
                symbols=tuple(load_symbols(symbols_file)),
                timeframes=tuple(timeframes or ("1m", "3m", "5m", "15m", "30m", "1h", "4h")),
                provider=provider,
                analysis_start=_parse_datetime(analysis_start),
                analysis_end=_parse_datetime(analysis_end),
                output_directory=output_directory,
                warmup_candles=warmup_candles,
                split_ratios=FuturesDatasetSplitRatios(
                    train=train_ratio,
                    validation=validation_ratio,
                    final_test=test_ratio,
                ),
            )
            reserved = {Path(job.dataset_path).resolve(strict=False) for job in plan.jobs}
            if manifest_output.resolve(strict=False) in reserved:
                raise ValueError("aligned campaign manifest conflicts with a dataset path")
            write_aligned_dataset_campaign_plan(manifest_output, plan)
            verified = load_aligned_dataset_campaign_plan(manifest_output)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "ALIGNED_DATASET_CAMPAIGN_PLANNED "
            f"| campaign_id={verified.campaign_id} "
            f"| symbols={len(verified.symbols)} "
            f"| timeframes={','.join(verified.timeframes)} "
            f"| jobs={len(verified.jobs)} "
            f"| warmup_start={verified.warmup_start.isoformat()} "
            f"| analysis_start={verified.boundaries.analysis_start.isoformat()} "
            f"| analysis_end={verified.boundaries.analysis_end.isoformat()} "
            f"| manifest={manifest_output}"
        )

    @dataset_app.command("aligned-campaign-execute")
    def aligned_campaign_execute(
        plan_file: Annotated[
            Path,
            typer.Option("--plan", exists=True, dir_okay=False, readable=True),
        ],
        execution_manifest_output: Annotated[
            Path,
            typer.Option("--execution-manifest-output", dir_okay=False),
        ],
    ) -> None:
        """Execute and verify a frozen aligned dataset campaign."""

        try:
            plan = load_aligned_dataset_campaign_plan(plan_file)
            if plan.provider != "binance":
                raise ValueError("aligned CLI currently supports the binance provider only")
            with BinanceHistoricalRangeProvider() as provider:
                result = execute_aligned_dataset_campaign(
                    plan=plan,
                    provider=provider,
                    plan_path=plan_file,
                    execution_manifest_path=execution_manifest_output,
                    extracted_at=datetime.now(UTC),
                )
            verified = load_aligned_dataset_campaign_execution_result(
                execution_manifest_output
            )
            verify_aligned_dataset_campaign_execution(plan=plan, result=verified)
        except (FileExistsError, KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "ALIGNED_DATASET_CAMPAIGN_EXECUTED "
            f"| campaign_id={verified.campaign_id} "
            f"| provider={verified.provider} "
            f"| planned_jobs={len(verified.jobs)} "
            f"| completed_jobs={len(verified.jobs)} "
            "| failed_jobs=0 | status=completed "
            f"| manifest={execution_manifest_output}"
        )


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("aligned campaign timestamps must include a timezone")
    return parsed
