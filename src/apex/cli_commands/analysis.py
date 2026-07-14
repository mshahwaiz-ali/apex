"""Manual selected-symbol analysis command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    build_analysis_record,
    build_futures_account_input,
    build_futures_plan_result,
    create_market_data_services,
    format_symbol_text,
    format_trade_management_plan,
    load_default_risk_config,
    serialize_symbol_analysis,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.data.providers.errors import MarketDataProviderError


def register_analysis_commands(app: typer.Typer) -> None:
    @app.command("analyze")
    def analyze(
        symbol: str = typer.Argument(..., help="Any provider-supported futures market symbol."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        wallet_balance: float = typer.Option(
            100.0,
            "--wallet-balance",
            min=0.01,
            help="Futures wallet balance used for account-aware planning.",
        ),
        risk_mode: str | None = typer.Option(
            None,
            "--risk-mode",
            help="STANDARD, AGGRESSIVE, or EXTREME. Defaults to product configuration.",
        ),
        leverage_mode: str | None = typer.Option(
            None,
            "--leverage-mode",
            help="AUTOMATIC or MANUAL. Defaults to product configuration.",
        ),
        manual_leverage: float | None = typer.Option(
            None,
            "--manual-leverage",
            min=1.0,
            help="Required only when leverage mode is MANUAL.",
        ),
        max_account_loss_pct: float | None = typer.Option(
            None,
            "--max-account-loss-pct",
            min=0.01,
            max=100.0,
            help="Optional override for maximum planned account loss percentage.",
        ),
        record: Path | None = typer.Option(
            None,
            "--record",
            help="Optional append-only JSONL analysis record path.",
        ),
        record_db: Path | None = typer.Option(
            None,
            "--record-db",
            help="Optional SQLite analysis record database path.",
        ),
    ) -> None:
        try:
            account = build_futures_account_input(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
                leverage_mode=leverage_mode,
                manual_leverage=manual_leverage,
                maximum_account_loss_percentage=max_account_loss_pct,
            )
            context = bootstrap()
            with create_market_data_services(context.settings) as services:
                result = analyze_selected_symbol(
                    symbol,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings, "timeframe_max_staleness_seconds", None
                    ),
                    candle_limit=candle_limit,
                    risk_config=load_default_risk_config(),
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    gainer_state_thresholds=getattr(
                        context.settings, "gainer_state_thresholds", None
                    ),
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Analysis market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = serialize_symbol_analysis(result)
        payload["futures_account"] = account.model_dump(mode="json") | {
            "maximum_account_loss_amount": account.maximum_account_loss_amount
        }
        assessment = getattr(result, "assessment", None)
        setup = getattr(assessment, "setup", None)
        if setup is not None:
            payload["futures_plan"] = build_futures_plan_result(setup, account)
        if record is not None or record_db is not None:
            analysis_record = build_analysis_record(payload)
            if record is not None:
                write_analysis_record(record, analysis_record)
            if record_db is not None:
                write_analysis_record_sqlite(record_db, analysis_record)

        if output == "json":
            typer.echo(json.dumps(payload, indent=2, default=str))
            return

        typer.echo(format_symbol_text(result))
        typer.echo(
            "Futures account: "
            f"wallet={account.wallet_balance:.2f} "
            f"risk={account.risk_mode.value} "
            f"leverage={account.leverage_mode.value} "
            f"max_loss={account.maximum_account_loss_amount:.2f} "
            f"margin={account.margin_mode.value}"
        )
        futures_plan = payload.get("futures_plan")
        if isinstance(futures_plan, dict):
            status = futures_plan.get("status", "UNKNOWN")
            typer.echo(f"Futures plan: {status}")
            management_plan = futures_plan.get("management_plan")
            if status == "APPROVED" and isinstance(management_plan, dict):
                typer.echo(format_trade_management_plan(management_plan))
            reasons = futures_plan.get("reasons", [])
            if isinstance(reasons, list):
                for reason in reasons:
                    typer.echo(f"- {reason}")
