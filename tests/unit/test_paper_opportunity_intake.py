"""Focused coverage for automatic paper opportunity intake."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from apex.backtesting import BacktestSignal
from apex.cli_commands.paper_intake import register_paper_intake_commands
from apex.paper_trading import (
    IntakeCandidate,
    IntakeMarketType,
    IntakeReason,
    IntakeResult,
    IntakeStatus,
    PaperTrade,
    PaperTradeState,
    PaperTradeStore,
    build_futures_intake_candidate,
    build_spot_intake_candidate,
    persist_intake_candidates,
)
from apex.risk import RiskDecision
from apex.strategies import StrategyType, TradeDirection

_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _trade(*, symbol: str = "BTC/USDT", market_type: str = "futures") -> PaperTrade:
    signal = BacktestSignal(
        symbol=symbol,
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=_NOW,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=80.0,
    )
    return PaperTrade(
        trade_id=f"trade-{symbol}",
        signal=signal,
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=_NOW,
        updated_at=_NOW,
        analysis_payload={"market_type": market_type},
    )


def _candidate(*, symbol: str = "BTC/USDT", market_type: IntakeMarketType) -> IntakeCandidate:
    trade = _trade(symbol=symbol, market_type=market_type.value)
    return IntakeCandidate(
        market_type=market_type,
        symbol=symbol,
        strategy="trend_pullback",
        direction="long",
        setup_segment={
            "market_type": market_type.value,
            "symbol": symbol,
            "strategy": "trend_pullback",
            "direction": "long",
        },
        analysis_timestamp=_NOW,
        plan_identity="stable-plan",
        source_command=f"paper intake-{market_type.value}",
        source_mode="normal",
        analysis_payload=trade.analysis_payload,
        paper_trade=trade,
    )


def test_approved_candidate_is_persisted_with_setup_segment_and_intake_metadata(tmp_path) -> None:
    store = PaperTradeStore(tmp_path / "trades.json")
    candidate = _candidate(market_type=IntakeMarketType.FUTURES)

    summary = persist_intake_candidates(
        store,
        (candidate,),
        market_type=IntakeMarketType.FUTURES,
    )

    assert summary.accepted == 1
    assert summary.created_trade_ids == (candidate.paper_trade.trade_id,)
    saved = store.load()[0]
    assert saved.analysis_payload["paper_intake"]["deduplication_key"]
    assert candidate.setup_segment["strategy"] == "trend_pullback"


def test_repeated_scheduler_candidate_is_duplicate_skipped(tmp_path) -> None:
    store = PaperTradeStore(tmp_path / "trades.json")
    first = _candidate(market_type=IntakeMarketType.FUTURES)
    repeated = replace(
        first,
        analysis_timestamp=datetime(2026, 7, 16, 12, 5, tzinfo=UTC),
    )

    persist_intake_candidates(store, (first,), market_type=IntakeMarketType.FUTURES)
    summary = persist_intake_candidates(
        store,
        (repeated,),
        market_type=IntakeMarketType.FUTURES,
    )

    assert summary.duplicates_skipped == 1
    assert summary.results[0].reason is IntakeReason.DUPLICATE_SKIPPED
    assert len(store.load()) == 1


def test_result_ordering_is_stable_and_empty_runs_are_supported(tmp_path) -> None:
    store = PaperTradeStore(tmp_path / "trades.json")
    empty = persist_intake_candidates(store, (), market_type=IntakeMarketType.SPOT)
    assert empty.candidates_observed == 0
    assert empty.results == ()

    summary = persist_intake_candidates(
        store,
        (
            _candidate(symbol="ETH/USDT", market_type=IntakeMarketType.SPOT),
            _candidate(symbol="BTC/USDT", market_type=IntakeMarketType.SPOT),
        ),
        market_type=IntakeMarketType.SPOT,
    )
    assert tuple(result.symbol for result in summary.results) == ("BTC/USDT", "ETH/USDT")


def test_non_approved_futures_analysis_is_rejected() -> None:
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        assessment=SimpleNamespace(decision=object(), setup=None),
    )
    result = build_futures_intake_candidate(
        analysis,  # type: ignore[arg-type]
        futures_plan=None,
        management_plan=None,
        account_policy_snapshot=None,
        source_command="paper intake-futures",
        source_mode="normal",
    )
    assert result.status is IntakeStatus.REJECTED
    assert result.reason is IntakeReason.NO_APPROVED_SETUP


@pytest.mark.parametrize(
    ("entry_state", "expected_reason"),
    [
        ("invalidated", IntakeReason.INVALIDATED),
        ("missed_entry", IntakeReason.MISSED_ENTRY),
        ("expired", IntakeReason.EXPIRED),
        ("no_trade", IntakeReason.NO_TRADE),
    ],
)
def test_terminal_or_non_trade_futures_entry_states_are_rejected(
    entry_state: str,
    expected_reason: IntakeReason,
) -> None:
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        assessment=SimpleNamespace(decision=RiskDecision.APPROVED, setup=object()),
        precision_entry={"state": entry_state},
    )
    result = build_futures_intake_candidate(
        analysis,  # type: ignore[arg-type]
        futures_plan={"entry": {"state": entry_state}},
        management_plan=None,
        account_policy_snapshot=None,
        source_command="paper intake-futures",
        source_mode="normal",
    )
    assert result.status is IntakeStatus.REJECTED
    assert result.reason is expected_reason


def test_non_actionable_futures_entry_state_is_rejected() -> None:
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        assessment=SimpleNamespace(decision=RiskDecision.APPROVED, setup=object()),
        precision_entry={"state": "watch"},
    )
    result = build_futures_intake_candidate(
        analysis,  # type: ignore[arg-type]
        futures_plan={"entry": {"state": "watch"}},
        management_plan=None,
        account_policy_snapshot=None,
        source_command="paper intake-futures",
        source_mode="normal",
    )
    assert result.reason is IntakeReason.NON_ACTIONABLE_ENTRY_STATE


def test_spot_short_is_rejected_before_plan_conversion() -> None:
    result = build_spot_intake_candidate(
        symbol="BTC/USDT",
        result=object(),  # type: ignore[arg-type]
        analysis_timestamp=_NOW,
        source_command="paper intake-spot",
        source_mode="eligible",
        direction="short",
    )
    assert result.status is IntakeStatus.REJECTED
    assert result.reason is IntakeReason.SPOT_SHORT_NOT_ALLOWED


def test_spot_allocation_rejection_is_explicit() -> None:
    selected = SimpleNamespace(decision=SimpleNamespace(value="APPROVE"))
    result = build_spot_intake_candidate(
        symbol="BTC/USDT",
        result=SimpleNamespace(  # type: ignore[arg-type]
            routing=SimpleNamespace(selected=selected),
            planning=None,
        ),
        analysis_timestamp=_NOW,
        source_command="paper intake-spot",
        source_mode="eligible",
    )
    assert result.status is IntakeStatus.REJECTED
    assert result.reason is IntakeReason.SPOT_ALLOCATION_REJECTED


def test_cli_commands_are_registered() -> None:
    app = typer.Typer()
    register_paper_intake_commands(app)
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "intake-futures" in result.stdout
    assert "intake-spot" not in result.stdout

def test_execution_rejected_opportunity_is_not_admitted_to_paper() -> None:
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        generated_at=_NOW,
        assessment=SimpleNamespace(
            decision=RiskDecision.APPROVED,
            setup=SimpleNamespace(
                strategy=SimpleNamespace(value="trend_pullback"),
                direction=SimpleNamespace(value="long"),
            ),
        ),
        precision_entry={"state": "ready_now"},
        strategy_routing={},
    )
    plan = {
        "status": "REJECTED",
        "opportunity_status": "SETUP_AVAILABLE",
        "execution_approval": {
            "status": "REJECTED",
            "approved": False,
            "eligibility": "REJECTED",
            "reasons": ["account policy lockout: DAILY_DRAWDOWN"],
        },
        "entry": {"state": "ready_now"},
    }

    result = build_futures_intake_candidate(
        analysis,  # type: ignore[arg-type]
        futures_plan=plan,
        management_plan=None,
        account_policy_snapshot=None,
        source_command="paper intake-futures",
        source_mode="futures",
    )

    assert result.status is IntakeStatus.REJECTED
    assert result.reason is IntakeReason.EXECUTION_NOT_APPROVED
    assert result.detail == "account policy lockout: DAILY_DRAWDOWN"


def test_accepted_candidate_preserves_execution_approval_metadata() -> None:
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        generated_at=_NOW,
        assessment=SimpleNamespace(
            decision=RiskDecision.APPROVED,
            setup=SimpleNamespace(
                strategy=SimpleNamespace(value="trend_pullback"),
                direction=SimpleNamespace(value="long"),
            ),
        ),
        precision_entry={"state": "ready_now"},
        strategy_routing={},
    )
    paper_trade = _trade()
    plan = {
        "status": "APPROVED",
        "opportunity_status": "SETUP_AVAILABLE",
        "execution_approval": {
            "status": "APPROVED",
            "approved": True,
            "eligibility": "PAPER_ONLY",
            "reasons": [],
        },
        "eligibility": "PAPER_ONLY",
        "risk_mode": "STANDARD",
        "entry": {"state": "ready_now"},
    }

    import apex.paper_trading.intake as intake_module

    original_create = intake_module.create_paper_trade
    try:
        intake_module.create_paper_trade = lambda *args, **kwargs: paper_trade
        result = build_futures_intake_candidate(
            analysis,  # type: ignore[arg-type]
            futures_plan=plan,
            management_plan=None,
            account_policy_snapshot=None,
            source_command="paper intake-futures",
            source_mode="futures",
        )
    finally:
        intake_module.create_paper_trade = original_create

    assert isinstance(result, IntakeCandidate)
    assert result.analysis_payload["opportunity_status"] == "SETUP_AVAILABLE"
    assert result.analysis_payload["execution_approval"] == {
        "status": "APPROVED",
        "approved": True,
        "eligibility": "PAPER_ONLY",
        "reasons": [],
    }


def test_intake_summary_counts_execution_approval_rejections(tmp_path) -> None:
    store = PaperTradeStore(tmp_path / "trades.json")
    rejected = IntakeResult(
        status=IntakeStatus.REJECTED,
        reason=IntakeReason.EXECUTION_NOT_APPROVED,
        market_type=IntakeMarketType.FUTURES,
        symbol="BTC/USDT",
        detail="account policy lockout",
    )

    summary = persist_intake_candidates(
        store,
        (rejected,),
        market_type=IntakeMarketType.FUTURES,
    )

    assert summary.rejected == 1
    assert summary.reason_counts == {"EXECUTION_NOT_APPROVED": 1}
