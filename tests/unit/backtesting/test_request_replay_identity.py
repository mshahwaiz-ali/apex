from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.backtesting.contracts import (
    BacktestActivationType,
    BacktestRequest,
    BacktestSignal,
)
from apex.strategies import StrategyType, TradeDirection

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _signal(
    candidate_id: str | None,
    *,
    entry_price: float = 100.0,
    activation_level: float | None = None,
    activation_expiry_candles: int | None = None,
) -> BacktestSignal:
    conditional = activation_level is not None
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
        activation_type=(BacktestActivationType.CANDLE_CLOSE if conditional else None),
        activation_level=activation_level,
        pre_entry_invalidation_price=97.5 if conditional else None,
        maximum_chase_price=101.0 if conditional else None,
        activation_expiry_candles=activation_expiry_candles,
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


def test_request_accepts_distinct_candidate_less_geometry() -> None:
    first = _signal(None, entry_price=100.0)
    second = _signal(None, entry_price=101.0)

    request = BacktestRequest(
        signals=(first, second),
        candles_by_symbol={},
    )

    assert request.signals == (first, second)


def test_request_rejects_exact_candidate_less_geometry_duplicate() -> None:
    first = _signal(None, entry_price=100.0)
    duplicate = _signal(None, entry_price=100.0)

    with pytest.raises(ValueError, match="replay signal identities must be unique"):
        BacktestRequest(
            signals=(first, duplicate),
            candles_by_symbol={},
        )


def test_request_accepts_distinct_candidate_less_activation_levels() -> None:
    first = _signal(None, activation_level=100.0, activation_expiry_candles=3)
    second = _signal(None, activation_level=100.5, activation_expiry_candles=3)

    request = BacktestRequest(
        signals=(first, second),
        candles_by_symbol={},
    )

    assert request.signals == (first, second)


def test_request_accepts_distinct_candidate_less_activation_expiry() -> None:
    first = _signal(None, activation_level=100.0, activation_expiry_candles=3)
    second = _signal(None, activation_level=100.0, activation_expiry_candles=5)

    request = BacktestRequest(
        signals=(first, second),
        candles_by_symbol={},
    )

    assert request.signals == (first, second)
