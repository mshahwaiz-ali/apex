"""CLI generation of P1 review inputs from stored paper trades."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.paper_trading import PaperTradeStore
from apex.validation.evidence import generate_paper_evidence


def register_validation_evidence_commands(app: typer.Typer) -> None:
    """Register evidence-generation commands for forward validation."""

    @app.command("paper-validation-generate")
    def paper_validation_generate(
        backtest_report: Path = typer.Argument(..., exists=True, dir_okay=False),
        paper_store: Path = typer.Option(
            Path("data/paper_trading/trades.json"),
            "--paper-store",
            dir_okay=False,
        ),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        critical_risk_control_failures: int = typer.Option(
            0, "--critical-risk-control-failures", min=0
        ),
        manual_instruction_failures: int = typer.Option(
            0, "--manual-instruction-failures", min=0
        ),
    ) -> None:
        """Build a P1 review input from saved backtest and paper records."""

        try:
            backtest = _load_backtest_metrics(backtest_report)
            evidence = generate_paper_evidence(PaperTradeStore(paper_store).load())
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = {
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
        }
        if report is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _load_backtest_metrics(path: Path) -> dict[str, int | float]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("backtest report must be a JSON object")
    payload = cast(dict[str, Any], value)
    report_value = payload.get("report", payload)
    if not isinstance(report_value, dict):
        raise TypeError("backtest report payload must be an object")
    report = cast(dict[str, Any], report_value)
    return {
        "total_trades": int(report["total_trades"]),
        "win_rate": float(report["win_rate"]),
        "expectancy": float(report["expectancy"]),
        "maximum_drawdown": float(report["maximum_drawdown"]),
    }


__all__ = ["register_validation_evidence_commands"]
