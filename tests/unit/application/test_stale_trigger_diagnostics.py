from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    StaleTriggerDiagnosticCode,
    TriggerFreshnessState,
    build_stale_trigger_diagnostics,
    opportunity_portfolio_payload,
    portfolio_from_setups,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    executable: bool = True,
    expiry_seconds: int | None = None,
    expiry_bars: int | None = None,
    expiry_reason: str = "",
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(99.0, 101.0, 100.0, 100.0, 102.0, True),
        stop_loss=StopLoss(97.0, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",)),),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=executable,
        setup_expiry_seconds=expiry_seconds,
        setup_expiry_bars=expiry_bars,
        setup_expiry_reason=expiry_reason,
    )


def test_no_expiry_is_reported_without_fabricating_staleness() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup("no-expiry"),
        evaluated_at=NOW,
    )

    assert diagnostics.state is TriggerFreshnessState.NOT_CONFIGURED
    assert diagnostics.codes == ()
    assert diagnostics.is_stale is False


def test_time_based_trigger_is_fresh_before_expiry() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup("fresh", expiry_seconds=60, expiry_reason="micro trigger window"),
        evaluated_at=NOW + timedelta(seconds=59),
    )

    assert diagnostics.state is TriggerFreshnessState.FRESH
    assert diagnostics.codes == ()
    assert diagnostics.age_seconds == 59.0


def test_time_based_trigger_is_stale_at_expiry_boundary() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup(
            "stale",
            executable=False,
            expiry_seconds=60,
            expiry_reason="micro trigger window",
        ),
        evaluated_at=NOW + timedelta(seconds=60),
    )

    assert diagnostics.state is TriggerFreshnessState.STALE
    assert diagnostics.codes == (StaleTriggerDiagnosticCode.EXPIRED_BY_SECONDS,)
    assert diagnostics.is_stale is True


def test_execution_authorized_after_expiry_is_reported_without_rewrite() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup(
            "stale-authorized",
            executable=True,
            expiry_seconds=30,
            expiry_reason="activation expired",
        ),
        evaluated_at=NOW + timedelta(seconds=31),
    )

    assert diagnostics.codes == (
        StaleTriggerDiagnosticCode.EXPIRED_BY_SECONDS,
        StaleTriggerDiagnosticCode.EXECUTION_AUTHORIZED_AFTER_EXPIRY,
    )
    assert diagnostics.execution_allowed_now is True


def test_bar_expiry_is_explicitly_unevaluated_without_candle_context() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup("bar-expiry", expiry_bars=3),
        evaluated_at=NOW + timedelta(minutes=5),
    )

    assert diagnostics.state is TriggerFreshnessState.BAR_EXPIRY_UNEVALUATED
    assert diagnostics.codes == (StaleTriggerDiagnosticCode.BAR_EXPIRY_REQUIRES_CONTEXT,)
    assert diagnostics.is_stale is False


def test_clock_skew_is_reported_deterministically() -> None:
    diagnostics = build_stale_trigger_diagnostics(
        _setup("clock-skew"),
        evaluated_at=NOW - timedelta(seconds=1),
    )

    assert diagnostics.state is TriggerFreshnessState.CLOCK_SKEW
    assert diagnostics.codes == (StaleTriggerDiagnosticCode.EVALUATED_BEFORE_DECISION_TIME,)
    assert diagnostics.age_seconds == -1.0


def test_stale_trigger_serializes_additively() -> None:
    setup = _setup(
        "serialized",
        executable=True,
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)
    portfolio = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    payload = opportunity_portfolio_payload(portfolio)["current_long"]

    assert payload is not None
    assert payload["stale_trigger"] == {
        "state": "stale",
        "codes": [
            "expired_by_seconds",
            "execution_authorized_after_expiry",
        ],
        "evaluated_at": evaluated_at.isoformat(),
        "decision_time": NOW.isoformat(),
        "age_seconds": 31.0,
        "setup_expiry_seconds": 30,
        "setup_expiry_bars": None,
        "setup_expiry_reason": "activation expired",
        "execution_allowed_now": True,
        "is_stale": True,
    }
    assert payload["execution_allowed_now"] is True
    assert payload["sequence_role"] == "current"


def test_scan_and_analyze_serialize_identical_trigger_freshness() -> None:
    setup = _setup(
        "parity",
        executable=False,
        expiry_seconds=30,
        expiry_reason="activation expired",
    )
    evaluated_at = NOW + timedelta(seconds=31)
    scan = portfolio_from_setups(
        (setup,),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    analyze = portfolio_from_setups(
        (replace(setup),),
        symbol="BTCUSDT",
        cmp=100.0,
        analysis_timestamp=evaluated_at,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    scan_payload = opportunity_portfolio_payload(scan)["nearby_long"]
    analyze_payload = opportunity_portfolio_payload(analyze)["nearby_long"]

    assert scan_payload is not None
    assert analyze_payload is not None
    assert scan_payload["stale_trigger"] == analyze_payload["stale_trigger"]
