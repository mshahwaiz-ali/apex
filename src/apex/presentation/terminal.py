"""TTY-aware emission for Apex text reports."""

from __future__ import annotations

import typer


def emit_terminal(text: str) -> None:
    """Print a report with restrained styling when the destination supports color."""

    for line in text.splitlines():
        if line.startswith("╭"):
            typer.secho(line, fg=typer.colors.CYAN, bold=True)
        elif line.startswith("┌─"):
            typer.secho(line, fg=typer.colors.BRIGHT_CYAN, bold=True)
        elif line.startswith("▶"):
            typer.secho(line, fg=typer.colors.BRIGHT_WHITE, bold=True)
        elif line.startswith("!"):
            typer.secho(line, fg=typer.colors.YELLOW, bold=True)
        else:
            typer.echo(line)


__all__ = ["emit_terminal"]
