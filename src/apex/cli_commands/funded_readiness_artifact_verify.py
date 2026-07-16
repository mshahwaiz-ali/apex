"""CLI verification for sealed funded-readiness evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.funded.readiness_artifact_verification import (
    FundedReadinessArtifactSourceStatus,
    funded_readiness_artifact_source_verification_payload,
    verify_funded_readiness_artifact_sources,
)


def register_funded_readiness_artifact_verify_commands(app: typer.Typer) -> None:
    """Register offline funded-readiness artifact source verification."""

    @app.command("funded-readiness-seal-verify")
    def funded_readiness_seal_verify(
        artifact: Annotated[
            Path,
            typer.Option("--artifact", exists=True, dir_okay=False, readable=True),
        ],
        input_file: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        report: Annotated[
            Path,
            typer.Option("--report", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[str, typer.Option("--output", "-o", help="text or json")] = "text",
    ) -> None:
        """Verify a sealed funded-readiness artifact against exact source files."""

        normalized_output = output.strip().lower()
        if normalized_output not in {"text", "json"}:
            raise typer.BadParameter("output must be text or json")
        try:
            verification = verify_funded_readiness_artifact_sources(
                artifact,
                input_path=input_file,
                report_path=report,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = funded_readiness_artifact_source_verification_payload(verification)
        if normalized_output == "json":
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            mismatched = sorted(
                label
                for label, matches in verification.source_matches.items()
                if not matches
            )
            renamed = sorted(
                label
                for label, matches in verification.source_name_matches.items()
                if not matches
            )
            typer.echo(
                "FUNDED_READINESS_ARTIFACT_VERIFY "
                f"| status={verification.status.value} "
                f"| mismatched={','.join(mismatched) or 'none'} "
                f"| renamed={','.join(renamed) or 'none'} "
                f"| reasons={','.join(verification.reasons) or 'none'}"
            )

        if verification.status is not FundedReadinessArtifactSourceStatus.VERIFIED:
            raise typer.Exit(code=2)
