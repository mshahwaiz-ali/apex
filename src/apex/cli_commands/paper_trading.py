"""Canonical symbol wrappers for paper-trading CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apex.application import (
    AccountStateStore,
    analyze_symbol,
    bootstrap,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    serialize_symbol_analysis,
)
from apex.application.account_context import resolve_account_context
from apex.application.exposure_classification import classify_proposed_exposure
from apex.application.paper_account_state import (
    PaperAccountExposure,
    apply_paper_account_transition,
    attach_account_state_registration,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.paper_trading import (
    PaperTrade,
    PaperTradeConfig,
    PaperTradeStore,
    create_paper_trade,
    update_paper_trade,
)


def register_paper_trading_commands(app: typer.Typer) -> None:
    """Register policy-aware paper commands using canonical market symbols."""

    @app.command("record")
    def paper_record(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        risk_mode: str | None = typer.Option(None, "--risk-mode"),
        account_policy: str | None = typer.Option(None, "--account-policy"),
        account_state_file: Path | None = typer.Option(
            None,
            "--account-state-file",
            dir_okay=False,
            help="Persistent account-state JSON file used for policy lockouts.",
        ),
        account_policies_file: Path = typer.Option(
            Path("config/account_policies.yaml"),
            "--account-policies-file",
            exists=True,
            dir_okay=False,
        ),
        wallet_balance: float | None = typer.Option(None, "--wallet-balance", min=0.01),
        proposed_directional_exposure_pct: float | None = typer.Option(
            None,
            "--proposed-directional-exposure-pct",
            min=0.0,
            max=100.0,
            help="Optional directional exposure override; defaults to full proposed risk.",
        ),
        proposed_correlated_exposure_pct: float | None = typer.Option(
            None,
            "--proposed-correlated-exposure-pct",
            min=0.0,
            max=100.0,
            help="Optional correlation override; stable-quote crypto defaults to full risk.",
        ),
        session: str | None = typer.Option(None, "--session"),
        is_weekend: bool = typer.Option(False, "--weekend"),
    ) -> None:
        """Analyze and record only after risk-mode and account-policy approval."""

        canonical_symbol = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            risk_config = load_default_risk_config()
            with create_market_data_services(context.settings) as services:
                analysis = analyze_symbol(
                    canonical_symbol,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings,
                        "timeframe_max_staleness_seconds",
                        None,
                    ),
                    candle_limit=candle_limit,
                    risk_config=risk_config,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    gainer_state_thresholds=getattr(
                        context.settings,
                        "gainer_state_thresholds",
                        None,
                    ),
                )
            if analysis.assessment.setup is None:
                typer.echo(f"{canonical_symbol}: NO_PAPER_TRADE | no approved setup")
                return
            preliminary_context = resolve_account_context(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
                account_policy_name=account_policy,
                account_state_file=account_state_file,
                account_policies_file=account_policies_file,
                session=session,
                is_weekend=is_weekend,
            )
            exposure = classify_proposed_exposure(
                symbol=canonical_symbol,
                direction=analysis.assessment.setup.direction,
                risk_pct=preliminary_context.account.maximum_account_loss_percentage,
                directional_override_pct=proposed_directional_exposure_pct,
                correlated_override_pct=proposed_correlated_exposure_pct,
            )
            account_context = resolve_account_context(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
                account_policy_name=account_policy,
                account_state_file=account_state_file,
                account_policies_file=account_policies_file,
                proposed_directional_exposure_pct=exposure.directional_exposure_pct,
                proposed_correlated_exposure_pct=exposure.correlated_exposure_pct,
                session=session,
                is_weekend=is_weekend,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Paper record market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        futures_plan = build_futures_plan_result(
            analysis.assessment.setup,
            account_context.account,
            account_policy=account_context.policy,
            account_policy_state=account_context.policy_state,
        )
        if futures_plan.get("status") == "REJECTED":
            reasons = "; ".join(str(reason) for reason in futures_plan.get("reasons", []))
            typer.echo(f"{canonical_symbol}: NO_PAPER_TRADE | {reasons}")
            return
        futures_plan["proposed_exposure_classification"] = exposure.as_dict()
        if account_context.snapshot is not None:
            futures_plan = attach_account_state_registration(
                futures_plan,
                PaperAccountExposure(
                    policy_name=account_context.snapshot.policy_name,
                    risk_pct=account_context.account.maximum_account_loss_percentage,
                    directional_risk_pct=exposure.directional_exposure_pct,
                    correlated_risk_pct=exposure.correlated_exposure_pct,
                ),
            )

        store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
        trade = create_paper_trade(
            analysis.assessment.setup,
            analysis_payload=serialize_symbol_analysis(analysis),
            futures_plan=futures_plan,
        )
        store.upsert(trade)
        typer.echo(
            f"{canonical_symbol}: PAPER_RECORDED | id={trade.trade_id} | state={trade.state.value}"
        )

    @app.command("update")
    def paper_update(
        symbol: str | None = typer.Argument(None, help="Optional market symbol filter."),
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
        account_state_file: Path | None = typer.Option(
            None,
            "--account-state-file",
            dir_okay=False,
            help="Optional persistent account-state JSON file to update with lifecycle events.",
        ),
    ) -> None:
        """Update paper trades and optionally synchronize persistent account state."""

        canonical = normalize_market_symbol(symbol) if symbol is not None else None
        try:
            context = bootstrap()
            store = PaperTradeStore(context.settings.data_dir / "paper_trading" / "trades.json")
            trades = store.load()
            account_store = (
                AccountStateStore(account_state_file) if account_state_file is not None else None
            )
            account_state = account_store.load() if account_store is not None else None
            if account_store is not None and account_state is None:
                raise ValueError(f"account-state file does not exist: {account_state_file}")
            updated: list[PaperTrade] = []
            with create_market_data_services(context.settings) as services:
                for trade in trades:
                    if canonical is not None and trade.signal.symbol != canonical:
                        updated.append(trade)
                        continue
                    if not trade.is_open:
                        updated.append(trade)
                        continue
                    candles = tuple(
                        services.candles.fetch_candles(
                            trade.signal.symbol,
                            timeframe,
                            limit=candle_limit,
                        )
                    )
                    next_trade = update_paper_trade(
                        trade,
                        candles,
                        config=PaperTradeConfig(),
                    )
                    if account_state is not None:
                        account_state = apply_paper_account_transition(
                            account_state,
                            trade,
                            next_trade,
                        )
                    updated.append(next_trade)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Paper update market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        store.save(tuple(updated))
        if account_store is not None and account_state is not None:
            account_store.save(account_state)
        typer.echo(f"PAPER_UPDATED | trades={len(updated)}")
