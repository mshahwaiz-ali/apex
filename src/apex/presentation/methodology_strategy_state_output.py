"""Render canonical market state and explicit strategy-fit semantics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from apex.presentation import OutputMode, humanize_code, render_fields, render_section
from apex.presentation.methodology_evidence_output import (
    render_discovery_analysis as _render_evidence_analysis,
)
from apex.presentation.methodology_evidence_output import (
    render_discovery_scan as _render_evidence_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
) -> str:
    """Render prior methodology sections plus market-state and strategy-fit truth."""

    sections = [_render_evidence_analysis(payload, mode=mode)]
    state = _mapping(payload.get("methodology_market_state_semantics"))
    fit = _mapping(payload.get("methodology_strategy_fit_semantics"))

    if state:
        state_fields: tuple[tuple[str, object], ...] = (
            ("Primary market state", humanize_code(state.get("primary_state"))),
            ("Secondary conditions", state.get("secondary_conditions")),
            ("State evidence count", state.get("evidence_count")),
            ("HTF conflict level", humanize_code(state.get("conflict_level"))),
            ("Mild HTF conflict", _yes_no(state.get("mild_htf_conflict"))),
            ("Strong HTF conflict", _yes_no(state.get("strong_htf_conflict"))),
            (
                "Direct structural opposition",
                _yes_no(state.get("direct_structural_opposition")),
            ),
            (
                "Execution blocked by conflict",
                _yes_no(state.get("execution_blocked_by_conflict")),
            ),
            ("Interpretation", state.get("interpretation")),
        )
        sections.append(render_section("Market State", render_fields(state_fields)))

    if fit:
        fit_fields: tuple[tuple[str, object], ...] = (
            ("Selected strategy", humanize_code(fit.get("selected_strategy"))),
            ("Primary state", humanize_code(fit.get("primary_state"))),
            ("Strategy-fit status", humanize_code(fit.get("fit_status"))),
            (
                "Explicit mismatch blocker",
                _yes_no(fit.get("explicit_mismatch_blocker")),
            ),
            (
                "Direct opposition blocker",
                _yes_no(fit.get("direct_opposition_blocker")),
            ),
            ("Mild conflict penalty", _yes_no(fit.get("mild_conflict_penalty"))),
            (
                "Eligibility matrix available",
                _yes_no(fit.get("eligibility_matrix_available")),
            ),
            ("Interpretation", fit.get("interpretation")),
        )
        sections.append(render_section("Strategy Fit", render_fields(fit_fields)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate market-state and strategy-fit verdicts."""

    sections = [_render_evidence_scan(payload)]
    results = _mappings(payload.get("results"))
    state_counts: Counter[str] = Counter()
    fit_counts: Counter[str] = Counter()
    conflict_blocked = 0
    for item in results:
        state = _mapping(item.get("methodology_market_state_semantics"))
        fit = _mapping(item.get("methodology_strategy_fit_semantics"))
        primary = state.get("primary_state")
        status = fit.get("fit_status")
        if primary is not None:
            state_counts[str(primary)] += 1
        if status is not None:
            fit_counts[str(status)] += 1
        conflict_blocked += state.get("execution_blocked_by_conflict") is True

    if results:
        fields = (
            ("Primary-state counts", dict(sorted(state_counts.items()))),
            ("Strategy-fit counts", dict(sorted(fit_counts.items()))),
            ("Results blocked by structural conflict", conflict_blocked),
            (
                "Interpretation",
                "absence of an explicit mismatch is not proof of full strategy eligibility",
            ),
        )
        sections.append(
            render_section("Market State and Strategy Fit Summary", render_fields(fields))
        )
    return "\n\n".join(section for section in sections if section)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _yes_no(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unavailable"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
