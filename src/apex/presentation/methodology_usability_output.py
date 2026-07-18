"""Render market usability and timeframe coverage semantics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from apex.presentation import humanize_code, render_bullets, render_fields, render_section
from apex.presentation.methodology_strategy_state_output import (
    render_discovery_analysis as _render_strategy_state_analysis,
)
from apex.presentation.methodology_strategy_state_output import (
    render_discovery_scan as _render_strategy_state_scan,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: object = "text",
) -> str:
    """Render prior methodology sections plus usability and coverage truth."""

    sections = [_render_strategy_state_analysis(payload, mode=mode)]
    usability = _mapping(payload.get("methodology_market_usability_semantics"))
    coverage = _mapping(payload.get("methodology_timeframe_coverage_semantics"))

    if usability:
        fields = (
            ("Usability state", humanize_code(usability.get("state"))),
            ("Usability score", usability.get("score")),
            ("Execution usable", _yes_no(usability.get("execution_usable"))),
            ("Caution required", _yes_no(usability.get("caution_required"))),
            ("Execution blocked", _yes_no(usability.get("execution_blocked"))),
            ("Missing inputs", usability.get("missing_inputs")),
            ("Interpretation", usability.get("interpretation")),
        )
        sections.append(render_section("Market Usability", render_fields(fields)))
        reasons = _strings(usability.get("reasons"))
        warnings = _strings(usability.get("warnings"))
        limitations = _strings(usability.get("limitations"))
        if reasons:
            sections.append(render_section("Usability Reasons", render_bullets(reasons)))
        if warnings:
            sections.append(render_section("Usability Warnings", render_bullets(warnings)))
        if limitations:
            sections.append(render_section("Usability Limitations", render_bullets(limitations)))

    if coverage:
        fields = (
            ("Evaluated timeframes", coverage.get("evaluated_timeframes")),
            ("Regime timeframes", coverage.get("regime_timeframes")),
            ("Quality timeframes", coverage.get("quality_timeframes")),
            ("Missing regime frames", coverage.get("missing_regime_timeframes")),
            ("Missing quality frames", coverage.get("missing_quality_timeframes")),
            ("Stale timeframes", coverage.get("stale_timeframes")),
            ("Low-confidence timeframes", coverage.get("low_confidence_timeframes")),
            ("Complete coverage", _yes_no(coverage.get("complete_coverage"))),
            ("Degraded coverage", _yes_no(coverage.get("degraded_coverage"))),
            ("Interpretation", coverage.get("interpretation")),
        )
        sections.append(render_section("Timeframe Coverage", render_fields(fields)))
        limitations = _strings(coverage.get("limitations"))
        if limitations:
            sections.append(render_section("Coverage Limitations", render_bullets(limitations)))

    return "\n\n".join(section for section in sections if section)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render scan output with aggregate usability and timeframe coverage."""

    sections = [_render_strategy_state_scan(payload)]
    results = _mappings(payload.get("results"))
    usability_counts: Counter[str] = Counter()
    blocked = caution = incomplete_coverage = degraded_coverage = 0
    for item in results:
        usability = _mapping(item.get("methodology_market_usability_semantics"))
        coverage = _mapping(item.get("methodology_timeframe_coverage_semantics"))
        state = usability.get("state")
        if state is not None:
            usability_counts[str(state)] += 1
        blocked += usability.get("execution_blocked") is True
        caution += usability.get("caution_required") is True
        incomplete_coverage += coverage.get("complete_coverage") is not True
        degraded_coverage += coverage.get("degraded_coverage") is True

    if results:
        fields = (
            ("Market-usability counts", dict(sorted(usability_counts.items()))),
            ("Results blocked by usability", blocked),
            ("Results requiring execution caution", caution),
            ("Results with incomplete timeframe coverage", incomplete_coverage),
            ("Results with degraded timeframe coverage", degraded_coverage),
            (
                "Interpretation",
                "usability and coverage are prerequisites, not substitutes for setup quality",
            ),
        )
        sections.append(render_section("Usability and Coverage Summary", render_fields(fields)))
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
