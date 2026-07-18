"""Tests for evidence-first futures screening policy."""

from types import SimpleNamespace

from apex.application.futures_screening import _lane_budgets
from apex.domain.futures_screening import FuturesDiscoveryLane, FuturesDiscoveryLaneSignal


def _ranked_item(symbol: str, lane: FuturesDiscoveryLane, score: float) -> tuple[object, ...]:
    return (
        SimpleNamespace(exchange_symbol=symbol),
        object(),
        object(),
        SimpleNamespace(total=score),
        (
            FuturesDiscoveryLaneSignal(
                lane=lane,
                score=score,
                reason=f"{lane.value} evidence",
            ),
        ),
    )


def test_dynamic_lane_budgets_follow_observed_lane_evidence() -> None:
    ranked = (
        *(
            _ranked_item(f"TREND{index}USDT", FuturesDiscoveryLane.TREND_CONTINUATION, 90.0)
            for index in range(5)
        ),
        _ranked_item("DEVELOPINGUSDT", FuturesDiscoveryLane.DEVELOPING, 20.0),
    )

    budgets = _lane_budgets(ranked, limit=4)

    assert (
        budgets[FuturesDiscoveryLane.TREND_CONTINUATION] > budgets[FuturesDiscoveryLane.DEVELOPING]
    )
    assert sum(budgets.values()) == 4
