"""Render execution geometry and structural invalidation semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_score_target_output import (
    render_discovery_analysis as _render_score_target_analysis,
)
from apex.presentation.methodology_score_target_output import (
    render_discovery_scan as _render_score_target_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior methodology sections plus execution and invalidation truth."""

    sections = [_render_score_target_analysis(payload, mode=mode)]
    geometry = _mapping(payload.get("methodology_execution_geometry_semantics"))
    invalidation = _mapping(payload.get("methodology_invalidation_semantics"))

    if geometry:
        geometry_fields = (
            ("Selected setup available", _yes_no(geometry.get("setup_available"))),
            ("Canonical entry available", _yes_no(geometry.get("canonical_entry_available"))),
            (
                "Canonical invalidation available",
                _yes_no(geometry.get("canonical_invalidation_available")),
            ),
            (
                "Compatibility entry visible",
                _yes_no(geometry.get("compatibility_entry_available")),
            ),
            (
                "Compatibility stop visible",
                _yes_no(geometry.get("compatibility_stop_available")),
            ),
            ("Execution ready", _yes_no(geometry.get("execution_ready"))),
            ("Geometry authoritative", _yes_no(geometry.get("geometry_authoritative"))),
            ("Interpretation", geometry.get("interpretation")),
        )
        sections.append(render_section("Execution Geometry", render_fields(geometry_fields)))
        limitations = _strings(geometry.get("limitations"))
        if limitations:
            sections.append(
                render_section("Execution Geometry Limitations", render_bullets(limitations))
            )

    if invalidation:
        invalidation_fields = (
            ("Canonical invalidation", _yes_no(invalidation.get("canonical_available"))),
            (
                "Compatibility stop price",
                _yes_no(invalidation.get("compatibility_price_available")),
            ),
            ("Invalidation price", invalidation.get("price")),
            ("Invalidation rule", humanize_code(invalidation.get("rule"))),
            ("Failure event", invalidation.get("failure_event")),
            (
                "Volatility buffer available",
                _yes_no(invalidation.get("volatility_buffer_available")),
            ),
            ("Slippage available", _yes_no(invalidation.get("slippage_available"))),
            ("Authoritative", _yes_no(invalidation.get("authoritative"))),
            ("Interpretation", invalidation.get("interpretation")),
        )
        sections.append(
            render_section("Structural Invalidation", render_fields(invalidation_fields))
        )
        limitations = _strings(invalidation.get("limitations"))
        if limitations:
            sections.append(
                render_section("Invalidation Limitations", render_bullets(limitations))
            )

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate execution-geometry truthfulness."""

    sections = [_render_score_target_scan(payload)]
    results = _mappings(payload.get("results"))
    canonical_entry = 0
    canonical_invalidation = 0
    compatibility_only = 0
    execution_ready = 0
    authoritative_geometry = 0
    for item in results:
        geometry = _mapping(item.get("methodology_execution_geometry_semantics"))
        has_entry = geometry.get("canonical_entry_available") is True
        has_invalidation = geometry.get("canonical_invalidation_available") is True
        canonical_entry += has_entry
        canonical_invalidation += has_invalidation
        compatibility_only += (
            geometry.get("compatibility_entry_available") is True
            and not (has_entry and has_invalidation)
        )
        execution_ready += geometry.get("execution_ready") is True
        authoritative_geometry += geometry.get("geometry_authoritative") is True

    if results:
        fields = (
            ("Results with canonical entry", canonical_entry),
            ("Results with canonical invalidation", canonical_invalidation),
            ("Compatibility-only geometry", compatibility_only),
            ("Execution-ready results", execution_ready),
            ("Authoritative geometry results", authoritative_geometry),
            (
                "Interpretation",
                "legacy prices remain visible, but only complete canonical geometry is executable",
            ),
        )
        sections.append(render_section("Execution Geometry Summary", render_fields(fields)))
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


def _yes_no(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unavailable"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
