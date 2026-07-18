"""Render confidence calibration and rejection semantics for discovery output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_discovery_output import (
    render_discovery_analysis as _render_methodology_analysis,
)
from apex.presentation.methodology_discovery_output import (
    render_discovery_scan as _render_methodology_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render methodology status plus confidence and rejection interpretation."""

    sections = [_render_methodology_analysis(payload, mode=mode)]
    confidence = _mapping(payload.get("methodology_confidence_semantics"))
    rejections = _mapping(payload.get("methodology_rejection_semantics"))

    if confidence:
        confidence_fields = (
            ("Available", _yes_no(confidence.get("available"))),
            ("Basis", humanize_code(confidence.get("basis"))),
            ("Historically calibrated", _yes_no(confidence.get("calibrated"))),
            ("Probability available", _yes_no(confidence.get("probability_available"))),
            ("Interpretation", confidence.get("interpretation")),
            ("Strongest support", confidence.get("strongest_support")),
            ("Strongest contradiction", confidence.get("strongest_contradiction")),
        )
        sections.append(render_section("Confidence Semantics", render_fields(confidence_fields)))
        missing = _strings(confidence.get("missing_evidence"))
        if missing:
            sections.append(
                render_section("Missing Confidence Evidence", render_bullets(missing))
            )

    if rejections:
        rejection_fields = (
            ("Execution blocked", _yes_no(rejections.get("execution_blocked"))),
            ("Quality reduced", _yes_no(rejections.get("quality_reduced"))),
            ("Hard blockers", rejections.get("hard_blocker_count")),
            ("Soft penalties", rejections.get("soft_penalty_count")),
            ("Total soft penalty", rejections.get("total_soft_penalty")),
            ("Interpretation", rejections.get("interpretation")),
        )
        sections.append(render_section("Rejection Semantics", render_fields(rejection_fields)))
        hard_blockers = _reason_lines(rejections.get("hard_blockers"))
        soft_penalties = _reason_lines(rejections.get("soft_penalties"))
        if hard_blockers:
            sections.append(render_section("Hard Blockers", render_bullets(hard_blockers)))
        if soft_penalties:
            sections.append(render_section("Soft Penalties", render_bullets(soft_penalties)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan groups; per-result cards carry confidence and rejection semantics."""

    return _render_methodology_scan(payload)


def _reason_lines(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    lines: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        code = humanize_code(item.get("code"))
        reason = item.get("reason")
        penalty = item.get("penalty")
        suffix = "" if not penalty else f" | penalty {penalty}"
        lines.append(f"{code}: {reason}{suffix}")
    return tuple(lines)


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


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
