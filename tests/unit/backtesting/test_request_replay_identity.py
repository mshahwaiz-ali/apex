from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting.contracts import BacktestRequest, BacktestSignal
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _signal(candidate_id: str, *, entry_price: float = 100.0) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.LONG,
        generated_at=NOW,
        entry_price=entry_price,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=entry_price - 98.0,
        confidence_score=80.0,
        candidate_id=candidate_id,
        replay_source="opportunity_portfolio",
    )


def test_request_accepts_distinct_equal_time_replay_identities() -> None:
    first = _signal("candidate-a")
    second = _signal("candidate-b")

    request = BacktestRequest(
        signals=(first, second),
        candles_by_symbol={},
    )

    assert request.signals == (first, second)


def test_request_rejects_duplicate_replay_identity_with_different_geometry() -> None:
    first = _signal("candidate-a", entry_price=100.0)
    duplicate_identity = _signal("candidate-a", entry_price=101.0)

    with pytest.raises(ValueError, match="replay signal identities must be unique"):
        BacktestRequest(
            signals=(first, duplicate_identity),
            candles_by_symbol={},
        )
