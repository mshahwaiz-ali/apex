from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from apex.backtesting import BacktestSignal
from apex.paper_trading import (
    PaperTrade,
    PaperTradeState,
    build_forward_paper_daily_report,
    load_and_verify_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.strategies import StrategyType, TradeDirection


def _signal(generated_at: datetime) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated_at,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        quantity=1.0,
        risk_amount=5.0,
        confidence_score=80.0,
    )


def _trade(
    trade_id: str,
    *,
    created_at: datetime,
    state: PaperTradeState,
    exit_time: datetime | None = None,
    net_pnl: float = 0.0,
    realized_r: float = 0.0,
) -> PaperTrade:
    return PaperTrade(
        trade_id=trade_id,
        signal=_signal(created_at),
        state=state,
        created_at=created_at,
        updated_at=exit_time or created_at,
        analysis_payload={},
        lifecycle_events=(
            {
                "event_type": "CREATED",
                "occurred_at": created_at.isoformat(),
            },
        ),
        exit_time=exit_time,
        exit_price=110.0 if exit_time is not None else None,
        net_pnl=net_pnl,
        realized_r_multiple=realized_r,
        closed_percentage=100.0 if exit_time is not None else 0.0,
    )


def test_daily_report_is_deterministic_and_day_scoped(tmp_path: Path) -> None:
    first_day = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    report_day = datetime(2026, 7, 15, 9, tzinfo=timezone.utc)
    closed = _trade(
        "closed",
        created_at=first_day,
        state=PaperTradeState.TARGET_HIT,
        exit_time=report_day,
        net_pnl=10.0,
        realized_r=2.0,
    )
    open_trade = _trade(
        "open",
        created_at=report_day,
        state=PaperTradeState.WAITING_FOR_ENTRY,
    )
    generated = datetime(2026, 7, 15, 23, tzinfo=timezone.utc)

    first = build_forward_paper_daily_report(
        report_date=date(2026, 7, 15),
        trades=(open_trade, closed),
        generated_at=generated,
    )
    second = build_forward_paper_daily_report(
        report_date=date(2026, 7, 15),
        trades=(closed, open_trade),
        generated_at=generated,
    )

    assert first == second
    assert first.payload["counts"] == {
        "cumulative_trades": 2,
        "created_today": 1,
        "closed_today": 1,
        "open_trades": 1,
        "lifecycle_events_today": 1,
    }
    assert first.payload["performance"]["realized_net_pnl_today"] == 10.0
    assert first.payload["performance"]["realized_r_today"] == 2.0
    assert first.payload["open_trade_ids"] == ["open"]
    assert first.payload["closed_trade_ids_today"] == ["closed"]

    path = tmp_path / "daily.json"
    write_forward_paper_daily_report(first, path)
    assert load_and_verify_forward_paper_daily_report(path) == first


def test_tampered_daily_report_is_rejected(tmp_path: Path) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    report = build_forward_paper_daily_report(
        report_date=date(2026, 7, 15),
        trades=(
            _trade(
                "open",
                created_at=now,
                state=PaperTradeState.WAITING_FOR_ENTRY,
            ),
        ),
        generated_at=now,
    )
    path = tmp_path / "daily.json"
    write_forward_paper_daily_report(report, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["counts"]["open_trades"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="hash does not match"):
        load_and_verify_forward_paper_daily_report(path)


def test_naive_event_timestamp_is_rejected() -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    trade = PaperTrade(
        trade_id="bad-event",
        signal=_signal(now),
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=now,
        updated_at=now,
        analysis_payload={},
        lifecycle_events=(
            {
                "event_type": "CREATED",
                "occurred_at": "2026-07-15T12:00:00",
            },
        ),
    )

    with pytest.raises(ValueError, match="event time must be timezone-aware"):
        build_forward_paper_daily_report(
            report_date=date(2026, 7, 15),
            trades=(trade,),
            generated_at=now,
        )
