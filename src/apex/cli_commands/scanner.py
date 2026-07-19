"""Dynamic futures opportunity scanner CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer

from apex.application import (
    bootstrap,
    build_analysis_record,
    configuration_metadata,
    create_market_data_services,
    reconcile_pending_opportunities_sqlite,
    scan_symbols,
    select_futures_scan_symbols,
    serialize_futures_screening,
    write_analysis_record,
    write_analysis_record_sqlite,
    write_json_report,
)
from apex.application.enriched_public_output import serialize_scan_result, serialize_symbol_analysis
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation.methodology_selected_entry_output import render_discovery_scan

ScanDirection = Literal["long", "short", "both"]


def register_scanner_commands(app: typer.Typer) -> None:
    """Register broad futures opportunity discovery."""

    @app.command("scan")
    def scan(
        symbols_file: Path | None = typer.Option(
            None,
            "--symbols-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Optional static symbol override. Defaults to live Binance futures discovery.",
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        report: Path | None = typer.Option(None, "--report"),
        record: Path | None = typer.Option(None, "--record"),
        record_db: Path | None = typer.Option(None, "--record-db"),
        explain: bool = typer.Option(False, "--explain", help="Show full diagnostic evidence."),
        candle_limit: int = typer.Option(200, "--candles", min=200, max=999),
        results: int = typer.Option(
            20,
            "--results",
            min=1,
            max=50,
            help="Maximum ranked results to display after detailed analysis.",
        ),
        shortlist: int = typer.Option(
            36,
            "--shortlist",
            min=1,
            max=100,
            help="Number of screened symbols to analyze in detail.",
        ),
        direction: ScanDirection = typer.Option(
            "both",
            "--direction",
            case_sensitive=False,
            help="Display long, short, or both directions.",
        ),
        config_dir: Path = typer.Option(
            Path("config"),
            "--config-dir",
            exists=True,
            file_okay=False,
            help="Configuration directory containing Apex YAML settings.",
        ),
    ) -> None:
        """Discover, analyze, and rank the active futures symbol universe."""

        try:
            output_mode = _normalize_scanner_output(output)
            context = bootstrap(config_dir)
            with create_market_data_services(context.settings) as services:
                base_screener_settings = context.settings.futures_screener
                screener_settings = base_screener_settings.model_copy(
                    update={
                        "shortlist_size": shortlist,
                        "ticker_prefilter_size": max(
                            base_screener_settings.ticker_prefilter_size,
                            shortlist,
                        ),
                    }
                )
                selection = select_futures_scan_symbols(
                    services.futures_universe,
                    services.futures_screener,
                    services.candles,
                    config=screener_settings.to_domain(),
                    symbols_file=symbols_file,
                    quote_asset=screener_settings.quote_asset,
                    blacklist=screener_settings.blacklist,
                    allowlist=screener_settings.allowlist,
                )
                result = scan_symbols(
                    selection.symbols,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings,
                        "timeframe_max_staleness_seconds",
                        None,
                    ),
                    candle_limit=candle_limit,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    methodology_gate_mode=context.settings.methodology_gate_mode,
                    market_environment_config=context.settings.market_environment,
                    futures_evidence_enabled=context.settings.futures_evidence_enabled,
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Scanner market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_scan_result(
            result,
            display_limit=results,
            direction=direction,
        )
        if selection.screening is not None:
            payload["screening"] = serialize_futures_screening(selection.screening)
        payload.update(configuration_metadata(context.settings.model_dump(mode="json")))
        if report is not None:
            write_json_report(payload, report)
        effective_record_db = record_db
        if effective_record_db is None and context.settings.outcome_tracking_enabled:
            effective_record_db = context.settings.data_dir / "reports" / "analysis.db"
        if record is not None or effective_record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if effective_record_db is not None:
                for analysis in result.analyses:
                    reconcile_pending_opportunities_sqlite(
                        effective_record_db,
                        analysis.symbol,
                        analysis.outcome_candles,
                    )
                    analysis_payload = serialize_symbol_analysis(analysis)
                    analysis_payload.update(
                        configuration_metadata(context.settings.model_dump(mode="json"))
                    )
                    write_analysis_record_sqlite(
                        effective_record_db,
                        build_analysis_record(analysis_payload),
                    )
                write_analysis_record_sqlite(effective_record_db, analysis_record)

        if output_mode == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        typer.echo(render_discovery_scan(payload, explain=explain))


def _normalize_scanner_output(value: str) -> str:
    """Normalize the scanner's intentionally small output surface."""

    normalized = value.strip().lower()
    if normalized not in {"text", "json"}:
        raise ValueError("scanner output must be one of: text, json")
    return normalized


__all__ = ["register_scanner_commands"]
