"""CLI verification for sealed history-backed funded-readiness artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.funded.history_readiness_artifact_verification import (
    FundedHistoryReadinessArtifactSourceStatus,
    funded_history_readiness_artifact_source_verification_payload,
    verify_funded_history_readiness_artifact_sources,
)


def register_funded_history_readiness_artifact_verify_commands(app: typer.Typer) -> None:
    """Register offline verification for history-backed readiness artifacts."""

    @app.command("funded-history-readiness-seal-verify")
    def funded_history_readiness_seal_verify(
        artifact: Annotated[
            Path,
            typer.Option("--artifact", exists=True, dir_okay=False, readable=True),
        ],
        input_file: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        history_review: Annotated[
            Path,
            typer.Option("--history-review", exists=True, dir_okay=False, readable=True),
        ],
        report: Annotated[
            Path,
            typer.Option("--report", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[str, typer.Option("--output", "-o", help="text or json")] = "text",
    ) -> None:
        """Verify a sealed history-backed readiness artifact against exact sources."""

        normalized_output = output.strip().lower()
        if normalized_output not in {"text", "json"}:
            raise typer.BadParameter("output must be text or json")
        try:
            verification = verify_funded_history_readiness_artifact_sources(
                artifact,
                input_path=input_file,
                history_review_path=history_review,
                report_path=report,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = funded_history_readiness_artifact_source_verification_payload(verification)
        if normalized_output == "json":
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            mismatched = sorted(
                label for label, matches in verification.source_matches.items() if not matches
            )
            renamed = sorted(
                label
                for label, matches in verification.source_name_matches.items()
                if not matches
            )
            typer.echo(
                "FUNDED_HISTORY_READINESS_ARTIFACT_VERIFY "
                f"| status={verification.status.value} "
                f"| mismatched={','.join(mismatched) or 'none'} "
                f"| renamed={','.join(renamed) or 'none'} "
                f"| reasons={','.join(verification.reasons) or 'none'}"
            )

        if verification.status is not FundedHistoryReadinessArtifactSourceStatus.VERIFIED:
            raise typer.Exit(code=2)
