"""Methodology-aware text facade for discovery analysis and scan output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.discovery_output import (
    render_discovery_analysis as _render_base_analysis,
)
from apex.presentation.discovery_output import render_discovery_scan as _render_base_scan


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render the base trade plan plus methodology maturity and projection status."""

    sections = [_render_base_analysis(payload, mode=mode)]
    methodology = _mapping(payload.get("methodology_setup_maturity"))
    completeness = _mapping(payload.get("methodology_completeness"))
    projection_notice = payload.get("methodology_projection_notice")
    fields: list[tuple[str, object]] = []

    if methodology:
        fields.extend(
            (
                ("Maturity", humanize_code(methodology.get("maturity"))),
                (
                    "Confirmation policy",
                    humanize_code(methodology.get("confirmation_policy")),
                ),
                (
                    "Execution conditions complete",
                    _yes_no(methodology.get("execution_conditions_complete")),
                ),
            )
        )
    if completeness:
        fields.extend(
            (
                ("Methodology fields available", _coverage(completeness)),
                (
                    "Native methodology fields",
                    completeness.get("native_field_count"),
                ),
            )
        )
    if payload.get("methodology_projection_authoritative") is not None:
        fields.append(
            (
                "Methodology authority",
                "Native" if payload.get("methodology_projection_authoritative") is True else "Projected",
            )
        )
    if projection_notice:
        fields.append(("Projection note", projection_notice))

    if fields:
        sections.append(render_section("Methodology Status", render_fields(fields)))

    unavailable = _strings(completeness.get("unavailable_fields"))
    if unavailable:
        sections.append(
            render_section(
                "Deferred Methodology Fields",
                render_bullets(humanize_code(item) for item in unavailable),
            )
        )
    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render grouped scan results with methodology coverage diagnostics."""

    sections = [_render_base_scan(payload)]
    fields = (
        (
            "Native methodology results",
            payload.get("methodology_authoritative_result_count"),
        ),
        (
            "Projected methodology results",
            payload.get("methodology_projected_result_count"),
        ),
        (
            "Common unavailable fields",
            payload.get("methodology_unavailable_field_counts"),
        ),
        (
            "Coverage meaning",
            payload.get("methodology_coverage_interpretation"),
        ),
    )
    if any(value is not None for _, value in fields):
        sections.append(render_section("Methodology Coverage", render_fields(fields)))
    return "\n\n".join(section for section in sections if section)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _yes_no(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unavailable"


def _coverage(completeness: Mapping[str, object]) -> str:
    available = completeness.get("available_field_count")
    total = completeness.get("field_count")
    if available is None or total is None:
        return "Unavailable"
    return f"{available}/{total}"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
