"""Apex command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex import __version__
from apex.application import bootstrap
from apex.config import load_settings

app = typer.Typer(help="Apex Trading Agent command line interface.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed Apex version."""

    typer.echo(__version__)


@app.command("validate-config")
def validate_config(
    config_dir: Path = typer.Option(Path("config"), exists=True, file_okay=False),  # noqa: B008
) -> None:
    """Validate the default Apex configuration."""

    settings = load_settings(config_dir)
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command()
def smoke() -> None:
    """Run a minimal end-to-end application bootstrap check."""

    context = bootstrap()
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "version": __version__,
                "environment": context.settings.environment,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
