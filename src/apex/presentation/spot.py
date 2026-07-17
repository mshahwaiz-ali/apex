"""Trader-facing presentation for canonical spot workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_price,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_spot_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
    title: str = "Spot Analysis",
) -> str:
    """Render one canonical spot analysis or orchestration payload."""

    normalize_output_mode(mode)
    selected = _mapping(payload.get("selected_strategy"))
    planning = _mapping(payload.get("planning"))
    candidates = _mapping_sequence(payload.get("candidates"))
    symbol = _analysis_symbol(selected, candidates)
    sections = [render_title(f"{title} — {symbol}" if symbol else title)]

    if selected is None:
        sections.append(
            render_section(
                "Decision",
                render_fields(
                    (
                        ("Status", "No approved spot setup"),
                        ("Plan available", "No"),
                        ("Candidates reviewed", len(candidates)),
                    )
                ),
            )
        )
        reasons = _candidate_rejections(candidates)
        if reasons:
            sections.append(render_section("Why No Setup", render_bullets(reasons)))
    else:
        sections.append(render_section("Selected Strategy", _strategy_fields(selected)))
        evidence = _strings(selected.get("evidence"))
        if evidence:
            sections.append(render_section("Evidence", render_bullets(evidence)))
        if planning is not None:
            sections.extend(_planning_sections(planning))
        else:
            sections.append(
                render_section("Planning", render_fields((("Plan available", "No"),)))
            )

    sections.append(render_section("Candidate Review", _candidate_summary(candidates)))
    warnings = _strings(payload.get("warnings"))
    if warnings:
        sections.append(render_section("Research Warnings", render_bullets(warnings)))
    return "\n\n".join(sections)


def render_spot_plan(
    payload: Mapping[str, object], *, mode: str | OutputMode = "text"
) -> str:
    """Render one standalone bounded spot plan payload."""

    normalize_output_mode(mode)
    sections = [render_title("Spot Position Plan"), *_planning_sections(payload)]
    warnings = _strings(payload.get("warnings"))
    if warnings:
        sections.append(render_section("Research Warnings", render_bullets(warnings)))
    return "\n\n".join(sections)


def render_spot_scan(
    payload: Mapping[str, object], *, mode: str | OutputMode = "text"
) -> str:
    """Render ranked live spot scan results and eligibility outcomes."""

    normalize_output_mode(mode)
    ranked = _mapping_sequence(payload.get("ranked"))
    ineligible = _mapping_sequence(payload.get("ineligible"))
    failures = _mapping_sequence(payload.get("failures"))
    sections = [
        render_title("Spot Market Scan"),
        render_section(
            "Scan Summary",
            render_fields(
                (
                    ("Mode", humanize_code(payload.get("mode"))),
                    ("Ranked markets", len(ranked)),
                    ("Ineligible markets", len(ineligible)),
                    ("Failures", len(failures)),
                )
            ),
        ),
    ]
    if ranked:
        sections.append(render_section("Ranked Opportunities", render_bullets(_ranked_rows(ranked))))
    else:
        sections.append(render_section("Ranked Opportunities", "  No markets produced a plan."))
    if ineligible:
        sections.append(render_section("Ineligible", render_bullets(_ineligible_rows(ineligible))))
    if failures:
        sections.append(render_section("Failures", render_bullets(_failure_rows(failures))))
    return "\n\n".join(sections)


def _strategy_fields(strategy: Mapping[str, object]) -> str:
    return render_fields(
        (
            ("Decision", humanize_code(strategy.get("decision"))),
            ("Strategy", humanize_code(strategy.get("strategy"))),
            ("Eligibility", humanize_code(strategy.get("eligibility"))),
            ("Invalidation", format_price(strategy.get("invalidation_price"))),
            ("Thesis", strategy.get("thesis", UNAVAILABLE)),
        )
    )


def _planning_sections(planning: Mapping[str, object]) -> list[str]:
    entry = _mapping(planning.get("entry_plan")) or {}
    stop = _mapping(planning.get("stop_plan")) or {}
    position = _mapping(planning.get("position_plan")) or {}
    targets = _mapping(planning.get("target_plan")) or {}
    lifecycle = _mapping(planning.get("lifecycle")) or {}
    return [
        render_section("Entry Plan", _mapping_fields(entry)),
        render_section("Risk and Allocation", _mapping_fields({**stop, **position})),
        render_section("Targets", _mapping_fields(targets)),
        render_section("Lifecycle", _mapping_fields(lifecycle)),
    ]


def _candidate_summary(candidates: Sequence[Mapping[str, object]]) -> str:
    if not candidates:
        return "  No strategy candidates were produced."
    rows = [
        f"{humanize_code(item.get('strategy'))}: {humanize_code(item.get('decision'))}"
        for item in candidates
    ]
    return render_bullets(rows)


def _candidate_rejections(candidates: Sequence[Mapping[str, object]]) -> list[str]:
    reasons: list[str] = []
    for candidate in candidates:
        reasons.extend(_strings(candidate.get("rejection_reasons")))
    return list(dict.fromkeys(reasons))


def _ranked_rows(items: Sequence[Mapping[str, object]]) -> list[str]:
    rows: list[str] = []
    for item in items:
        analysis = _mapping(item.get("analysis")) or {}
        selected = _mapping(analysis.get("selected_strategy"))
        planning = _mapping(analysis.get("planning"))
        strategy = humanize_code(selected.get("strategy")) if selected else "No selection"
        rows.append(
            f"#{item.get('rank', UNAVAILABLE)} {item.get('symbol', UNAVAILABLE)} — "
            f"{strategy}; plan {'available' if planning else 'not available'}"
        )
    return rows


def _ineligible_rows(items: Sequence[Mapping[str, object]]) -> list[str]:
    return [
        f"{item.get('symbol', UNAVAILABLE)} — {humanize_code(item.get('eligibility_status'))}: "
        f"{', '.join(_strings(item.get('reason_codes'))) or UNAVAILABLE}"
        for item in items
    ]


def _failure_rows(items: Sequence[Mapping[str, object]]) -> list[str]:
    return [f"{item.get('symbol', UNAVAILABLE)} — {item.get('error', UNAVAILABLE)}" for item in items]


def _analysis_symbol(
    selected: Mapping[str, object] | None, candidates: Sequence[Mapping[str, object]]
) -> str | None:
    for item in ([selected] if selected is not None else []) + list(candidates):
        symbol = item.get("symbol")
        if isinstance(symbol, str) and symbol:
            return symbol
    return None


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _mapping_sequence(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return []
    return [str(item) for item in value]


def _mapping_fields(payload: Mapping[str, object]) -> str:
    if not payload:
        return render_fields((("Status", UNAVAILABLE),))
    return render_fields(
        (humanize_code(key), _display(value)) for key, value in sorted(payload.items())
    )


def _display(value: object) -> object:
    if isinstance(value, Mapping):
        return f"{len(value)} configured fields"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return ", ".join(str(item) for item in value) or UNAVAILABLE
    if isinstance(value, float):
        if "percentage" in str(value):
            return format_percentage(value)
        return format_amount(value)
    return value if value is not None else UNAVAILABLE


__all__ = ["render_spot_analysis", "render_spot_plan", "render_spot_scan"]
