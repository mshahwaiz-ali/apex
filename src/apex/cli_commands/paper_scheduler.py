"""Scheduler-ready spot and futures paper-cycle commands."""

from __future__ import annotations

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


def register_paper_scheduler_commands(app: typer.Typer) -> None:
    """Register dedicated scheduler-safe spot and futures commands."""

    def run_market_cycle(
        *,
        market_type: str,
        timeframe: str,
        candle_limit: int,
        stale_lock_minutes: int,
    ) -> None:
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
            typer.echo(f"PAPER_SCHEDULE_SKIPPED | market={market_type} | reason={exc}")
            raise typer.Exit(code=0) from exc
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        runtime = result.runtime
        typer.echo(
            "PAPER_SCHEDULE_COMPLETED "
            f"| market={market_type} "
            f"| eligible={runtime.cycle.eligible_trade_count} "
            f"| advanced={runtime.cycle.advanced_trade_count} "
            f"| unchanged={runtime.cycle.unchanged_trade_count} "
            f"| provider_failures={len(runtime.provider_failures)} "
            f"| log={result.log_path}"
        )

    @app.command("scheduled-futures")
    def scheduled_futures(
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
    ) -> None:
        """Run one overlap-safe futures paper cycle for cron or systemd."""

        run_market_cycle(
            market_type="futures",
            timeframe=timeframe,
            candle_limit=candle_limit,
            stale_lock_minutes=stale_lock_minutes,
        )

    @app.command("scheduled-spot")
    def scheduled_spot(
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
    ) -> None:
        """Run one overlap-safe spot paper cycle for cron or systemd."""

        run_market_cycle(
            market_type="spot",
            timeframe=timeframe,
            candle_limit=candle_limit,
            stale_lock_minutes=stale_lock_minutes,
        )
