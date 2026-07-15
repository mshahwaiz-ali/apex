from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from apex.backtesting import EvidenceQuality, HistoricalEdgeProfile
from apex.paper_trading import (
    DeviationCompatibilityStatus,
    ForwardPaperEdgeProfile,
    ForwardPaperValidationStatus,
    LifecycleAnomalyCode,
    PaperTrade,
    PaperTradeState,
    audit_paper_trade_lifecycle,
    build_forward_paper_review_report,
    compare_historical_to_forward,
    load_and_verify_forward_paper_review_report,
    write_forward_paper_review_report,
)
from apex.backtesting import BacktestSignal
from apex.strategies import StrategyType, TradeDirection


DIMENSIONS = {
    "strategy": "trend_pullback",
    "market_type": "futures",
    "risk_mode": "STANDARD",
    "symbol": "BTCUSDT",
    "market_regime": "trend",
    "score_band": "80_89",
}


def _historical() -> HistoricalEdgeProfile:
    return HistoricalEdgeProfile(
        dimensions=DIMENSIONS,
        sample_size=100,
        win_rate=0.6,
        loss_rate=0.4,
        breakeven_rate=0.0,
        average_r=0.5,
        median_r=0.4,
        expectancy=0.5,
        profit_factor=1.8,
        maximum_drawdown_r=3.0,
        maximum_losing_streak=4,
        average_holding_candles=8.0,
        average_execution_cost_r=0.05,
        evidence_quality=EvidenceQuality.PROMISING,
    )


def _forward(expectancy: float = 0.4) -> ForwardPaperEdgeProfile:
    return ForwardPaperEdgeProfile(
        dimensions=DIMENSIONS,
        sample_size=50,
        win_rate=0.56,
        expectancy=expectancy,
        profit_factor=1.5,
        maximum_drawdown_r=3.5,
    )


def _signal(now: datetime) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=now,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=80.0,
    )


def _trade(*, state: PaperTradeState, events: tuple[dict[str, Any], ...], candles_held: int = 0) -> PaperTrade:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    terminal = state in {PaperTradeState.STOPPED, PaperTradeState.TARGET_HIT}
    return PaperTrade(
        trade_id="trade-1",
        signal=_signal(now),
        state=state,
        created_at=now,
        updated_at=now,
        analysis_payload={},
        lifecycle_events=events,
        exit_time=now if terminal else None,
        exit_price=95.0 if terminal else None,
        closed_percentage=100.0 if terminal else 0.0,
        candles_held=candles_held,
    )


def test_compatible_comparison_and_excessive_degradation() -> None:
    compatible = compare_historical_to_forward(
        _historical(), _forward(), historical_period_days=100, forward_period_days=50
    )
    assert compatible.compatibility_status is DeviationCompatibilityStatus.COMPATIBLE

    degraded = compare_historical_to_forward(
        _historical(), _forward(-0.1), historical_period_days=100, forward_period_days=50
    )
    assert degraded.compatibility_status is DeviationCompatibilityStatus.DEGRADED
    assert "EXPECTANCY_DEGRADATION_EXCESSIVE" in degraded.rejection_reasons


def test_segment_mismatch_is_rejected() -> None:
    mismatch = ForwardPaperEdgeProfile(
        dimensions={**DIMENSIONS, "symbol": "ETHUSDT"},
        sample_size=10,
        win_rate=0.5,
        expectancy=0.2,
        profit_factor=1.2,
        maximum_drawdown_r=1.0,
    )
    with pytest.raises(ValueError, match="must match exactly"):
        compare_historical_to_forward(
            _historical(), mismatch, historical_period_days=100, forward_period_days=10
        )


def test_lifecycle_order_missing_close_and_holding_limit() -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    bad_order = _trade(
        state=PaperTradeState.ENTERED,
        events=(
            {"event_type": "ENTERED", "occurred_at": now.isoformat()},
            {"event_type": "CREATED", "occurred_at": now.isoformat()},
        ),
    )
    missing_close = _trade(
        state=PaperTradeState.STOPPED,
        events=({"event_type": "CREATED", "occurred_at": now.isoformat()},),
    )
    held = _trade(
        state=PaperTradeState.ENTERED,
        events=(
            {"event_type": "CREATED", "occurred_at": now.isoformat()},
            {"event_type": "ENTERED", "occurred_at": now.isoformat()},
        ),
        candles_held=25,
    )
    audit = audit_paper_trade_lifecycle((bad_order, missing_close, held), maximum_holding_candles=24)
    codes = {item.code for item in audit.anomalies}
    assert LifecycleAnomalyCode.TERMINAL_WITHOUT_CLOSE in codes
    assert LifecycleAnomalyCode.HOLDING_LIMIT_EXCEEDED in codes


@dataclass(frozen=True)
class _Validation:
    status: ForwardPaperValidationStatus


def test_review_identity_tamper_and_no_automatic_production(tmp_path: Path) -> None:
    deviation = compare_historical_to_forward(
        _historical(), _forward(), historical_period_days=100, forward_period_days=50
    )
    audit = audit_paper_trade_lifecycle((), maximum_holding_candles=24)
    validation = cast(Any, _Validation(ForwardPaperValidationStatus.PASSED_VALIDATION))
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    first = build_forward_paper_review_report(
        generated_at=now,
        daily_report_sha256="daily-hash",
        forward_validation=validation,
        deviation=deviation,
        lifecycle_audit=audit,
        sample_sufficient=True,
        manual_execution_usable=True,
    )
    second = build_forward_paper_review_report(
        generated_at=now,
        daily_report_sha256="daily-hash",
        forward_validation=validation,
        deviation=deviation,
        lifecycle_audit=audit,
        sample_sufficient=True,
        manual_execution_usable=True,
    )
    assert first == second
    assert first.payload["production_eligible"] is False

    path = tmp_path / "review.json"
    write_forward_paper_review_report(first, path)
    assert load_and_verify_forward_paper_review_report(path) == first
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["production_eligible"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_forward_paper_review_report(path)
