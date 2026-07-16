"""CLI verification for sealed forward-edge evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.validation.forward_edge_artifact_verification import (
    ForwardEdgeArtifactSourceStatus,
    forward_edge_artifact_source_verification_payload,
    verify_forward_edge_artifact_source,
)


def register_forward_edge_artifact_verify_commands(app: typer.Typer) -> None:
    """Register offline sealed forward-edge source verification."""

    @app.command("forward-edge-seal-verify")
    def forward_edge_seal_verify(
        artifact: Annotated[
            Path,
            typer.Option("--artifact", exists=True, dir_okay=False, readable=True),
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
        output: Annotated[str, typer.Option("--output", "-o", help="text or json")] = "text",
    ) -> None:
        """Verify a sealed forward-edge artifact against historical source evidence."""

        normalized_output = output.strip().lower()
        if normalized_output not in {"text", "json"}:
            raise typer.BadParameter("output must be text or json")
        try:
            verification = verify_forward_edge_artifact_source(
                artifact,
                historical_validation,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = forward_edge_artifact_source_verification_payload(verification)
        if normalized_output == "json":
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            reasons = ",".join(verification.reasons) or "none"
            typer.echo(
                "FORWARD_EDGE_ARTIFACT_VERIFY "
                f"| status={verification.status.value} "
                f"| source_matches={str(verification.source_matches).lower()} "
                f"| name_matches={str(verification.historical_validation_name_matches).lower()} "
                f"| reasons={reasons}"
            )

        if verification.status is not ForwardEdgeArtifactSourceStatus.VERIFIED:
            raise typer.Exit(code=2)
