"""CLI orchestration for the complete N4 evidence pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer

from apex.validation.evidence_pipeline import run_evidence_pipeline
from apex.validation.forward_edge import ForwardEdgePolicy


def register_evidence_pipeline_commands(app: typer.Typer) -> None:
    """Register the final N4 evidence pipeline command."""

    @app.command("evidence-pipeline-run")
    def evidence_pipeline_run(
        result: Annotated[
            Path,
            typer.Option("--result", exists=True, dir_okay=False, readable=True),
        ],
        execution_manifest: Annotated[
            Path,
            typer.Option(
                "--execution-manifest",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        dimensions_file: Annotated[
            Path,
            typer.Option("--dimensions", exists=True, dir_okay=False, readable=True),
        ],
        output_directory: Annotated[
            Path,
            typer.Option("--output-directory", file_okay=False),
        ],
        paper_store: Annotated[
            Path | None,
            typer.Option("--paper-store", exists=True, dir_okay=False, readable=True),
        ] = None,
        minimum_forward_trades: Annotated[
            int,
            typer.Option("--minimum-forward-trades", min=1),
        ] = 30,
        minimum_forward_expectancy: Annotated[
            float,
            typer.Option("--minimum-forward-expectancy", min=0.0),
        ] = 0.0,
        minimum_forward_profit_factor: Annotated[
            float,
            typer.Option("--minimum-forward-profit-factor", min=0.0),
        ] = 1.0,
        maximum_forward_expectancy_degradation: Annotated[
            float,
            typer.Option("--maximum-forward-expectancy-degradation", min=0.0),
        ] = 0.50,
        maximum_evidence_age_days: Annotated[
            int | None,
            typer.Option("--maximum-evidence-age-days", min=1),
        ] = None,
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Publish N4.8 through N4.11 evidence artifacts as one atomic run."""

        try:
            dimensions = _load_dimensions(dimensions_file)
            pipeline = run_evidence_pipeline(
                result_path=result,
                execution_manifest_path=execution_manifest,
                dimensions=dimensions,
                output_directory=output_directory,
                generated_at=datetime.now(UTC),
                paper_store_path=paper_store,
                forward_policy=(
                    ForwardEdgePolicy(
                        minimum_closed_trades=minimum_forward_trades,
                        minimum_expectancy=minimum_forward_expectancy,
                        minimum_profit_factor=minimum_forward_profit_factor,
                        maximum_expectancy_degradation=(
                            maximum_forward_expectancy_degradation
                        ),
                    )
                    if paper_store is not None
                    else None
                ),
                maximum_evidence_age=(
                    timedelta(days=maximum_evidence_age_days)
                    if maximum_evidence_age_days is not None
                    else None
                ),
                force=force,
            )
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "EVIDENCE_PIPELINE_COMPLETED "
            f"| pipeline_id={pipeline.pipeline_id} "
            f"| output={pipeline.output_directory} "
            f"| forward_paper={pipeline.forward_validation_path is not None}"
        )


def _load_dimensions(path: Path) -> dict[str, str]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("pipeline dimensions file must contain a non-empty string mapping")
    return dict(value)
