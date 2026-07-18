"""Render authoritative actionability and canonical entry opportunity sets."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_execution_output import (
    render_discovery_analysis as _render_execution_analysis,
)
from apex.presentation.methodology_execution_output import (
    render_discovery_scan as _render_execution_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior methodology sections plus authoritative actionability."""

    sections = [_render_execution_analysis(payload, mode=mode)]
    actionability = _mapping(payload.get("methodology_actionability_semantics"))
    opportunities = _mapping(payload.get("methodology_entry_opportunity_semantics"))

    if actionability:
        fields = (
            ("Legacy status", humanize_code(actionability.get("legacy_status"))),
            ("Canonical maturity", humanize_code(actionability.get("canonical_maturity"))),
            ("Authoritative actionability", humanize_code(actionability.get("actionability"))),
            ("Execution ready", _yes_no(actionability.get("execution_ready"))),
            (
                "Legacy status authoritative",
                _yes_no(actionability.get("legacy_status_authoritative")),
            ),
            ("Interpretation", actionability.get("interpretation")),
        )
        sections.append(render_section("Actionability", render_fields(fields)))

    if opportunities:
        fields = (
            ("Canonical opportunities", opportunities.get("opportunity_count")),
            ("Primary opportunity", humanize_code(opportunities.get("primary_kind"))),
            ("Available kinds", opportunities.get("available_kinds")),
            ("Immediate available", _yes_no(opportunities.get("immediate_available"))),
            ("Aggressive available", _yes_no(opportunities.get("aggressive_available"))),
            ("Conditional available", _yes_no(opportunities.get("conditional_available"))),
            (
                "Multiple opportunities",
                _yes_no(opportunities.get("multiple_opportunities_available")),
            ),
            ("Interpretation", opportunities.get("interpretation")),
        )
        sections.append(render_section("Entry Opportunities", render_fields(fields)))
        lines = _opportunity_lines(opportunities.get("opportunities"))
        if lines:
            sections.append(render_section("Opportunity Geometry", render_bullets(lines)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with authoritative actionability counts."""

    sections = [_render_execution_scan(payload)]
    results = _mappings(payload.get("results"))
    actionability_counts: Counter[str] = Counter()
    multiple_opportunities = 0
    immediate_available = 0
    for item in results:
        actionability = _mapping(item.get("methodology_actionability_semantics"))
        opportunities = _mapping(item.get("methodology_entry_opportunity_semantics"))
        label = actionability.get("actionability")
        if label is not None:
            actionability_counts[str(label)] += 1
        multiple_opportunities += opportunities.get("multiple_opportunities_available") is True
        immediate_available += opportunities.get("immediate_available") is True

    if results:
        fields = (
            ("Authoritative actionability counts", dict(sorted(actionability_counts.items()))),
            ("Results with immediate canonical entry", immediate_available),
            ("Results with multiple canonical entries", multiple_opportunities),
            (
                "Interpretation",
                "legacy READY_NOW wording is compatibility metadata, not execution authority",
            ),
        )
        sections.append(render_section("Actionability Summary", render_fields(fields)))
    return "\n\n".join(section for section in sections if section)


def _opportunity_lines(value: object) -> tuple[str, ...]:
    lines: list[str] = []
    for item in _mappings(value):
        kind = humanize_code(item.get("kind"))
        zone = f"{item.get('zone_low')} - {item.get('zone_high')}"
        lines.append(
            f"{kind}: zone {zone}; ideal {item.get('ideal_entry')}; "
            f"max chase {item.get('maximum_chase')}; expiry {item.get('expiry_bars')} bars"
        )
    return tuple(lines)


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
