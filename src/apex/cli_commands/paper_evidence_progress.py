"""CLI reporting for P1 forward-paper sample progress."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from apex.application import bootstrap
from apex.paper_trading.evidence_progress import build_forward_evidence_progress
from apex.paper_trading.store import PaperTradeStore
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.paper_progress import render_evidence_progress


def register_paper_evidence_progress_command(app: typer.Typer) -> None:
    """Register the forward-paper evidence progress command."""

    @app.command("evidence-progress")
    def evidence_progress(
        minimum_closed_trades: int = typer.Option(100, "--minimum-closed-trades", min=1),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy output selector: text or json.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text or json.",
        ),
    ) -> None:
        context = bootstrap()
        store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
        progress = build_forward_evidence_progress(
            store.load(),
            minimum_closed_trades=minimum_closed_trades,
        )
        payload = asdict(progress)
        payload["all_segments_sufficient"] = progress.all_segments_sufficient

        try:
            mode = _resolve_presentation_mode(output=output, format_=format_)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--format") from exc

        if mode is OutputMode.JSON:
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return

        typer.echo(render_evidence_progress(payload, mode=mode))


def _resolve_presentation_mode(*, output: str, format_: str | None) -> OutputMode:
    if format_ is not None:
        return normalize_cli_output_mode(format_)

    legacy = output.strip().lower()
    if legacy not in {"text", "json"}:
        raise ValueError("legacy output must be text or json")
    return normalize_cli_output_mode(legacy)
