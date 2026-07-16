"""Scheduler-ready spot and futures paper-cycle commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from apex.application import bootstrap, create_market_data_services
from apex.paper_trading import (
    PaperCycleAlreadyRunningError,
    PaperTradeConfig,
    PaperTradeStore,
    run_scheduled_paper_cycle,
)
from apex.presentation import (
    OutputMode,
    normalize_output_mode,
    render_fields,
    render_section,
    render_title,
)


def register_paper_scheduler_commands(app: typer.Typer) -> None:
    """Register dedicated scheduler-safe spot and futures commands."""

    def run_market_cycle(
        *,
        market_type: str,
        timeframe: str,
        candle_limit: int,
        stale_lock_minutes: int,
        format_: str,
    ) -> None:
        try:
            output_mode = normalize_output_mode(format_)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            base = context.settings.data_dir / "paper_trading" / "scheduler"
            store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
            with create_market_data_services(context.settings) as services:
                result = run_scheduled_paper_cycle(
                    store=store,
                    provider=services.candles,
                    market_type=market_type,
                    timeframe=timeframe,
                    candle_limit=candle_limit,
                    lock_path=base / "locks" / f"{market_type}.lock",
                    log_path=base / "logs" / f"{market_type}.jsonl",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    stale_lock_after=timedelta(minutes=stale_lock_minutes),
                    config=PaperTradeConfig(),
                )
        except PaperCycleAlreadyRunningError as exc:
            payload: dict[str, object] = {
                "market_type": market_type,
                "outcome": "skipped",
                "reason": str(exc),
            }
            _emit_scheduler(payload, output_mode)
            raise typer.Exit(code=0) from exc
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        runtime = result.runtime
        payload: dict[str, object] = {
            "market_type": market_type,
            "outcome": "completed",
            "eligible_trade_count": runtime.cycle.eligible_trade_count,
            "advanced_trade_count": runtime.cycle.advanced_trade_count,
            "unchanged_trade_count": runtime.cycle.unchanged_trade_count,
            "provider_failure_count": len(runtime.provider_failures),
            "provider_failures": [
                {"symbol": symbol, "reason": reason}
                for symbol, reason in runtime.provider_failures
            ],
            "log_path": str(result.log_path),
        }
        _emit_scheduler(payload, output_mode)

    @app.command("scheduled-futures")
    def scheduled_futures(
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        format_: str = typer.Option(
            "text",
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Run one overlap-safe futures paper cycle for cron or systemd."""

        run_market_cycle(
            market_type="futures",
            timeframe=timeframe,
            candle_limit=candle_limit,
            stale_lock_minutes=stale_lock_minutes,
            format_=format_,
        )

    @app.command("scheduled-spot")
    def scheduled_spot(
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        format_: str = typer.Option(
            "text",
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Run one overlap-safe spot paper cycle for cron or systemd."""

        run_market_cycle(
            market_type="spot",
            timeframe=timeframe,
            candle_limit=candle_limit,
            stale_lock_minutes=stale_lock_minutes,
            format_=format_,
        )


def _emit_scheduler(payload: dict[str, object], output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    completed = payload.get("outcome") == "completed"
    sections = [
        render_title("Paper Trading Scheduler"),
        render_section(
            "Run status",
            render_fields(
                (
                    ("Market", str(payload.get("market_type", "Unavailable")).title()),
                    ("Outcome", str(payload.get("outcome", "Unavailable")).title()),
                    ("Eligible trades", payload.get("eligible_trade_count")),
                    ("Advanced trades", payload.get("advanced_trade_count")),
                    ("Unchanged trades", payload.get("unchanged_trade_count")),
                    ("Provider failures", payload.get("provider_failure_count")),
                )
            ),
        ),
        render_section(
            "Next action",
            (
                "Review lifecycle changes and continue scheduled collection."
                if completed
                else f"No cycle ran: {payload.get('reason', 'scheduler lock is active')}."
            ),
        ),
    ]
    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(
            render_section(
                "Scheduler diagnostics",
                render_fields((("Log path", payload.get("log_path")),)),
            )
        )
    if output_mode is OutputMode.DEBUG:
        sections.append(
            render_section(
                "Deterministic payload summary",
                render_fields(
                    (
                        ("Top-level keys", ", ".join(sorted(payload))),
                        ("Payload field count", len(payload)),
                    )
                ),
            )
        )
    typer.echo("\n\n".join(sections))
