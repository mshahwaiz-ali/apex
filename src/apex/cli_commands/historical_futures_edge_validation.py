"""CLI integration for historical futures out-of-sample edge validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting.historical_edge_validation import HistoricalEdgeValidationPolicy
from apex.backtesting.historical_futures_edge_validation import (
    build_historical_futures_edge_validation_report,
    write_historical_futures_edge_validation_report,
)


def register_historical_futures_edge_validation_commands(app: typer.Typer) -> None:
    """Register N4.9 out-of-sample evidence validation."""

    @app.command("historical-futures-edge-validate")
    def historical_futures_edge_validate(
        edge_report: Annotated[
            Path,
            typer.Option("--edge-report", exists=True, dir_okay=False, readable=True),
        ],
        output_file: Annotated[
            Path,
            typer.Option("--output", dir_okay=False),
        ],
        minimum_validation_trades: Annotated[
            int,
            typer.Option("--minimum-validation-trades", min=1),
        ] = 50,
        minimum_final_test_trades: Annotated[
            int,
            typer.Option("--minimum-final-test-trades", min=1),
        ] = 50,
        minimum_out_of_sample_trades: Annotated[
            int,
            typer.Option("--minimum-out-of-sample-trades", min=1),
        ] = 100,
        minimum_profit_factor: Annotated[
            float,
            typer.Option("--minimum-profit-factor", min=0.0),
        ] = 1.0,
        maximum_validation_expectancy_degradation: Annotated[
            float,
            typer.Option("--maximum-validation-expectancy-degradation", min=0.0),
        ] = 0.50,
        maximum_final_test_expectancy_degradation: Annotated[
            float,
            typer.Option("--maximum-final-test-expectancy-degradation", min=0.0),
        ] = 0.60,
        force: Annotated[
            bool,
            typer.Option("--force", help="Allow replacing an existing validation report."),
        ] = False,
    ) -> None:
        """Evaluate train, validation, and untouched final-test edge stability."""

        try:
            policy = HistoricalEdgeValidationPolicy(
                minimum_validation_trades=minimum_validation_trades,
                minimum_test_trades=minimum_final_test_trades,
                minimum_out_of_sample_trades=minimum_out_of_sample_trades,
                minimum_profit_factor=minimum_profit_factor,
                maximum_validation_expectancy_degradation=(
                    maximum_validation_expectancy_degradation
                ),
                maximum_test_expectancy_degradation=(
                    maximum_final_test_expectancy_degradation
                ),
            )
            report = build_historical_futures_edge_validation_report(
                edge_report_path=edge_report,
                generated_at=datetime.now(UTC),
                policy=policy,
            )
            write_historical_futures_edge_validation_report(
                output_file,
                report,
                force=force,
            )
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "HISTORICAL_FUTURES_EDGE_VALIDATION_COMPLETED "
            f"| campaign_id={report['campaign_id']} "
            f"| segments={report['segment_count']} "
            f"| validated={report['validated_out_of_sample_count']} "
            f"| report_id={report['report_id']} "
            f"| output={output_file}"
        )
