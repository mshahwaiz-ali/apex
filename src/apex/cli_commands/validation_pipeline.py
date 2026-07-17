"""Integrated validation generation/review and funded-readiness commands."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.cli_commands.readiness import _forward_report_from_input, _funded_report_from_input
from apex.cli_commands.validation_evidence import _load_backtest_metrics
from apex.paper_trading import PaperTradeStore
from apex.validation.evidence import generate_paper_evidence
from apex.validation.history import (
    DailyValidationRecord,
    DailyValidationStore,
    closed_trades_by_strategy,
    strategy_sample_shortfalls,
)


def register_validation_pipeline_commands(app: typer.Typer) -> None:
    """Register end-to-end validation and report-backed funded-readiness commands."""

    @app.command("paper-validation-run")
    def paper_validation_run(
        backtest_report: Path = typer.Argument(..., exists=True, dir_okay=False),
        paper_store: Path = typer.Option(
            Path("data/paper_trading/trades.json"),
            "--paper-store",
            dir_okay=False,
        ),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        history: Path = typer.Option(
            Path("data/validation/daily.json"),
            "--history",
            dir_okay=False,
            help="Persistent date-keyed P1 validation history.",
        ),
        trading_date: str | None = typer.Option(
            None,
            "--date",
            help="Validation trading date in YYYY-MM-DD format; defaults to UTC today.",
        ),
        minimum_per_strategy: int = typer.Option(
            10,
            "--minimum-per-strategy",
            min=1,
            help="Minimum closed samples required for each observed strategy.",
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        minimum_closed_trades: int = typer.Option(30, "--minimum-closed-trades", min=1),
        maximum_win_rate_deviation: float = typer.Option(
            0.15, "--maximum-win-rate-deviation", min=0.0
        ),
        maximum_expectancy_deviation: float = typer.Option(
            0.50, "--maximum-expectancy-deviation", min=0.0
        ),
        maximum_drawdown_increase: float = typer.Option(
            0.25, "--maximum-drawdown-increase", min=0.0
        ),
        critical_risk_control_failures: int = typer.Option(
            0, "--critical-risk-control-failures", min=0
        ),
        manual_instruction_failures: int = typer.Option(0, "--manual-instruction-failures", min=0),
    ) -> None:
        """Generate, evaluate, and persist one auditable daily validation snapshot."""

        try:
            trades = PaperTradeStore(paper_store).load()
            backtest = _load_backtest_metrics(backtest_report)
            evidence = generate_paper_evidence(trades)
            payload: dict[str, Any] = {
                "generated_at": datetime.now(UTC).isoformat(),
                "backtest": backtest,
                "paper": {
                    "closed_trades": evidence.closed_trades,
                    "win_rate": evidence.win_rate,
                },
                "evidence": {
                    "critical_lifecycle_failures": evidence.critical_lifecycle_failures,
                    "critical_risk_control_failures": critical_risk_control_failures,
                    "manual_instruction_failures": manual_instruction_failures,
                    "paper_expectancy": evidence.paper_expectancy,
                    "paper_maximum_drawdown": evidence.paper_maximum_drawdown,
                },
                "thresholds": {
                    "minimum_closed_trades": minimum_closed_trades,
                    "maximum_win_rate_deviation": maximum_win_rate_deviation,
                    "maximum_expectancy_deviation": maximum_expectancy_deviation,
                    "maximum_drawdown_increase": maximum_drawdown_increase,
                },
            }
            result = _forward_report_from_input(payload)
            counts = closed_trades_by_strategy(trades)
            record = DailyValidationRecord(
                trading_date=(
                    date.fromisoformat(trading_date)
                    if trading_date is not None
                    else datetime.now(UTC).date()
                ),
                generated_at=datetime.now(UTC),
                report=result,
                closed_trades_by_strategy=counts,
            )
            records = DailyValidationStore(history).upsert(record)
            shortfalls = strategy_sample_shortfalls(
                counts,
                minimum_per_strategy=minimum_per_strategy,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        serialized = _jsonable_report(result)
        _write_json(report, serialized)
        if output == "json":
            typer.echo(
                json.dumps(
                    {
                        "report": serialized,
                        "daily_history": {
                            "trading_date": record.trading_date.isoformat(),
                            "history_count": len(records),
                            "minimum_per_strategy": minimum_per_strategy,
                            "strategy_sample_shortfalls": shortfalls,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return
        reasons = ",".join(str(reason) for reason in serialized["reasons"]) or "none"
        typer.echo(
            f"PAPER_VALIDATION | eligibility={serialized['eligibility']} "
            f"| closed={serialized['closed_paper_trades']} "
            f"| modeled={serialized['modeled_trades']} | reasons={reasons} "
            f"| history_days={len(records)} "
            f"| strategy_shortfalls={len(shortfalls)}"
        )

    @app.command("funded-readiness-from-report")
    def funded_readiness_from_report(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False),
        forward_validation_report: Path = typer.Option(
            ...,
            "--forward-validation-report",
            exists=True,
            dir_okay=False,
        ),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Evaluate funded readiness using a separately persisted canonical validation report."""

        try:
            payload = _load_mapping(input_file)
            payload["forward_validation"] = _load_mapping(forward_validation_report)
            result = _funded_report_from_input(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        serialized = _jsonable_report(result)
        _write_json(report, serialized)
        if output == "json":
            typer.echo(json.dumps(serialized, indent=2, sort_keys=True))
            return
        reasons = ",".join(str(reason) for reason in serialized["reasons"]) or "none"
        typer.echo(
            f"FUNDED_READINESS | ready={str(serialized['ready']).lower()} "
            f"| provider={serialized['provider_name']} | reasons={reasons}"
        )


def _load_mapping(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("input document must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonable_report(value: object) -> dict[str, Any]:
    payload = json.loads(json.dumps(asdict(cast(Any, value)), default=str))
    if not isinstance(payload, dict):
        raise TypeError("report serialization must produce an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = ["register_validation_pipeline_commands"]
