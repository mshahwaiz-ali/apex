"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from apex.application import (
    RegimeHistoryStore,
    analyze_selected_symbol,
    bootstrap,
    build_analysis_record,
    configuration_metadata,
    create_market_data_services,
    reconcile_pending_opportunities_sqlite,
    regime_observation_from_analysis,
    write_analysis_record_sqlite,
)
from apex.application.discovery_contracts import SymbolAnalysis
from apex.application.enriched_public_output import serialize_symbol_analysis
from apex.application.methodology_geometry_runtime import (
    geometry_execution_costs_from_settings,
)
from apex.cli_commands.symbols import normalize_futures_symbol
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import normalize_cli_output_mode
from apex.presentation.methodology_selected_entry_output import render_discovery_analysis
from apex.presentation.terminal import cli_progress, emit_terminal


def _serialize_analysis_payload(
    result: SymbolAnalysis,
    *,
    rollout_diagnostics_enabled: bool = False,
) -> dict[str, object]:
    """Serialize the canonical selected-symbol analysis payload."""

    return serialize_symbol_analysis(
        result,
        include_rollout_diagnostics=rollout_diagnostics_enabled,
    )


def register_analysis_commands(app: typer.Typer) -> None:
    """Register focused manual futures analysis."""

    @app.command("analyze")
    def analyze(
        symbol: str = typer.Argument(
            ...,
            metavar="SYMBOL",
            help="Futures symbol; bare assets default to USDT, for example BANK.",
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        explain: bool = typer.Option(
            False,
            "--explain",
            help="Show the full evidence, contradictions, rejected candidates, and diagnostics.",
        ),
        candle_limit: int = typer.Option(200, "--candles", min=200, max=1000),
        config_dir: Path = typer.Option(
            Path("config"),
            "--config-dir",
            exists=True,
            file_okay=False,
            help="Configuration directory containing Apex YAML settings.",
        ),
    ) -> None:
        """Analyze one futures symbol and produce a detailed trade plan."""

        try:
            output_mode = normalize_cli_output_mode(output)
            normalized_symbol = normalize_futures_symbol(symbol)
            with cli_progress() as progress:
                progress.update("Loading configuration…")
                context = bootstrap(config_dir)
                analysis_time = datetime.now(UTC)
                regime_history_path = context.settings.data_dir / "reports" / "regime_history.json"
                regime_history = RegimeHistoryStore(regime_history_path)
                previous_regime = regime_history.previous_state(
                    normalized_symbol,
                    before=analysis_time,
                )
                progress.update(f"Fetching {normalized_symbol} market data…")
                with create_market_data_services(context.settings) as services:
                    progress.update("Running multi-timeframe analysis…")
                    result = analyze_selected_symbol(
                        normalized_symbol,
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
                        generated_at=analysis_time,
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
                        previous_market_regime=previous_regime,
                    )
                regime_observation = regime_observation_from_analysis(
                    symbol=result.symbol,
                    observed_at=result.generated_at,
                    market_intelligence=result.market_intelligence,
                )
                if regime_observation is not None:
                    regime_history.append(regime_observation)
                progress.update("Building trade opportunities…")
                payload = _serialize_analysis_payload(result)
                payload["regime_history"] = {
                    "schema_version": 1,
                    "path": str(regime_history_path),
                    "previous_state": previous_regime,
                    "persisted": regime_observation is not None,
                }
                payload.update(configuration_metadata(context.settings.model_dump(mode="json")))
                if context.settings.outcome_tracking_enabled:
                    outcome_db = context.settings.data_dir / "reports" / "analysis.db"
                    analysis_record = build_analysis_record(payload)
                    reconcile_pending_opportunities_sqlite(
                        outcome_db, result.symbol, result.outcome_candles
                    )
                    write_analysis_record_sqlite(outcome_db, analysis_record)
                progress.update("Preparing output…")
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Analysis market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if output_mode.value == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        emit_terminal(render_discovery_analysis(payload, mode=output_mode, explain=explain))


__all__ = ["register_analysis_commands"]
