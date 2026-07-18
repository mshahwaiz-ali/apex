"""Render score meaning and target/horizon semantics for discovery output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    humanize_code,
    render_bullets,
    render_fields,
    render_section,
)
from apex.presentation.methodology_semantics_output import (
    render_discovery_analysis as _render_semantics_analysis,
)
from apex.presentation.methodology_semantics_output import (
    render_discovery_scan as _render_semantics_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
) -> str:
    """Render prior methodology sections plus score and horizon interpretation."""

    sections = [_render_semantics_analysis(payload, mode=mode)]
    score = _mapping(payload.get("methodology_score_semantics"))
    horizon = _mapping(payload.get("methodology_target_horizon_semantics"))

    if score:
        score_fields = (
            ("Displayed score", score.get("displayed_score")),
            ("Scale", humanize_code(score.get("score_scale"))),
            ("Execution conditions complete", _yes_no(score.get("execution_conditions_complete"))),
            ("Execution blocked", _yes_no(score.get("execution_blocked"))),
            ("Score authorizes execution", _yes_no(score.get("score_can_authorize_execution"))),
            ("Interpretation", score.get("interpretation")),
        )
        sections.append(render_section("Score Semantics", render_fields(score_fields)))
        limitations = _strings(score.get("limitations"))
        if limitations:
            sections.append(render_section("Score Limitations", render_bullets(limitations)))

    if horizon:
        horizon_fields = (
            ("Canonical targets", horizon.get("target_count")),
            (
                "Maximum projected move",
                _percentage(horizon.get("maximum_projected_move_percentage")),
            ),
            ("10%+ target supported", _yes_no(horizon.get("has_double_digit_target"))),
            ("Universal target applied", _yes_no(horizon.get("universal_target_applied"))),
            ("Target interpretation", horizon.get("target_interpretation")),
            ("Duration available", _yes_no(horizon.get("duration_available"))),
            ("Hold category", humanize_code(horizon.get("hold_category"))),
            ("Expected bars", horizon.get("expected_bars")),
            ("Setup expiry bars", horizon.get("setup_expiry_bars")),
            ("Duration interpretation", horizon.get("duration_interpretation")),
        )
        sections.append(
            render_section("Target and Horizon Semantics", render_fields(horizon_fields))
        )

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate score and target/horizon interpretation."""

    sections = [_render_semantics_scan(payload)]
    results = _mappings(payload.get("results"))
    score_available = 0
    score_execution_complete = 0
    double_digit_targets = 0
    duration_available = 0
    for item in results:
        score = _mapping(item.get("methodology_score_semantics"))
        horizon = _mapping(item.get("methodology_target_horizon_semantics"))
        score_available += score.get("available") is True
        score_execution_complete += score.get("execution_conditions_complete") is True
        double_digit_targets += horizon.get("has_double_digit_target") is True
        duration_available += horizon.get("duration_available") is True

    if results:
        fields = (
            ("Results with displayed scores", score_available),
            ("Results with complete execution geometry", score_execution_complete),
            ("Results with supported 10%+ targets", double_digit_targets),
            ("Results with canonical duration", duration_available),
            ("Interpretation", "targets and horizons are setup-derived, never universal"),
        )
        sections.append(render_section("Score and Horizon Summary", render_fields(fields)))
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


def _percentage(value: object) -> str:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"{float(value):.2f}%"
    return "Unavailable"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
