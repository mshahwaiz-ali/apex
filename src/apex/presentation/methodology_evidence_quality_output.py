"""Render evidence independence and contradiction semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_usability_output import (
    render_discovery_analysis as _render_usability_analysis,
)
from apex.presentation.methodology_usability_output import (
    render_discovery_scan as _render_usability_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior methodology sections plus evidence quality truth."""

    sections = [_render_usability_analysis(payload, mode=mode)]
    independence = _mapping(payload.get("methodology_evidence_independence_semantics"))
    contradiction = _mapping(payload.get("methodology_contradiction_semantics"))

    if independence:
        fields = (
            ("Evidence observations", independence.get("evidence_count")),
            ("Evidence families", independence.get("family_count")),
            ("Independence groups", independence.get("independence_group_count")),
            ("Correlated observations", independence.get("correlated_observation_count")),
            ("Supporting families", independence.get("supporting_family_count")),
            ("Contradicting families", independence.get("contradicting_family_count")),
            (
                "Strongest support family",
                humanize_code(independence.get("strongest_support_family")),
            ),
            (
                "Strongest contradiction family",
                humanize_code(independence.get("strongest_contradiction_family")),
            ),
            ("Interpretation", independence.get("interpretation")),
        )
        sections.append(render_section("Evidence Independence", render_fields(fields)))
        limitations = _strings(independence.get("limitations"))
        if limitations:
            sections.append(render_section("Independence Limitations", render_bullets(limitations)))

    if contradiction:
        fields = (
            ("Contradiction count", contradiction.get("contradiction_count")),
            ("Maximum severity", contradiction.get("maximum_severity")),
            ("Average severity", contradiction.get("average_severity")),
            ("High-severity contradictions", contradiction.get("high_severity_count")),
            ("Affected families", contradiction.get("affected_families")),
            ("Execution blocked", _yes_no(contradiction.get("execution_blocked"))),
            ("Invalidation present", _yes_no(contradiction.get("invalidation_present"))),
            ("Interpretation", contradiction.get("interpretation")),
        )
        sections.append(render_section("Contradictions", render_fields(fields)))
        limitations = _strings(contradiction.get("limitations"))
        if limitations:
            sections.append(render_section("Contradiction Limitations", render_bullets(limitations)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate evidence independence and contradiction counts."""

    sections = [_render_usability_scan(payload)]
    results = _mappings(payload.get("results"))
    correlated = contradictions = high_severity = invalidated = 0
    for item in results:
        independence = _mapping(item.get("methodology_evidence_independence_semantics"))
        contradiction = _mapping(item.get("methodology_contradiction_semantics"))
        correlated += _integer(independence.get("correlated_observation_count")) > 0
        contradictions += _integer(contradiction.get("contradiction_count")) > 0
        high_severity += _integer(contradiction.get("high_severity_count")) > 0
        invalidated += contradiction.get("invalidation_present") is True

    if results:
        fields = (
            ("Results with correlated evidence", correlated),
            ("Results with contradictions", contradictions),
            ("Results with high-severity contradictions", high_severity),
            ("Results with explicit invalidation", invalidated),
            (
                "Interpretation",
                "correlated signals are capped and contradictions remain distinct from hard invalidation",
            ),
        )
        sections.append(render_section("Evidence Quality Summary", render_fields(fields)))
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
