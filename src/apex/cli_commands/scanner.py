"""Dynamic futures opportunity scanner CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    bootstrap,
    build_analysis_record,
    create_market_data_services,
    scan_symbols,
    select_futures_scan_symbols,
    serialize_futures_screening,
    serialize_scan_result,
    write_analysis_record,
    write_analysis_record_sqlite,
    write_json_report,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation.scanner import render_futures_scan

_REMOVED_PUBLIC_FIELDS = {
    "execution_approval",
    "futures_account",
    "futures_plan",
    "risk_mode",
}


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
        candle_limit: int = typer.Option(200, "--candles", min=40, max=999),
    ) -> None:
        """Discover, analyze, and rank the active futures symbol universe."""

        try:
            output_mode = _normalize_scanner_output(output)
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                screener_settings = context.settings.futures_screener
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
                    candle_limit=candle_limit + 1,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Scanner market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = _without_account_fields(serialize_scan_result(result))
        if selection.screening is not None:
            payload["screening"] = serialize_futures_screening(selection.screening)
        if report is not None:
            write_json_report(payload, report)
        if record is not None or record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if record_db is not None:
                write_analysis_record_sqlite(record_db, analysis_record)

        if output_mode == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return
        typer.echo(render_futures_scan(payload))


def _without_account_fields(payload: dict[str, object]) -> dict[str, object]:
    """Remove legacy account-planning fields from scanner output."""

    cleaned = {key: value for key, value in payload.items() if key not in _REMOVED_PUBLIC_FIELDS}
    for key in ("best_overall",):
        value = cleaned.get(key)
        if isinstance(value, dict):
            cleaned[key] = _without_account_fields(value)
    for key in ("results", "top_long_setups", "top_short_setups"):
        value = cleaned.get(key)
        if isinstance(value, list):
            cleaned[key] = [
                _without_account_fields(item) if isinstance(item, dict) else item for item in value
            ]
    return cleaned


def _normalize_scanner_output(value: str) -> str:
    """Normalize the scanner's intentionally small output surface."""

    normalized = value.strip().lower()
    if normalized not in {"text", "json"}:
        raise ValueError("scanner output must be one of: text, json")
    return normalized


__all__ = ["register_scanner_commands"]
