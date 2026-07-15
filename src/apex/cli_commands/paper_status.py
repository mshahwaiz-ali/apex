"""CLI status inspection for sustained P1 paper validation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

import typer

from apex.application import bootstrap
from apex.paper_trading import PaperOperationsStatus, build_paper_operations_status


def register_paper_status_command(app: typer.Typer) -> None:
    """Register the sustained paper-operations status command."""

    @app.command("operations-status")
    def operations_status(
        maximum_run_age_minutes: int = typer.Option(15, "--maximum-run-age-minutes", min=1),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Inspect cycle, intake, pipeline freshness, locks, samples, and reports."""

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

        _emit_status(status, output)


def paper_operations_status_payload(status: PaperOperationsStatus) -> dict[str, Any]:
    """Return a JSON-ready operations status payload."""

    payload = _jsonable(asdict(status))
    if not isinstance(payload, dict):
        raise TypeError("paper operations status payload must be an object")
    payload["scheduler_ready"] = status.scheduler_ready
    payload["operations_ready"] = status.operations_ready
    return payload


def _emit_status(status: PaperOperationsStatus, output: str) -> None:
    normalized = output.strip().lower()
    payload = paper_operations_status_payload(status)
    if normalized == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    if normalized != "text":
        raise typer.BadParameter("output must be text or json")

    typer.echo(
        "PAPER_OPERATIONS_STATUS "
        f"| operations_ready={str(status.operations_ready).lower()} "
        f"| scheduler_ready={str(status.scheduler_ready).lower()} "
        f"| trades={status.total_trade_count} "
        f"| daily_reports={status.daily_report_count} "
        f"| reviews={status.review_report_count}"
    )
    for market in status.markets:
        typer.echo(
            f"- {market.market_type.upper()} "
            f"| ready={str(market.operationally_ready).lower()} "
            f"| cycle_fresh={str(market.scheduler_fresh).lower()} "
            f"| intake_fresh={str(market.intake_fresh).lower()} "
            f"| pipeline_fresh={str(market.pipeline_fresh).lower()} "
            f"| cycle_lock_stale={str(market.lock_stale).lower()} "
            f"| intake_lock_stale={str(market.intake_lock_stale).lower()} "
            f"| pipeline_lock_stale={str(market.pipeline_lock_stale).lower()} "
            f"| open={market.open_trade_count} "
            f"| closed={market.closed_trade_count} "
            f"| provider_failures={market.latest_provider_failure_count}"
        )


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
