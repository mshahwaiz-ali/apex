"""Render selected-entry decision semantics without inventing selection authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    humanize_code,
    render_bullets,
    render_fields,
    render_section,
)
from apex.presentation.methodology_expiry_ranking_output import (
    render_discovery_analysis as _render_expiry_ranking_analysis,
)
from apex.presentation.methodology_expiry_ranking_output import (
    render_discovery_scan as _render_expiry_ranking_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
) -> str:
    """Render prior sections plus selected-entry decision truth."""

    sections = [_render_expiry_ranking_analysis(payload, mode=mode)]
    selection = _mapping(payload.get("methodology_selected_entry_semantics"))
    if selection:
        fields = (
            ("Opportunity count", selection.get("opportunity_count")),
            ("Selection available", _yes_no(selection.get("selection_available"))),
            (
                "Selection authoritative",
                _yes_no(selection.get("selection_authoritative")),
            ),
            ("Selected index", selection.get("selected_index")),
            ("Selected kind", humanize_code(selection.get("selected_kind"))),
            ("Currently executable", _yes_no(selection.get("currently_executable"))),
            (
                "Future trigger required",
                _yes_no(selection.get("future_trigger_required")),
            ),
            ("Required trigger", selection.get("required_trigger")),
            (
                "Aggressive alternative available",
                _yes_no(selection.get("aggressive_alternative_available")),
            ),
            (
                "Conditional alternative available",
                _yes_no(selection.get("conditional_alternative_available")),
            ),
            (
                "Better nearby alternative available",
                _yes_no(selection.get("better_nearby_alternative_available")),
            ),
            (
                "Maximum chase respected",
                _yes_no(selection.get("maximum_chase_respected")),
            ),
            ("Selection reason", selection.get("selection_reason")),
        )
        sections.append(render_section("Selected Entry Decision", render_fields(fields)))
        opportunity = _mapping(selection.get("selected_opportunity"))
        if opportunity:
            opportunity_fields = (
                ("Kind", humanize_code(opportunity.get("kind"))),
                ("Zone low", opportunity.get("zone_low")),
                ("Zone high", opportunity.get("zone_high")),
                ("Ideal entry", opportunity.get("ideal_entry")),
                ("Confirmation level", opportunity.get("confirmation_level")),
                ("Maximum chase", opportunity.get("maximum_chase")),
                ("Distance percentage", opportunity.get("current_distance_percentage")),
                ("Distance ATR", opportunity.get("current_distance_atr")),
                ("Quality", opportunity.get("quality")),
                ("Expiry bars", opportunity.get("expiry_bars")),
                ("Reason", opportunity.get("reason")),
            )
            sections.append(
                render_section("Selected Entry Geometry", render_fields(opportunity_fields))
            )
        limitations = _strings(selection.get("selection_limitations"))
        if limitations:
            sections.append(render_section("Selection Limitations", render_bullets(limitations)))
    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with selected-entry decision aggregates."""

    sections = [_render_expiry_ranking_scan(payload)]
    results = _mappings(payload.get("results"))
    selected = executable = conditional = ambiguous = 0
    for item in results:
        decision = _mapping(item.get("methodology_selected_entry_semantics"))
        selected += decision.get("selection_available") is True
        executable += decision.get("currently_executable") is True
        conditional += decision.get("future_trigger_required") is True
        ambiguous += (
            _integer(decision.get("opportunity_count")) > 1
            and decision.get("selection_available") is not True
        )

    if results:
        fields = (
            ("Results with unambiguous entry selection", selected),
            ("Results executable at selected entry", executable),
            ("Results requiring a future trigger", conditional),
            ("Results with ambiguous multiple entries", ambiguous),
            (
                "Interpretation",
                "multiple opportunities remain unselected unless the canonical model "
                "identifies one explicitly",
            ),
        )
        sections.append(render_section("Selected Entry Summary", render_fields(fields)))
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
