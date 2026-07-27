"""Dynamic futures opportunity scanner CLI command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import typer

from apex.application import (
    RegimeHistoryStore,
    bootstrap,
    build_analysis_record,
    configuration_metadata,
    create_market_data_services,
    reconcile_pending_opportunities_sqlite,
    regime_observation_from_analysis,
    scan_symbols,
    select_futures_scan_symbols,
    serialize_futures_screening,
    write_analysis_record_sqlite,
)
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.enriched_public_output import (
    serialize_scan_result,
    serialize_symbol_analysis,
)
from apex.application.methodology_geometry_runtime import (
    geometry_execution_costs_from_settings,
)
from apex.cli_commands.symbols import normalize_futures_symbol
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation.methodology_selected_entry_output import render_discovery_scan
from apex.presentation.terminal import cli_progress, emit_terminal

ScanDirection = Literal["long", "short", "both"]


def _serialize_scan_payload(
    result: ScanResult,
    *,
    display_limit: int,
    direction: ScanDirection,
    rollout_diagnostics_enabled: bool = False,
) -> dict[str, object]:
    """Serialize the canonical ranked scan payload."""

    return serialize_scan_result(
        result,
        display_limit=display_limit,
        direction=direction,
        include_rollout_diagnostics=rollout_diagnostics_enabled,
    )


def _serialize_scan_analysis_record(
    analysis: SymbolAnalysis,
    *,
    rollout_diagnostics_enabled: bool = False,
) -> dict[str, object]:
    """Serialize one scan result for internal outcome tracking."""

    return serialize_symbol_analysis(
        analysis,
        include_rollout_diagnostics=rollout_diagnostics_enabled,
    )


def register_scanner_commands(app: typer.Typer) -> None:
    """Register broad futures opportunity discovery."""

    @app.command("scan")
    def scan(
        symbol: str | None = typer.Argument(
            None,
            metavar="[SYMBOL]",
            help="Optional single market; bare assets default to USDT, for example BANK.",
        ),
        symbols_file: Path | None = typer.Option(
            None,
            "--symbols-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Optional static symbol override. Defaults to live Binance futures discovery.",
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        explain: bool = typer.Option(
            False,
            "--explain",
            help="Show full evidence, contradictions, rejected candidates, and diagnostics.",
        ),
        candle_limit: int = typer.Option(200, "--candles", min=200, max=999),
        results: int = typer.Option(
            20,
            "--results",
            min=1,
            max=50,
            help="Maximum ranked trade opportunities to display.",
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
        """Find and rank current or developing futures trade setups."""

        try:
            output_mode = _normalize_scanner_output(output)
            normalized_symbol = None if symbol is None else normalize_futures_symbol(symbol)
            if normalized_symbol is not None and symbols_file is not None:
                raise ValueError("provide either SYMBOL or --symbols-file, not both")

            with cli_progress() as progress:
                progress.update("Loading configuration…")
                context = bootstrap(config_dir)
                scan_time = datetime.now(UTC)
                regime_history_path = context.settings.data_dir / "reports" / "regime_history.json"
                regime_history = RegimeHistoryStore(regime_history_path)
                selection = None
                with create_market_data_services(context.settings) as services:
                    if normalized_symbol is None:
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
                        progress.update("Discovering and screening Binance futures markets…")
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
                        selected_symbols = selection.symbols
                    else:
                        progress.update(f"Preparing focused scan for {normalized_symbol}…")
                        selected_symbols = (normalized_symbol,)

                    progress.update("Analyzing selected symbols…")
                    previous_regimes = {
                        selected_symbol.upper(): previous
                        for selected_symbol in selected_symbols
                        if (
                            previous := regime_history.previous_state(
                                selected_symbol,
                                before=scan_time,
                            )
                        )
                        is not None
                    }
                    result = scan_symbols(
                        selected_symbols,
                        services.candles,
                        timeframes=context.settings.analysis_timeframes,
                        timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                        timeframe_max_staleness_seconds=getattr(
                            context.settings,
                            "timeframe_max_staleness_seconds",
                            None,
                        ),
                        timeframe_indicator_profiles=getattr(
                            context.settings, "timeframe_indicator_profiles", None
                        ),
                        candle_limit=candle_limit,
                        generated_at=scan_time,
                        strategy_routing=getattr(context.settings, "strategy_routing", None),
                        methodology_gate_mode=context.settings.methodology_gate_mode,
                        methodology_settings=context.settings.methodology,
                        geometry_safety_mode=(
                            context.settings.methodology_gate_mode
                            if context.settings.geometry_execution.enabled
                            else "shadow"
                        ),
                        geometry_execution_costs=geometry_execution_costs_from_settings(
                            context.settings.geometry_execution
                        ),
                        market_environment_config=context.settings.market_environment,
                        futures_evidence_enabled=context.settings.futures_evidence_enabled,
                        previous_market_regimes=previous_regimes,
                    )
                persisted_regimes = 0
                for analysis in result.analyses:
                    regime_observation = regime_observation_from_analysis(
                        symbol=analysis.symbol,
                        observed_at=analysis.generated_at,
                        market_intelligence=analysis.market_intelligence,
                    )
                    if regime_observation is not None:
                        regime_history.append(regime_observation)
                        persisted_regimes += 1
                progress.update("Ranking retained opportunities…")
                payload = _serialize_scan_payload(
                    result,
                    display_limit=results,
                    direction=direction,
                )
                if selection is not None and selection.screening is not None:
                    payload["screening"] = serialize_futures_screening(selection.screening)
                payload.update(configuration_metadata(context.settings.model_dump(mode="json")))
                payload["regime_history"] = {
                    "schema_version": 1,
                    "path": str(regime_history_path),
                    "prior_state_count": len(previous_regimes),
                    "persisted_observation_count": persisted_regimes,
                }
                outcome_db = context.settings.data_dir / "reports" / "analysis.db"
                payload["outcome_tracking"] = {
                    "enabled": context.settings.outcome_tracking_enabled,
                    "database": str(outcome_db),
                }
                if context.settings.outcome_tracking_enabled:
                    progress.update("Saving outcome-tracking records…")
                    analysis_record = build_analysis_record(payload)
                    for analysis in result.analyses:
                        reconcile_pending_opportunities_sqlite(
                            outcome_db,
                            analysis.symbol,
                            analysis.outcome_candles,
                        )
                        analysis_payload = _serialize_scan_analysis_record(analysis)
                        analysis_payload.update(
                            configuration_metadata(context.settings.model_dump(mode="json"))
                        )
                        write_analysis_record_sqlite(
                            outcome_db,
                            build_analysis_record(analysis_payload),
                        )
                    write_analysis_record_sqlite(outcome_db, analysis_record)
                progress.update("Preparing output…")
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Scanner market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if output_mode == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        emit_terminal(render_discovery_scan(payload, explain=explain))


def _normalize_scanner_output(value: str) -> str:
    """Normalize the scanner's intentionally small output surface."""

    normalized = value.strip().lower()
    if normalized not in {"text", "json"}:
        raise ValueError("scanner output must be one of: text, json")
    return normalized


__all__ = ["register_scanner_commands"]
