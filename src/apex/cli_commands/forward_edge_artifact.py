"""CLI support for sealing forward-edge evidence reports."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.validation.forward_edge import load_forward_edge_report
from apex.validation.forward_edge_artifact import (
    build_forward_edge_artifact,
    write_forward_edge_artifact,
)


def register_forward_edge_artifact_commands(app: typer.Typer) -> None:
    """Register deterministic forward-edge artifact sealing."""

    @app.command("forward-edge-seal")
    def forward_edge_seal(
        report: Annotated[
            Path,
            typer.Option("--report", exists=True, dir_okay=False, readable=True),
        ],
        historical_validation: Annotated[
            Path,
            typer.Option(
                "--historical-validation",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Seal a forward-edge report with exact historical source provenance."""

        try:
            report_payload = load_forward_edge_report(report)
            artifact = build_forward_edge_artifact(
                report_payload,
                historical_validation_path=historical_validation,
            )
            write_forward_edge_artifact(output, artifact, force=force)
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        source = artifact["source"]
        typer.echo(
            "FORWARD_EDGE_ARTIFACT_SEALED "
            f"| report_id={report_payload['report_id']} "
            f"| campaign_id={report_payload['campaign_id']} "
            f"| source_sha256={source['historical_validation_sha256']} "
            f"| artifact_sha256={artifact['artifact_sha256']} "
            f"| output={output}"
        )
