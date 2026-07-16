"""CLI status inspection for sustained paper validation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

import typer

from apex.application import bootstrap
from apex.paper_trading import PaperOperationsStatus, build_paper_operations_status
from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.paper import render_paper_status


def register_paper_status_command(app: typer.Typer) -> None:
    """Register the sustained paper-operations status command."""

    @app.command("operations-status")
    def operations_status(
        maximum_run_age_minutes: int = typer.Option(15, "--maximum-run-age-minutes", min=1),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy text or json output selector.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Inspect cycle, intake, pipeline freshness, failures, locks, and reports."""

        try:
            context = bootstrap()
            status = build_paper_operations_status(
                data_dir=context.settings.data_dir,
                generated_at=datetime.now(UTC),
                maximum_run_age=timedelta(minutes=maximum_run_age_minutes),
                stale_lock_after=timedelta(minutes=stale_lock_minutes),
            )
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        _emit_status(status, format_ or output)


def paper_operations_status_payload(status: PaperOperationsStatus) -> dict[str, Any]:
    """Return a JSON-ready operations status payload."""

    payload = _jsonable(asdict(status))
    if not isinstance(payload, dict):
        raise TypeError("paper operations status payload must be an object")
    payload["scheduler_ready"] = status.scheduler_ready
    payload["operations_ready"] = status.operations_ready
    return payload


def _emit_status(status: PaperOperationsStatus, mode: str) -> None:
    payload = paper_operations_status_payload(status)
    try:
        output_mode = normalize_output_mode(mode)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(render_paper_status(payload, mode=output_mode))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value
