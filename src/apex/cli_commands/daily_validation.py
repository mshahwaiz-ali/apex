"""CLI for persistent daily P1 validation history."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.cli_commands.readiness import _forward_report_from_input, _load_mapping
from apex.paper_trading import PaperTradeStore
from apex.validation.history import (
    DailyValidationRecord,
    DailyValidationStore,
    closed_trades_by_strategy,
    strategy_sample_shortfalls,
)


def register_daily_validation_commands(app: typer.Typer) -> None:
    """Register daily P1 history commands."""

    @app.command("paper-validation-daily")
    def paper_validation_daily(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False),
        paper_store: Path = typer.Option(
            Path("data/paper_trading/trades.json"),
            "--paper-store",
            dir_okay=False,
        ),
        history: Path = typer.Option(
            Path("data/validation/daily.json"),
            "--history",
            dir_okay=False,
        ),
        trading_date: str | None = typer.Option(None, "--date"),
        minimum_per_strategy: int = typer.Option(10, "--minimum-per-strategy", min=1),
    ) -> None:
        """Evaluate one P1 input and persist a date-keyed daily snapshot."""

        try:
            payload = _load_mapping(input_file)
            report = _forward_report_from_input(payload)
            trades = PaperTradeStore(paper_store).load()
            counts = closed_trades_by_strategy(trades)
            record = DailyValidationRecord(
                trading_date=(
                    date.fromisoformat(trading_date)
                    if trading_date is not None
                    else datetime.now(UTC).date()
                ),
                generated_at=datetime.now(UTC),
                report=report,
                closed_trades_by_strategy=counts,
            )
            records = DailyValidationStore(history).upsert(record)
            shortfalls = strategy_sample_shortfalls(
                counts,
                minimum_per_strategy=minimum_per_strategy,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload_out: dict[str, Any] = {
            "schema_version": 1,
            "record": _jsonable(asdict(record)),
            "history_count": len(records),
            "minimum_per_strategy": minimum_per_strategy,
            "strategy_sample_shortfalls": shortfalls,
        }
        typer.echo(json.dumps(payload_out, indent=2, sort_keys=True))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return cast(Any, value)


__all__ = ["register_daily_validation_commands"]
