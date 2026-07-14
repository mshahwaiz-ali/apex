"""CLI for aggregate P1 validation-history review."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.validation.aggregate import AggregateHistoryThresholds, evaluate_aggregate_history
from apex.validation.history import DailyValidationStore


def register_history_review_commands(app: typer.Typer) -> None:
    """Register aggregate validation-history commands."""

    @app.command("paper-validation-history-review")
    def paper_validation_history_review(
        history: Path = typer.Option(
            Path("data/validation/daily.json"),
            "--history",
            exists=True,
            dir_okay=False,
        ),
        report: Path = typer.Option(
            Path("data/validation/history-review.json"),
            "--report",
            dir_okay=False,
        ),
        minimum_validation_days: int = typer.Option(10, min=1),
        minimum_total_samples: int = typer.Option(30, min=1),
        minimum_samples_per_strategy: int = typer.Option(10, min=1),
        minimum_consecutive_failure_free_days: int = typer.Option(5, min=1),
        minimum_ready_day_ratio: float = typer.Option(0.80, min=0.0, max=1.0),
        maximum_win_rate_deterioration: float = typer.Option(0.05, min=0.0),
        maximum_expectancy_deterioration: float = typer.Option(0.10, min=0.0),
        maximum_drawdown_deterioration: float = typer.Option(0.05, min=0.0),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Review accumulated daily P1 records and persist the canonical aggregate report."""

        try:
            thresholds = AggregateHistoryThresholds(
                minimum_validation_days=minimum_validation_days,
                minimum_total_samples=minimum_total_samples,
                minimum_samples_per_strategy=minimum_samples_per_strategy,
                minimum_consecutive_failure_free_days=minimum_consecutive_failure_free_days,
                minimum_ready_day_ratio=minimum_ready_day_ratio,
                maximum_win_rate_deterioration=maximum_win_rate_deterioration,
                maximum_expectancy_deterioration=maximum_expectancy_deterioration,
                maximum_drawdown_deterioration=maximum_drawdown_deterioration,
            )
            result = evaluate_aggregate_history(
                DailyValidationStore(history).load(),
                thresholds=thresholds,
                generated_at=datetime.now(UTC),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        serialized = _serialize(result)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if output == "json":
            typer.echo(json.dumps(serialized, indent=2, sort_keys=True))
            return
        reasons = ",".join(str(reason) for reason in serialized["reasons"]) or "none"
        typer.echo(
            "PAPER_VALIDATION_HISTORY | "
            f"ready={str(serialized['ready_for_funded_review']).lower()} "
            f"| days={serialized['validation_days']} | samples={serialized['total_samples']} "
            f"| reasons={reasons}"
        )


def _serialize(value: object) -> dict[str, Any]:
    payload = json.loads(json.dumps(asdict(value), default=str))
    if not isinstance(payload, dict):
        raise TypeError("aggregate report serialization must produce an object")
    return cast(dict[str, Any], payload)


__all__ = ["register_history_review_commands"]
