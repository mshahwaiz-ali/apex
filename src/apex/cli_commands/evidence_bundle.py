"""CLI inspection for canonical setup evidence bundles."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer

from apex.validation.evidence_bundle import load_evidence_bundle


def register_evidence_bundle_commands(app: typer.Typer) -> None:
    """Register N4.11 artifact-to-approval evidence inspection."""

    @app.command("evidence-bundle-inspect")
    def evidence_bundle_inspect(
        historical_validation: Annotated[
            Path,
            typer.Option("--historical-validation", exists=True, dir_okay=False, readable=True),
        ],
        dimensions_file: Annotated[
            Path,
            typer.Option("--dimensions", exists=True, dir_okay=False, readable=True),
        ],
        forward_validation: Annotated[
            Path | None,
            typer.Option("--forward-validation", exists=True, dir_okay=False, readable=True),
        ] = None,
        maximum_age_days: Annotated[
            int | None,
            typer.Option("--maximum-age-days", min=1),
        ] = None,
        output: Annotated[
            Path | None,
            typer.Option("--output", dir_okay=False),
        ] = None,
    ) -> None:
        """Resolve one exact setup segment into protocol-compatible evidence views."""

        try:
            dimensions = _load_dimensions(dimensions_file)
            bundle = load_evidence_bundle(
                historical_validation_path=historical_validation,
                forward_validation_path=forward_validation,
                dimensions=dimensions,
                as_of=datetime.now(UTC),
                maximum_age=(
                    timedelta(days=maximum_age_days)
                    if maximum_age_days is not None
                    else None
                ),
            )
            payload = bundle.to_payload()
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _load_dimensions(path: Path) -> dict[str, str]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("evidence dimensions file must contain a non-empty string mapping")
    return dict(value)
