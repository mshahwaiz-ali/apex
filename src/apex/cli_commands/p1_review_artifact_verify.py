"""CLI verification for sealed P1 review evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.paper_trading.p1_review_artifact_verification import (
    P1ReviewArtifactSourceStatus,
    p1_review_artifact_source_verification_payload,
    verify_p1_review_artifact_sources,
)


def register_p1_review_artifact_verify_commands(app: typer.Typer) -> None:
    """Register offline P1 review artifact source verification."""

    @app.command("p1-review-seal-verify")
    def p1_review_seal_verify(
        artifact: Annotated[
            Path,
            typer.Option("--artifact", exists=True, dir_okay=False, readable=True),
        ],
        review_report: Annotated[
            Path,
            typer.Option("--review-report", exists=True, dir_okay=False, readable=True),
        ],
        historical_profile: Annotated[
            Path,
            typer.Option("--historical-profile", exists=True, dir_okay=False, readable=True),
        ],
        forward_profile: Annotated[
            Path,
            typer.Option("--forward-profile", exists=True, dir_okay=False, readable=True),
        ],
        daily_report: Annotated[
            Path,
            typer.Option("--daily-report", exists=True, dir_okay=False, readable=True),
        ],
        paper_store: Annotated[
            Path,
            typer.Option("--paper-store", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[str, typer.Option("--output", "-o", help="text or json")] = "text",
    ) -> None:
        """Verify a sealed P1 review artifact against all exact source files."""

        normalized_output = output.strip().lower()
        if normalized_output not in {"text", "json"}:
            raise typer.BadParameter("output must be text or json")
        try:
            verification = verify_p1_review_artifact_sources(
                artifact,
                review_report_path=review_report,
                historical_profile_path=historical_profile,
                forward_profile_path=forward_profile,
                daily_report_path=daily_report,
                paper_store_path=paper_store,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = p1_review_artifact_source_verification_payload(verification)
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
                "P1_REVIEW_ARTIFACT_VERIFY "
                f"| status={verification.status.value} "
                f"| mismatched={','.join(mismatched) or 'none'} "
                f"| renamed={','.join(renamed) or 'none'} "
                f"| reasons={','.join(verification.reasons) or 'none'}"
            )

        if verification.status is not P1ReviewArtifactSourceStatus.VERIFIED:
            raise typer.Exit(code=2)
