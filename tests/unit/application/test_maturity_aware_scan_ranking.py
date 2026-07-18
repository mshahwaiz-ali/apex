from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from apex.application.decision_analysis import _scan_sort_key
from apex.application.public_output import serialize_scan_result
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _analysis(
    symbol: str,
    *,
    strategy: StrategyType | None,
    status: EntryStatus | None,
    score: float,
    rank: int = 1,
) -> Any:
    setup = (
        None
        if strategy is None or status is None
        else SimpleNamespace(strategy=strategy, entry_status=status)
    )
    record = SimpleNamespace(final_rank_score=score, rank=rank)
    ranking = SimpleNamespace(primary=record, alternatives=(), rejected=())
    return SimpleNamespace(
        symbol=symbol,
        assessment=SimpleNamespace(setup=setup),
        candidate_ranking=ranking,
    )


def test_actionable_ranks_before_higher_scoring_developing_setup() -> None:
    actionable = _analysis(
        "ACTIONABLE",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.READY_NOW,
        score=70.0,
    )
    developing = _analysis(
        "DEVELOPING",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        status=EntryStatus.READY_NOW,
        score=99.0,
    )

    ranked = sorted((developing, actionable), key=_scan_sort_key)

    assert [item.symbol for item in ranked] == ["ACTIONABLE", "DEVELOPING"]


def test_maturity_classes_rank_developing_before_unavailable_before_no_trade() -> None:
    developing = _analysis(
        "DEVELOPING",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        status=EntryStatus.READY_NOW,
        score=10.0,
    )
    unavailable = _analysis(
        "UNAVAILABLE",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.LATE_OR_CHASING,
        score=99.0,
    )
    no_trade = _analysis(
        "NO_TRADE",
        strategy=None,
        status=None,
        score=100.0,
    )

    ranked = sorted((no_trade, unavailable, developing), key=_scan_sort_key)

    assert [item.symbol for item in ranked] == [
        "DEVELOPING",
        "UNAVAILABLE",
        "NO_TRADE",
    ]


def test_raw_phase5_ordering_is_preserved_within_same_maturity_class() -> None:
    higher_score = _analysis(
        "HIGHER_SCORE",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.READY_NOW,
        score=80.0,
        rank=2,
    )
    lower_score = _analysis(
        "LOWER_SCORE",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.READY_NOW,
        score=70.0,
        rank=1,
    )
    same_score_better_rank = _analysis(
        "BETTER_RANK",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.READY_NOW,
        score=80.0,
        rank=1,
    )

    ranked = sorted(
        (lower_score, higher_score, same_score_better_rank),
        key=_scan_sort_key,
    )

    assert [item.symbol for item in ranked] == [
        "BETTER_RANK",
        "HIGHER_SCORE",
        "LOWER_SCORE",
    ]
    assert higher_score.candidate_ranking.primary.final_rank_score == 80.0
    assert higher_score.candidate_ranking.primary.rank == 2


def test_best_actionable_is_execution_ready_after_maturity_aware_ordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actionable = _analysis(
        "ACTIONABLE",
        strategy=StrategyType.MOMENTUM_SCALP,
        status=EntryStatus.READY_NOW,
        score=70.0,
    )
    developing = _analysis(
        "DEVELOPING",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        status=EntryStatus.READY_NOW,
        score=99.0,
    )
    ranked = tuple(sorted((developing, actionable), key=_scan_sort_key))

    def _serialize(item: Any) -> dict[str, object]:
        execution_ready = item.symbol == "ACTIONABLE"
        return {
            "symbol": item.symbol,
            "setup": {},
            "decision": "LONG",
            "entry_status": "READY_NOW",
            "execution_ready": execution_ready,
            "result_group": "actionable" if execution_ready else "developing",
            "methodology_setup_maturity": {
                "maturity": "entry_available" if execution_ready else "confirmation_pending_close"
            },
        }

    monkeypatch.setattr("apex.application.public_output.serialize_symbol_analysis", _serialize)
    result = SimpleNamespace(
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
        analyses=ranked,
        failures={},
    )

    payload = serialize_scan_result(result)

    assert payload["best_overall"]["symbol"] == "ACTIONABLE"
    assert payload["best_actionable"]["symbol"] == "ACTIONABLE"
    assert payload["best_actionable"]["execution_ready"] is True
    assert payload["best_developing"]["symbol"] == "DEVELOPING"
