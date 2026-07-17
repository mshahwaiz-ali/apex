"""Provider-backed paper-operation CLI command."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import typer

from apex.application import bootstrap, create_market_data_services
from apex.paper_trading import (
    PaperRuntimeResult,
    PaperTradeConfig,
    PaperTradeStore,
    run_provider_backed_paper_cycle,
    write_paper_operation_cycle_result,
)
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.paper import render_paper_cycle


def register_paper_cycle_command(app: typer.Typer) -> None:
    """Register the provider-backed spot/futures paper cycle command."""

    @app.command("cycle")
    def paper_cycle(
        market_type: str = typer.Option(
            "futures",
            "--market-type",
            help="Paper market to advance. Only futures is currently active.",
        ),
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        report_date: str | None = typer.Option(
            None,
            "--report-date",
            help="Optional ISO date for the deterministic daily report.",
        ),
        daily_report: Path | None = typer.Option(
            None,
            "--daily-report",
            dir_okay=False,
            help="Optional daily forward-paper report path.",
        ),
        cycle_report: Path | None = typer.Option(
            None,
            "--cycle-report",
            dir_okay=False,
            help="Optional operational cycle summary path.",
        ),
        force: bool = typer.Option(False, "--force", help="Allow report overwrite."),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy text or json output selector.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text or json.",
        ),
    ) -> None:
        """Fetch closed candles and advance one deterministic paper cycle."""

        normalized_market = market_type.strip().lower()
        if normalized_market != "futures":
            raise typer.BadParameter("market-type must be futures")
        parsed_report_date = _parse_report_date(report_date)
        if daily_report is not None and parsed_report_date is None:
            raise typer.BadParameter("--daily-report requires --report-date")

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
            with create_market_data_services(context.settings) as services:
                result = run_provider_backed_paper_cycle(
                    store=store,
                    provider=services.candles,
                    market_type=normalized_market,
                    timeframe=timeframe,
                    candle_limit=candle_limit,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    config=PaperTradeConfig(),
                    daily_report_date=parsed_report_date,
                    daily_report_path=daily_report,
                    force_report=force,
                )
            if cycle_report is not None:
                write_paper_operation_cycle_result(result.cycle, cycle_report, force=force)
        except (FileExistsError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = paper_runtime_payload(result)
        if cycle_report is not None:
            payload["cycle_report_path"] = str(cycle_report)
        if daily_report is not None:
            payload["daily_report_path"] = str(daily_report)
        _emit_result(payload, format_ or output)


def paper_runtime_payload(result: PaperRuntimeResult) -> dict[str, Any]:
    """Return a JSON-ready deterministic runtime summary."""

    return {
        "cycle": _jsonable(asdict(result.cycle)),
        "requested_symbols": list(result.requested_symbols),
        "successful_symbols": list(result.successful_symbols),
        "provider_failures": [
            {"symbol": symbol, "reason": reason} for symbol, reason in result.provider_failures
        ],
        "fully_collected": result.fully_collected,
    }


def _parse_report_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("report-date must use YYYY-MM-DD") from exc


def _emit_result(payload: dict[str, Any], mode: str) -> None:
    try:
        output_mode = normalize_cli_output_mode(mode)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(render_paper_cycle(payload, mode=output_mode))


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
