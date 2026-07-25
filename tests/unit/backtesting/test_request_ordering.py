from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting.contracts import BacktestRequest, BacktestSignal
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _signal(candidate_id: str) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=80.0,
        candidate_id=candidate_id,
        replay_source="opportunity_portfolio",
    )


def test_request_accepts_deterministic_equal_time_candidate_order() -> None:
    first = _signal("candidate-a")
    second = _signal("candidate-b")

    request = BacktestRequest(
        signals=(first, second),
        candles_by_symbol={},
    )

    assert request.signals == (first, second)


def test_request_rejects_insertion_order_for_equal_time_candidates() -> None:
    first = _signal("candidate-a")
    second = _signal("candidate-b")

    with pytest.raises(
        ValueError,
        match="deterministic chronological order",
    ):
        BacktestRequest(
            signals=(second, first),
            candles_by_symbol={},
        )
