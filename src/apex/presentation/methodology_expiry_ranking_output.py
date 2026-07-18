"""Render setup expiry and candidate-ranking integrity semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_evidence_quality_output import (
    render_discovery_analysis as _render_evidence_quality_analysis,
)
from apex.presentation.methodology_evidence_quality_output import (
    render_discovery_scan as _render_evidence_quality_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior sections plus expiry and ranking-integrity truth."""

    sections = [_render_evidence_quality_analysis(payload, mode=mode)]
    expiry = _mapping(payload.get("methodology_expiry_semantics"))
    ranking = _mapping(payload.get("methodology_ranking_integrity_semantics"))

    if expiry:
        fields = (
            ("Setup expiry bars", expiry.get("setup_expiry_bars")),
            ("Minimum entry expiry bars", expiry.get("minimum_entry_expiry_bars")),
            ("Maximum entry expiry bars", expiry.get("maximum_entry_expiry_bars")),
            ("Expiry reason", expiry.get("expiry_reason")),
            ("Late or missed", _yes_no(expiry.get("late_or_missed"))),
            ("Structurally failed", _yes_no(expiry.get("structurally_failed"))),
            ("Elapsed bars available", _yes_no(expiry.get("elapsed_bars_available"))),
            ("Expired proven", _yes_no(expiry.get("expired_proven"))),
            ("Interpretation", expiry.get("interpretation")),
        )
        sections.append(render_section("Setup Expiry", render_fields(fields)))
        limitations = _strings(expiry.get("limitations"))
        if limitations:
            sections.append(render_section("Expiry Limitations", render_bullets(limitations)))

    if ranking:
        fields = (
            ("Ranking available", _yes_no(ranking.get("ranking_available"))),
            ("Ranked candidates", ranking.get("ranked_count")),
            ("Primary available", _yes_no(ranking.get("primary_available"))),
            ("Primary rank", ranking.get("primary_rank")),
            ("Primary rank score", ranking.get("primary_score")),
            ("Primary quality", humanize_code(ranking.get("primary_quality_label"))),
            ("Primary outcome", humanize_code(ranking.get("primary_outcome"))),
            ("Alternatives", ranking.get("alternative_count")),
            ("Rejected candidates", ranking.get("rejected_count")),
            ("Methodology executable", _yes_no(ranking.get("methodology_executable"))),
            ("Hard blockers", ranking.get("hard_blocker_count")),
            ("Rank authorizes execution", _yes_no(ranking.get("rank_authorizes_execution"))),
            ("Interpretation", ranking.get("interpretation")),
        )
        sections.append(render_section("Ranking Integrity", render_fields(fields)))
        limitations = _strings(ranking.get("limitations"))
        if limitations:
            sections.append(render_section("Ranking Limitations", render_bullets(limitations)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate expiry and ranking-integrity counts."""

    sections = [_render_evidence_quality_scan(payload)]
    results = _mappings(payload.get("results"))
    expired = late_or_missed = ranked_not_executable = blocker_over_rank = 0
    for item in results:
        expiry = _mapping(item.get("methodology_expiry_semantics"))
        ranking = _mapping(item.get("methodology_ranking_integrity_semantics"))
        expired += expiry.get("expired_proven") is True
        late_or_missed += expiry.get("late_or_missed") is True
        ranked_not_executable += (
            ranking.get("primary_available") is True
            and ranking.get("methodology_executable") is not True
        )
        blocker_over_rank += _integer(ranking.get("hard_blocker_count")) > 0

    if results:
        fields = (
            ("Results with proven expiry or failure", expired),
            ("Results marked late or missed", late_or_missed),
            ("Primary-ranked but not executable", ranked_not_executable),
            ("Results where blockers outrank score", blocker_over_rank),
            (
                "Interpretation",
                "rank orders candidates but never overrides expiry, hard blockers, or missing geometry",
            ),
        )
        sections.append(render_section("Expiry and Ranking Summary", render_fields(fields)))
    return "\n\n".join(section for section in sections if section)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _yes_no(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unavailable"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
