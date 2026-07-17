"""Canonical text presentation for Stage 3 discovery output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    normalize_cli_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one canonical discovery result."""

    normalize_cli_output_mode(mode)
    symbol = str(payload.get("symbol") or "Unknown symbol")
    setup = _mapping(payload.get("setup"))
    if not setup:
        reasons = _strings(payload.get("reasons"))
        sections = [render_title(f"{symbol} — No Trade")]
        sections.append(
            render_section(
                "Assessment",
                render_fields(
                    (
                        ("Status", "No trade"),
                        ("Reason", reasons[0] if reasons else "No defensible setup was selected"),
                        ("Candidates evaluated", payload.get("candidate_count")),
                    )
                ),
            )
        )
        return "\n\n".join(sections)

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    policies = _mappings(setup.get("management_policies"))
    direction = humanize_code(setup.get("direction"))
    sections = [render_title(f"{symbol} — {direction} Setup")]
    sections.append(
        render_section(
            "Selected Setup",
            render_fields(
                (
                    ("Group", humanize_code(payload.get("result_group"))),
                    ("Status", humanize_code(setup.get("entry_status"))),
                    ("Direction", direction),
                    ("Strategy", humanize_code(setup.get("strategy"))),
                    ("Confidence", format_score(setup.get("confidence_score"))),
                )
            ),
        )
    )
    trade_fields: list[tuple[str, object]] = [
        ("Current price", format_price(entry.get("current_price"))),
        ("Entry zone", _price_range(entry.get("lower"), entry.get("upper"))),
        ("Preferred entry", format_price(entry.get("preferred"))),
        ("Maximum chase", format_price(entry.get("maximum_chase_price"))),
        ("Structural stop", format_price(stop.get("price"))),
        ("Stop distance", f"{stop.get('distance_pct', 0):.2f}%"),
        ("Stop quality", humanize_code(stop.get("quality_band"))),
    ]
    for index, target in enumerate(targets[:3], start=1):
        trade_fields.append(
            (
                f"TP{index}",
                f"{format_price(target.get('price'))} | "
                f"{format_ratio(target.get('risk_reward'))} | "
                f"close {target.get('partial_close_pct', 0):g}%",
            )
        )
    sections.append(render_section("Trade Plan", render_fields(trade_fields)))

    if policies:
        policy_lines = [
            f"{humanize_code(item.get('kind'))}: {item.get('action')} "
            f"when {item.get('trigger')}"
            for item in policies
        ]
        sections.append(render_section("Trade Management", render_bullets(policy_lines)))

    warnings = _strings(setup.get("warnings"))
    if warnings:
        sections.append(render_section("Warnings", render_bullets(warnings)))
    return "\n\n".join(sections)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render ranked canonical scan output grouped by actionability."""

    actionable = _mappings(payload.get("actionable_setups"))
    developing = _mappings(payload.get("developing_setups"))
    unavailable = _mappings(payload.get("unavailable_setups"))
    no_trade = _mappings(payload.get("no_trade_results"))
    sections = [render_title("Apex Futures Scan")]
    sections.append(
        render_section(
            "Scan Summary",
            render_fields(
                (
                    ("Markets analyzed", payload.get("total_analysis_count")),
                    ("Displayed candidates", payload.get("displayed_analysis_count")),
                    ("Selected setups", payload.get("selected_setup_count")),
                    ("Actionable now", payload.get("actionable_count")),
                    ("Developing", payload.get("developing_count")),
                    ("Unavailable", payload.get("unavailable_count")),
                    ("No trade", payload.get("no_trade_count")),
                    ("Long candidates", payload.get("long_candidate_count")),
                    ("Short candidates", payload.get("short_candidate_count")),
                    ("Status counts", payload.get("status_counts")),
                )
            ),
        )
    )
    sections.extend(
        section
        for section in (
            _render_group("Actionable Setups", actionable),
            _render_group("Developing Setups", developing),
            _render_group("Late or Invalidated", unavailable),
            _render_group("No Trade", no_trade),
        )
        if section
    )
    return "\n\n".join(sections)


def _render_group(title: str, results: Sequence[Mapping[str, object]]) -> str:
    if not results:
        return ""
    cards = [render_discovery_analysis(item) for item in results]
    separator = "\n\n" + "═" * 56 + "\n\n"
    return render_section(title, separator.join(cards))


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


def _price_range(low: object, high: object) -> str:
    if low is None and high is None:
        return "Unavailable"
    if low is None:
        return format_price(high)
    if high is None:
        return format_price(low)
    return f"{format_price(low)} – {format_price(high)}"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]