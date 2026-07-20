from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from apex.application.discovery_analysis import (
    _methodology_selection_parity_diagnostics,
)
from apex.application.methodology_selection_parity import (
    evaluate_methodology_selection_parity,
    methodology_selection_parity_payload,
)
from apex.scoring.contracts import (
    CandidateSelectionResult,
    ConflictSummary,
    DirectionalConsensus,
)

NOW = datetime(2026, 7, 20, tzinfo=UTC)


class _Scored:
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id


class _Ranked:
    def __init__(self, candidate_id: str, rank: int) -> None:
        self.scored = _Scored(candidate_id)
        self.rank = rank


def _result(
    *ranked_ids: str,
    selected_id: str | None,
    symbol: str = "BTCUSDT",
    decision_time: datetime = NOW,
) -> CandidateSelectionResult:
    ranked = tuple(
        _Ranked(candidate_id, rank) for rank, candidate_id in enumerate(ranked_ids, start=1)
    )
    selected = next(
        (item for item in ranked if item.scored.candidate_id == selected_id),
        None,
    )
    consensus = DirectionalConsensus.NONE
    return CandidateSelectionResult(
        symbol=symbol,
        decision_time=decision_time,
        all_scored_candidates=cast(
            Any,
            tuple(item.scored for item in ranked),
        ),
        ranked_candidates=cast(Any, ranked),
        rejected_candidates=(),
        conflict_summary=ConflictSummary(
            directional_consensus=consensus,
            long_count=0,
            short_count=0,
            duplicate_groups=(),
            warnings=(),
        ),
        directional_consensus=consensus,
        selected_candidate=cast(Any, selected),
        no_trade_reason=None if selected is not None else "no selection",
        evaluated_strategy_order=(),
        configuration_id="methodology-selection-parity-test",
        metadata={},
    )


def test_selection_parity_reports_no_change() -> None:
    shadow = _result("a", "b", selected_id="a")
    enforced = _result("a", "b", selected_id="a")

    audit = evaluate_methodology_selection_parity(shadow, enforced)

    assert audit.selected_candidate_changed is False
    assert audit.ranking_changed is False
    assert audit.reason_codes == ("METHODOLOGY_SELECTION_PARITY",)


def test_selection_parity_reports_replacement_selection() -> None:
    shadow = _result("a", "b", selected_id="a")
    enforced = _result("b", selected_id="b")

    payload = methodology_selection_parity_payload(
        evaluate_methodology_selection_parity(shadow, enforced)
    )

    assert payload["shadow_selected_candidate_id"] == "a"
    assert payload["enforced_selected_candidate_id"] == "b"
    assert payload["selected_candidate_changed"] is True
    assert payload["ranking_changed"] is True
    assert payload["enforcement_removed_selection"] is False
    assert payload["reason_codes"] == ["METHODOLOGY_ENFORCEMENT_CHANGED_SELECTION"]


def test_selection_parity_reports_removed_selection() -> None:
    shadow = _result("a", selected_id="a")
    enforced = _result(selected_id=None)

    audit = evaluate_methodology_selection_parity(shadow, enforced)

    assert audit.enforcement_removed_selection is True
    assert audit.enforcement_created_selection is False
    assert audit.reason_codes == ("METHODOLOGY_ENFORCEMENT_REMOVED_SELECTION",)


def test_selection_parity_rejects_mismatched_symbol() -> None:
    shadow = _result("a", selected_id="a")
    enforced = replace(shadow, symbol="ETHUSDT")

    with pytest.raises(ValueError, match="matching symbols"):
        evaluate_methodology_selection_parity(shadow, enforced)


def test_selection_parity_rejects_mismatched_decision_time() -> None:
    shadow = _result("a", selected_id="a")
    enforced = replace(
        shadow,
        decision_time=datetime(2026, 7, 20, 0, 1, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="matching decision times"):
        evaluate_methodology_selection_parity(shadow, enforced)


def test_live_shadow_mode_orients_selection_parity_correctly() -> None:
    shadow = _result("a", "b", selected_id="a")
    enforced = _result("b", selected_id="b")

    payload = _methodology_selection_parity_diagnostics(
        live_mode="shadow",
        live_selection=shadow,
        counterfactual_selection=enforced,
    )

    assert payload["shadow_selected_candidate_id"] == "a"
    assert payload["enforced_selected_candidate_id"] == "b"
    assert payload["selected_candidate_changed"] is True


def test_live_enforce_mode_orients_selection_parity_correctly() -> None:
    shadow = _result("a", "b", selected_id="a")
    enforced = _result("b", selected_id="b")

    payload = _methodology_selection_parity_diagnostics(
        live_mode="enforce",
        live_selection=enforced,
        counterfactual_selection=shadow,
    )

    assert payload["shadow_selected_candidate_id"] == "a"
    assert payload["enforced_selected_candidate_id"] == "b"
    assert payload["selected_candidate_changed"] is True


def test_live_selection_parity_rejects_unknown_mode() -> None:
    result = _result("a", selected_id="a")

    with pytest.raises(ValueError, match="shadow or enforce"):
        _methodology_selection_parity_diagnostics(
            live_mode="invalid",
            live_selection=result,
            counterfactual_selection=result,
        )
