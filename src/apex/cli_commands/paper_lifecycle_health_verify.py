"""CLI verification for persisted lifecycle-health source evidence."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application.paper_lifecycle_health_verification import (
    PaperLifecycleHealthSourceStatus,
    paper_lifecycle_health_source_verification_payload,
    verify_paper_lifecycle_health_artifact_source,
)


def register_paper_lifecycle_health_verify_command(app: typer.Typer) -> None:
    """Register offline lifecycle-health source verification."""

    @app.command("lifecycle-health-verify")
    def lifecycle_health_verify(
        artifact: Path = typer.Option(
            ...,
            "--artifact",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        source_log: Path = typer.Option(
            ...,
            "--source-log",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Verify a lifecycle-health artifact against its scheduler source log."""

        normalized_output = _normalize_output(output)
        try:
            verification = verify_paper_lifecycle_health_artifact_source(
                artifact,
                source_log,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = paper_lifecycle_health_source_verification_payload(verification)
        if normalized_output == "json":
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            reasons = ",".join(verification.reasons) or "none"
            typer.echo(
                "PAPER_LIFECYCLE_HEALTH_VERIFY "
                f"| status={verification.status.value} "
                f"| run_id={verification.run_id} "
                f"| market={verification.market_type} "
                f"| line={verification.source_line_number} "
                f"| source_record_matches={str(verification.source_record_matches).lower()} "
                f"| source_log_matches={str(verification.source_log_matches).lower()} "
                f"| analytics_matches={str(verification.analytics_matches).lower()} "
                f"| reasons={reasons}"
            )

        if verification.status is not PaperLifecycleHealthSourceStatus.VERIFIED:
            raise typer.Exit(code=2)


def _normalize_output(output: str) -> str:
    normalized = output.strip().lower()
    if normalized not in {"text", "json"}:
        raise typer.BadParameter("output must be text or json")
    return normalized
