"""CLI support for sealing funded-readiness evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.funded.readiness_artifact import (
    build_funded_readiness_artifact,
    write_funded_readiness_artifact,
)


def register_funded_readiness_artifact_commands(app: typer.Typer) -> None:
    """Register deterministic funded-readiness artifact sealing."""

    @app.command("funded-readiness-seal")
    def funded_readiness_seal(
        input_file: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        report: Annotated[
            Path,
            typer.Option("--report", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Seal one funded-readiness input and its emitted report."""

        try:
            artifact = build_funded_readiness_artifact(
                input_path=input_file,
                report_path=report,
            )
            write_funded_readiness_artifact(output, artifact, force=force)
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FUNDED_READINESS_ARTIFACT_SEALED "
            f"| provider={artifact['provider_name']} "
            f"| ready={str(artifact['ready']).lower()} "
            f"| artifact_sha256={artifact['artifact_sha256']} "
            f"| output={output}"
        )
