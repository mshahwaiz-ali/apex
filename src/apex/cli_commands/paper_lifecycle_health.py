"""CLI review of lifecycle health from stored paper pipeline audits."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer

from apex.application import bootstrap
from apex.application.paper_lifecycle_health import PaperLifecycleHealthPolicy
from apex.application.paper_lifecycle_health_io import (
    PaperLifecycleHealthAudit,
    build_paper_lifecycle_health_artifact,
    load_latest_paper_lifecycle_health,
    write_paper_lifecycle_health_artifact,
)
from apex.paper_trading.intake import IntakeMarketType


def register_paper_lifecycle_health_command(app: typer.Typer) -> None:
    """Register deterministic lifecycle-health review command."""

    @app.command("lifecycle-health")
    def lifecycle_health(
        market: IntakeMarketType = typer.Option(
            IntakeMarketType.FUTURES,
            "--market",
            case_sensitive=False,
        ),
        minimum_terminal_trades: int = typer.Option(20, "--minimum-terminal-trades", min=1),
        maximum_provider_failure_rate: float = typer.Option(
            0.10,
            "--maximum-provider-failure-rate",
            min=0.0,
            max=1.0,
        ),
        maximum_missing_candle_rate: float = typer.Option(
            0.10,
            "--maximum-missing-candle-rate",
            min=0.0,
            max=1.0,
        ),
        maximum_persistence_failure_rate: float = typer.Option(
            0.02,
            "--maximum-persistence-failure-rate",
            min=0.0,
            max=1.0,
        ),
        maximum_invalidation_rate: float = typer.Option(
            0.25,
            "--maximum-invalidation-rate",
            min=0.0,
            max=1.0,
        ),
        maximum_unfilled_terminal_rate: float = typer.Option(
            0.40,
            "--maximum-unfilled-terminal-rate",
            min=0.0,
            max=1.0,
        ),
        minimum_average_realized_r: float = typer.Option(0.0, "--minimum-average-realized-r"),
        minimum_realized_net_pnl: float = typer.Option(0.0, "--minimum-realized-net-pnl"),
        require_realized_performance: bool = typer.Option(
            True,
            "--require-realized-performance/--allow-missing-realized-performance",
        ),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        force_report: bool = typer.Option(False, "--force-report"),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Evaluate the latest successful scheduled pipeline analytics record."""

        try:
            context = bootstrap()
            audit_path = (
                context.settings.data_dir
                / "paper_trading"
                / "scheduler"
                / "logs"
                / f"pipeline-{market.value}.jsonl"
            )
            policy = PaperLifecycleHealthPolicy(
                minimum_terminal_trades=minimum_terminal_trades,
                maximum_provider_failure_rate=maximum_provider_failure_rate,
                maximum_missing_candle_rate=maximum_missing_candle_rate,
                maximum_persistence_failure_rate=maximum_persistence_failure_rate,
                maximum_invalidation_rate=maximum_invalidation_rate,
                maximum_unfilled_terminal_rate=maximum_unfilled_terminal_rate,
                minimum_average_realized_r=minimum_average_realized_r,
                minimum_realized_net_pnl=minimum_realized_net_pnl,
                require_realized_performance=require_realized_performance,
            )
            audit = load_latest_paper_lifecycle_health(
                audit_path,
                market_type=market,
                policy=policy,
            )
            artifact = build_paper_lifecycle_health_artifact(audit, policy=policy)
            if report is not None:
                write_paper_lifecycle_health_artifact(
                    artifact,
                    report,
                    force=force_report,
                )
        except (FileExistsError, FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        _emit_lifecycle_health(audit, artifact.payload, output)


def paper_lifecycle_health_audit_payload(audit: PaperLifecycleHealthAudit) -> dict[str, Any]:
    """Return a stable JSON-ready legacy audit payload."""

    payload = _jsonable(asdict(audit))
    if not isinstance(payload, dict):
        raise TypeError("paper lifecycle health audit payload must be an object")
    return payload


def _emit_lifecycle_health(
    audit: PaperLifecycleHealthAudit,
    payload: dict[str, Any],
    output: str,
) -> None:
    normalized = output.strip().lower()
    if normalized == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    if normalized != "text":
        raise typer.BadParameter("output must be text or json")

    health = audit.health
    reasons = ",".join(reason.value for reason in health.reasons) or "none"
    typer.echo(
        "PAPER_LIFECYCLE_HEALTH "
        f"| market={audit.market_type.value} "
        f"| status={health.status.value} "
        f"| ready_for_review={str(health.ready_for_forward_viability_review).lower()} "
        f"| terminal_trades={health.terminal_trade_count} "
        f"| sample_shortfall={health.sample_shortfall} "
        f"| provider_failure_rate={health.provider_failure_rate:.4f} "
        f"| missing_candle_rate={health.missing_candle_rate:.4f} "
        f"| invalidation_rate={health.invalidation_rate:.4f} "
        f"| unfilled_terminal_rate={health.unfilled_terminal_rate:.4f} "
        f"| average_r={_optional_float(health.average_realized_r_multiple)} "
        f"| net_pnl={_optional_float(health.realized_net_pnl)} "
        f"| reasons={reasons} "
        f"| run_id={audit.run_id} "
        f"| report_sha256={payload['report_sha256']}"
    )


def _optional_float(value: float | None) -> str:
    return "na" if value is None else f"{value:.4f}"


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
