"""CLI support for sealing history-backed funded-readiness evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.funded.history_readiness_artifact import (
    build_funded_history_readiness_artifact,
    write_funded_history_readiness_artifact,
)


def register_funded_history_readiness_artifact_commands(app: typer.Typer) -> None:
    """Register deterministic history-backed funded-readiness sealing."""

    @app.command("funded-history-readiness-seal")
    def funded_history_readiness_seal(
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
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Seal one aggregate-history-backed funded-readiness review."""

        try:
            artifact = build_funded_history_readiness_artifact(
                input_path=input_file,
                history_review_path=history_review,
                report_path=report,
            )
            write_funded_history_readiness_artifact(output, artifact, force=force)
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FUNDED_HISTORY_READINESS_ARTIFACT_SEALED "
            f"| provider={artifact['provider_name']} "
            f"| ready={str(artifact['ready']).lower()} "
            f"| history_ready={str(artifact['history_ready_for_funded_review']).lower()} "
            f"| artifact_sha256={artifact['artifact_sha256']} "
            f"| output={output}"
        )
