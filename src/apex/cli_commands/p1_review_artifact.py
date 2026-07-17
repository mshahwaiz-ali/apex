"""CLI support for sealing forward-validation review evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.paper_trading.p1_review_artifact import (
    build_p1_review_artifact,
    write_p1_review_artifact,
)


def register_p1_review_artifact_commands(app: typer.Typer) -> None:
    """Register deterministic forward-validation review artifact sealing."""

    @app.command("p1-review-seal")
    def p1_review_seal(
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
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Seal one forward-validation review and all exact source evidence files."""

        try:
            artifact = build_p1_review_artifact(
                review_report_path=review_report,
                historical_profile_path=historical_profile,
                forward_profile_path=forward_profile,
                daily_report_path=daily_report,
                paper_store_path=paper_store,
            )
            write_p1_review_artifact(output, artifact, force=force)
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "P1_REVIEW_ARTIFACT_SEALED "
            f"| review_state={artifact['review_state']} "
            f"| artifact_sha256={artifact['artifact_sha256']} "
            f"| output={output}"
        )
