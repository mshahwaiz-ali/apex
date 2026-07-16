"""Operational CLI for the combined forward-paper review artifact."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.backtesting import EvidenceQuality, HistoricalEdgeProfile
from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.paper_progress import render_operational_review
from apex.paper_trading import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationResult,
    ForwardPaperValidationStatus,
    PaperTradeStore,
    audit_paper_trade_lifecycle,
    build_forward_paper_review_report,
    compare_historical_to_forward,
    load_and_verify_forward_paper_daily_report,
    write_forward_paper_review_report,
)


@dataclass(frozen=True, slots=True)
class _ValidationStatusOnly:
    status: ForwardPaperValidationStatus


def register_p1_review_command(app: typer.Typer) -> None:
    """Register the combined operational paper review command."""

    @app.command("p1-review")
    def p1_review(
        historical_profile: Path = typer.Option(
            ...,
            "--historical-profile",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        forward_profile: Path = typer.Option(
            ...,
            "--forward-profile",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        daily_report: Path = typer.Option(
            ...,
            "--daily-report",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        paper_store: Path = typer.Option(
            ...,
            "--paper-store",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        output: Path = typer.Option(..., "--output", dir_okay=False),
        historical_period_days: int = typer.Option(..., "--historical-period-days", min=1),
        forward_period_days: int = typer.Option(..., "--forward-period-days", min=1),
        maximum_holding_candles: int = typer.Option(240, "--maximum-holding-candles", min=1),
        validation_status: str = typer.Option(
            ForwardPaperValidationStatus.INSUFFICIENT_SAMPLE.value,
            "--validation-status",
        ),
        minimum_closed_trades: int = typer.Option(100, "--minimum-closed-trades", min=1),
        manual_execution_usable: bool = typer.Option(False, "--manual-execution-usable"),
        force: bool = typer.Option(False, "--force"),
        format_: str = typer.Option(
            OutputMode.TEXT.value,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Build a hash-verified operational review from persisted evidence."""

        try:
            historical = load_historical_edge_profile(historical_profile)
            forward = load_forward_edge_profile(forward_profile)
            daily = load_and_verify_forward_paper_daily_report(daily_report)
            trades = PaperTradeStore(paper_store).load()
            deviation = compare_historical_to_forward(
                historical,
                forward,
                historical_period_days=historical_period_days,
                forward_period_days=forward_period_days,
            )
            audit = audit_paper_trade_lifecycle(
                trades,
                maximum_holding_candles=maximum_holding_candles,
            )
            status = ForwardPaperValidationStatus(validation_status)
            validation = cast(
                ForwardPaperValidationResult,
                _ValidationStatusOnly(status=status),
            )
            review = build_forward_paper_review_report(
                generated_at=datetime.now(UTC),
                daily_report_sha256=daily.report_sha256,
                forward_validation=validation,
                deviation=deviation,
                lifecycle_audit=audit,
                sample_sufficient=forward.sample_size >= minimum_closed_trades,
                manual_execution_usable=manual_execution_usable,
            )
            write_forward_paper_review_report(review, output, force=force)
            mode = normalize_output_mode(format_)
        except (
            FileExistsError,
            FileNotFoundError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise typer.BadParameter(str(exc)) from exc

        if mode is OutputMode.JSON:
            typer.echo(json.dumps(review.payload, indent=2, sort_keys=True, default=str))
            return

        typer.echo(
            render_operational_review(
                review.payload,
                output_path=output,
                anomaly_count=len(audit.anomalies),
                mode=mode,
            )
        )


def load_historical_edge_profile(path: Path) -> HistoricalEdgeProfile:
    """Load one explicit historical edge profile JSON object."""

    payload = _load_object(path)
    return HistoricalEdgeProfile(
        dimensions=_string_mapping(payload["dimensions"]),
        sample_size=int(payload["sample_size"]),
        win_rate=float(payload["win_rate"]),
        loss_rate=float(payload["loss_rate"]),
        breakeven_rate=float(payload["breakeven_rate"]),
        average_r=float(payload["average_r"]),
        median_r=float(payload["median_r"]),
        expectancy=float(payload["expectancy"]),
        profit_factor=_optional_float(payload.get("profit_factor")),
        maximum_drawdown_r=float(payload["maximum_drawdown_r"]),
        maximum_losing_streak=int(payload["maximum_losing_streak"]),
        average_holding_candles=float(payload["average_holding_candles"]),
        average_execution_cost_r=float(payload["average_execution_cost_r"]),
        evidence_quality=EvidenceQuality(str(payload["evidence_quality"])),
    )


def load_forward_edge_profile(path: Path) -> ForwardPaperEdgeProfile:
    """Load one explicit forward-paper edge profile JSON object."""

    payload = _load_object(path)
    return ForwardPaperEdgeProfile(
        dimensions=_string_mapping(payload["dimensions"]),
        sample_size=int(payload["sample_size"]),
        win_rate=float(payload["win_rate"]),
        expectancy=float(payload["expectancy"]),
        profit_factor=_optional_float(payload.get("profit_factor")),
        maximum_drawdown_r=float(payload["maximum_drawdown_r"]),
    )


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"profile must be a JSON object: {path}")
    return cast(dict[str, Any], value)


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("dimensions must be a JSON object")
    return {str(key): str(item) for key, item in value.items()}


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("optional numeric value must be a number, numeric string, or null")
    return float(value)
