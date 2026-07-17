"""CLI integration for forward-paper setup evidence validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.paper_trading import PaperTradeStore
from apex.validation.forward_edge import (
    ForwardEdgePolicy,
    build_forward_edge_report,
    write_forward_edge_report,
)


def register_forward_edge_commands(app: typer.Typer) -> None:
    """Register forward-paper evidence attachment."""

    @app.command("forward-edge-validate")
    def forward_edge_validate(
        historical_validation: Annotated[
            Path,
            typer.Option("--historical-validation", exists=True, dir_okay=False, readable=True),
        ],
        paper_store: Annotated[
            Path,
            typer.Option("--paper-store", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        minimum_closed_trades: Annotated[
            int,
            typer.Option("--minimum-closed-trades", min=1),
        ] = 30,
        minimum_expectancy: Annotated[
            float,
            typer.Option("--minimum-expectancy", min=0.0),
        ] = 0.0,
        minimum_profit_factor: Annotated[
            float,
            typer.Option("--minimum-profit-factor", min=0.0),
        ] = 1.0,
        maximum_expectancy_degradation: Annotated[
            float,
            typer.Option("--maximum-expectancy-degradation", min=0.0),
        ] = 0.50,
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Attach closed paper outcomes to validated setup segments."""

        try:
            report = build_forward_edge_report(
                historical_validation_path=historical_validation,
                paper_trades=PaperTradeStore(paper_store).load(),
                generated_at=datetime.now(UTC),
                policy=ForwardEdgePolicy(
                    minimum_closed_trades=minimum_closed_trades,
                    minimum_expectancy=minimum_expectancy,
                    minimum_profit_factor=minimum_profit_factor,
                    maximum_expectancy_degradation=maximum_expectancy_degradation,
                ),
            )
            write_forward_edge_report(output, report, force=force)
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FORWARD_EDGE_VALIDATION_COMPLETED "
            f"| campaign_id={report['campaign_id']} "
            f"| segments={report['segment_count']} "
            f"| validated={report['validated_forward_paper_count']} "
            f"| report_id={report['report_id']} "
            f"| output={output}"
        )
