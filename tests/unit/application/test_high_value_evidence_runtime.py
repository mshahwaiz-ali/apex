from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apex.application.high_value_evidence_runtime import (
    build_high_value_evidence_runtime_snapshot,
    high_value_evidence_runtime_payload,
)
from apex.domain.futures_evidence import (
    MarketEvidenceBundle,
    OpenInterestSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.models import Candle

NOW = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)


def _candle(index: int, close: float) -> Candle:
    opened = NOW - timedelta(minutes=25 - index * 5)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=100.0,
        is_closed=True,
        source="fixture",
    )


@dataclass(frozen=True)
class _DecisionFrame:
    recent_candles: tuple[Candle, ...]


@dataclass(frozen=True)
class _Context:
    decision_frame: _DecisionFrame
    market_evidence: MarketEvidenceBundle | None


def _context(*, evidence: bool = True) -> _Context:
    market_evidence = None
    if evidence:
        market_evidence = MarketEvidenceBundle(
            symbol="BTCUSDT",
            as_of=NOW,
            taker_flow=(
                TakerFlowSnapshot(
                    symbol="BTCUSDT",
                    period="5m",
                    buy_volume=75.0,
                    sell_volume=25.0,
                    buy_sell_ratio=3.0,
                    captured_at=NOW - timedelta(minutes=5),
                    source="fixture",
                ),
            ),
            open_interest=(
                OpenInterestSnapshot(
                    symbol="BTCUSDT",
                    period="5m",
                    open_interest=1000.0,
                    open_interest_value=100000.0,
                    captured_at=NOW - timedelta(minutes=20),
                    source="fixture",
                ),
                OpenInterestSnapshot(
                    symbol="BTCUSDT",
                    period="5m",
                    open_interest=1200.0,
                    open_interest_value=132000.0,
                    captured_at=NOW - timedelta(minutes=5),
                    source="fixture",
                ),
            ),
            source="fixture",
        )
    return _Context(
        decision_frame=_DecisionFrame(
            recent_candles=(
                _candle(0, 100.0),
                _candle(1, 103.0),
                _candle(2, 106.0),
                _candle(3, 110.0),
            )
        ),
        market_evidence=market_evidence,
    )


def test_runtime_snapshot_derives_available_features_from_shared_context() -> None:
    snapshot = build_high_value_evidence_runtime_snapshot(_context(), as_of=NOW)

    assert snapshot.available_features == (
        "taker_flow_imbalance_proxy",
        "price_open_interest_relationship",
    )
    assert snapshot.taker_flow_imbalance is not None
    assert snapshot.taker_flow_imbalance.imbalance == 0.5
    assert snapshot.price_open_interest is not None
    assert snapshot.price_open_interest.state.value == "long_buildup"
    assert snapshot.unavailable_reasons == ()


def test_runtime_snapshot_is_fail_closed_when_market_evidence_is_absent() -> None:
    snapshot = build_high_value_evidence_runtime_snapshot(
        _context(evidence=False),
        as_of=NOW,
    )

    assert snapshot.available_features == ()
    assert snapshot.taker_flow_imbalance is None
    assert snapshot.price_open_interest is None
    assert snapshot.unavailable_reasons == (
        ("price_open_interest_relationship", "market_evidence_unavailable"),
        ("taker_flow_imbalance_proxy", "market_evidence_unavailable"),
    )


def test_runtime_payload_is_deterministic_and_explicit() -> None:
    payload = high_value_evidence_runtime_payload(
        build_high_value_evidence_runtime_snapshot(_context(), as_of=NOW)
    )

    assert payload["available_features"] == [
        "taker_flow_imbalance_proxy",
        "price_open_interest_relationship",
    ]
    assert payload["unavailable_reasons"] == []
    assert payload["taker_flow_imbalance_proxy"] == {
        "buy_volume": 75.0,
        "sell_volume": 25.0,
        "imbalance": 0.5,
        "sample_count": 1,
        "latest_captured_at": "2026-07-20T12:25:00+00:00",
        "source_label": "taker_flow_history_proxy",
    }
    relationship = payload["price_open_interest_relationship"]
    assert isinstance(relationship, dict)
    assert relationship["state"] == "long_buildup"
    assert relationship["source_labels"] == [
        "closed_candles",
        "open_interest_history",
    ]
