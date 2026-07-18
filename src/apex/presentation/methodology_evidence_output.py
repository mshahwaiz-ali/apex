"""Render evidence freshness and confirmation-source semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_actionability_output import (
    render_discovery_analysis as _render_actionability_analysis,
)
from apex.presentation.methodology_actionability_output import (
    render_discovery_scan as _render_actionability_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior methodology sections plus evidence and confirmation truth."""

    sections = [_render_actionability_analysis(payload, mode=mode)]
    freshness = _mapping(payload.get("methodology_evidence_freshness_semantics"))
    confirmation = _mapping(payload.get("methodology_confirmation_source_semantics"))

    if freshness:
        fields = (
            ("Evidence count", freshness.get("evidence_count")),
            ("Freshness available", _yes_no(freshness.get("freshness_available"))),
            ("Minimum freshness", freshness.get("minimum_freshness")),
            ("Average freshness", freshness.get("average_freshness")),
            ("Stale evidence", freshness.get("stale_evidence_count")),
            ("Incomplete data blocked", _yes_no(freshness.get("incomplete_data_blocked"))),
            ("Interpretation", freshness.get("interpretation")),
        )
        sections.append(render_section("Evidence Freshness", render_fields(fields)))
        limitations = _strings(freshness.get("limitations"))
        if limitations:
            sections.append(render_section("Freshness Limitations", render_bullets(limitations)))

    if confirmation:
        fields = (
            ("Confirmation policy", humanize_code(confirmation.get("confirmation_policy"))),
            ("Close required", _yes_no(confirmation.get("close_required"))),
            ("Intrabar allowed", _yes_no(confirmation.get("intrabar_allowed"))),
            ("Confirmation complete", _yes_no(confirmation.get("confirmation_complete"))),
            ("Provisional signal", _yes_no(confirmation.get("provisional_signal"))),
            ("Closed candle proven", _yes_no(confirmation.get("closed_candle_proven"))),
            ("Interpretation", confirmation.get("interpretation")),
        )
        sections.append(render_section("Confirmation Source", render_fields(fields)))
        limitations = _strings(confirmation.get("limitations"))
        if limitations:
            sections.append(render_section("Confirmation Limitations", render_bullets(limitations)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with evidence freshness and confirmation counts."""

    sections = [_render_actionability_scan(payload)]
    results = _mappings(payload.get("results"))
    stale = provisional = close_pending = closed_proven = 0
    for item in results:
        freshness = _mapping(item.get("methodology_evidence_freshness_semantics"))
        confirmation = _mapping(item.get("methodology_confirmation_source_semantics"))
        stale += _integer(freshness.get("stale_evidence_count")) > 0
        provisional += confirmation.get("provisional_signal") is True
        close_pending += (
            confirmation.get("close_required") is True
            and confirmation.get("confirmation_complete") is not True
        )
        closed_proven += confirmation.get("closed_candle_proven") is True

    if results:
        fields = (
            ("Results with stale canonical evidence", stale),
            ("Results with provisional signals", provisional),
            ("Results awaiting required close", close_pending),
            ("Results with closed-candle proof", closed_proven),
            (
                "Interpretation",
                "active-candle evidence remains provisional unless canonical policy explicitly allows it",
            ),
        )
        sections.append(render_section("Evidence and Confirmation Summary", render_fields(fields)))
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
