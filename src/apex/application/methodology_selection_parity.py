"""Compare shadow and enforced methodology selection outcomes."""

from __future__ import annotations

from dataclasses import dataclass

from apex.scoring.contracts import CandidateSelectionResult


def _selected_candidate_id(result: CandidateSelectionResult) -> str | None:
    selected = result.selected_candidate
    return None if selected is None else selected.scored.candidate_id


def _ranked_candidate_ids(result: CandidateSelectionResult) -> tuple[str, ...]:
    return tuple(item.scored.candidate_id for item in result.ranked_candidates)


@dataclass(frozen=True, slots=True)
class MethodologySelectionParityAudit:
    """Deterministic impact of methodology enforcement after candidate scoring."""

    shadow_selected_candidate_id: str | None
    enforced_selected_candidate_id: str | None
    shadow_ranked_candidate_ids: tuple[str, ...]
    enforced_ranked_candidate_ids: tuple[str, ...]
    selected_candidate_changed: bool
    ranking_changed: bool
    enforcement_removed_selection: bool
    enforcement_created_selection: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(set(self.shadow_ranked_candidate_ids)) != len(self.shadow_ranked_candidate_ids):
            raise ValueError("shadow ranked candidate identities must be unique")
        if len(set(self.enforced_ranked_candidate_ids)) != len(self.enforced_ranked_candidate_ids):
            raise ValueError("enforced ranked candidate identities must be unique")
        if not self.reason_codes:
            raise ValueError("selection parity audit requires reason codes")


def evaluate_methodology_selection_parity(
    shadow: CandidateSelectionResult,
    enforced: CandidateSelectionResult,
) -> MethodologySelectionParityAudit:
    """Compare post-scoring selection without changing either result."""

    if shadow.symbol != enforced.symbol:
        raise ValueError("selection parity requires matching symbols")
    if shadow.decision_time != enforced.decision_time:
        raise ValueError("selection parity requires matching decision times")

    shadow_selected = _selected_candidate_id(shadow)
    enforced_selected = _selected_candidate_id(enforced)
    shadow_ranked = _ranked_candidate_ids(shadow)
    enforced_ranked = _ranked_candidate_ids(enforced)
    selected_changed = shadow_selected != enforced_selected
    ranking_changed = shadow_ranked != enforced_ranked
    removed_selection = shadow_selected is not None and enforced_selected is None
    created_selection = shadow_selected is None and enforced_selected is not None

    if removed_selection:
        reason_codes = ("METHODOLOGY_ENFORCEMENT_REMOVED_SELECTION",)
    elif created_selection:
        reason_codes = ("METHODOLOGY_ENFORCEMENT_CREATED_SELECTION",)
    elif selected_changed:
        reason_codes = ("METHODOLOGY_ENFORCEMENT_CHANGED_SELECTION",)
    elif ranking_changed:
        reason_codes = ("METHODOLOGY_ENFORCEMENT_CHANGED_RANKING",)
    else:
        reason_codes = ("METHODOLOGY_SELECTION_PARITY",)

    return MethodologySelectionParityAudit(
        shadow_selected_candidate_id=shadow_selected,
        enforced_selected_candidate_id=enforced_selected,
        shadow_ranked_candidate_ids=shadow_ranked,
        enforced_ranked_candidate_ids=enforced_ranked,
        selected_candidate_changed=selected_changed,
        ranking_changed=ranking_changed,
        enforcement_removed_selection=removed_selection,
        enforcement_created_selection=created_selection,
        reason_codes=reason_codes,
    )


def methodology_selection_parity_payload(
    audit: MethodologySelectionParityAudit,
) -> dict[str, object]:
    """Serialize methodology selection impact for diagnostics."""

    return {
        "shadow_selected_candidate_id": audit.shadow_selected_candidate_id,
        "enforced_selected_candidate_id": audit.enforced_selected_candidate_id,
        "shadow_ranked_candidate_ids": list(audit.shadow_ranked_candidate_ids),
        "enforced_ranked_candidate_ids": list(audit.enforced_ranked_candidate_ids),
        "selected_candidate_changed": audit.selected_candidate_changed,
        "ranking_changed": audit.ranking_changed,
        "enforcement_removed_selection": audit.enforcement_removed_selection,
        "enforcement_created_selection": audit.enforcement_created_selection,
        "reason_codes": list(audit.reason_codes),
    }


__all__ = [
    "MethodologySelectionParityAudit",
    "evaluate_methodology_selection_parity",
    "methodology_selection_parity_payload",
]
