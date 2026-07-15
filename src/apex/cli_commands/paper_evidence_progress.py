"""CLI reporting for P1 forward-paper sample progress."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from apex.application import bootstrap
from apex.paper_trading.evidence_progress import build_forward_evidence_progress
from apex.paper_trading.store import PaperTradeStore


def register_paper_evidence_progress_command(app: typer.Typer) -> None:
    """Register the forward-paper evidence progress command."""

    @app.command("evidence-progress")
    def evidence_progress(
        minimum_closed_trades: int = typer.Option(100, "--minimum-closed-trades", min=1),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        context = bootstrap()
        store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
        progress = build_forward_evidence_progress(
            store.load(),
            minimum_closed_trades=minimum_closed_trades,
        )
        normalized = output.strip().lower()
        if normalized == "json":
            payload = asdict(progress)
            payload["all_segments_sufficient"] = progress.all_segments_sufficient
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return
        if normalized != "text":
            raise typer.BadParameter("output must be text or json")
        typer.echo(
            "PAPER_EVIDENCE_PROGRESS "
            f"| closed={progress.total_closed_trades} "
            f"| segments={len(progress.segments)} "
            f"| all_sufficient={str(progress.all_segments_sufficient).lower()}"
        )
        for segment in progress.segments:
            label = ",".join(f"{key}={value}" for key, value in segment.dimensions.items())
            typer.echo(
                f"- {label} | closed={segment.closed_trade_count} "
                f"| remaining={segment.remaining_closed_trades} "
                f"| expectancy_r={segment.expectancy_r:.4f} "
                f"| profit_factor={segment.profit_factor} "
                f"| drawdown_r={segment.maximum_drawdown_r:.4f}"
            )
