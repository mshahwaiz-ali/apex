"""Trader-facing futures scanner presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_price,
    format_score,
    humanize_code,
    normalize_output_mode,
    render_fields,
    render_section,
    render_title,
)
from apex.presentation.futures import render_futures_analysis


def render_futures_scan(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one serialized scanner payload without changing scanner decisions."""

    output_mode = normalize_output_mode(mode)
    results = _mappings(payload.get("results"))
    failures = _mapping(payload.get("failures"))
    approved = tuple(item for item in results if _is_approved(item))
    no_trade = tuple(item for item in results if not _is_approved(item))

    sections = [render_title("Apex Futures Scan")]
    sections.append(
        render_section(
            "Scan Summary",
            render_fields(
                (
                    ("Risk mode", humanize_code(payload.get("risk_mode"))),
                    ("Markets analyzed", len(results)),
                    ("Actionable setups", len(approved)),
                    ("No-trade markets", len(no_trade)),
                    ("Failures", len(failures)),
                )
            ),
        )
    )

    if approved:
        sections.append(_render_ranked_setups(approved))
    else:
        sections.append(
            render_section(
                "Actionable Setups",
                "  None. Directional bias may still exist, but no executable entry passed the current rules.",
            )
        )

    sections.append(_render_market_cards(results, output_mode))
    if failures:
        sections.append(_render_failures(failures))
    return "\n\n".join(section for section in sections if section)


def _render_ranked_setups(results: Sequence[Mapping[str, object]]) -> str:
    lines: list[str] = []
    for rank, item in enumerate(results, start=1):
        entry_zone = _mapping(item.get("entry_zone"))
        lines.append(
            f"  {rank}. {item.get('symbol', 'Unknown')} — "
            f"{humanize_code(item.get('decision'))} | "
            f"{humanize_code(item.get('strategy'))} | "
            f"score {format_score(item.get('confidence_score'))} | "
            f"entry {_price_range(entry_zone.get('low'), entry_zone.get('high'))}"
        )
    return render_section("Actionable Setups", lines)


def _render_market_cards(
    results: Sequence[Mapping[str, object]],
    mode: OutputMode,
) -> str:
    if not results:
        return render_section("Markets", "  No market results were returned.")
    cards = [render_futures_analysis(item, mode=mode) for item in results]
    separator = "\n\n" + "═" * 56 + "\n\n"
    return render_section("Markets", separator.join(cards))


def _render_failures(failures: Mapping[str, object]) -> str:
    lines = [f"  - {symbol}: {reason}" for symbol, reason in failures.items()]
    return render_section("Failures", lines)


def _is_approved(payload: Mapping[str, object]) -> bool:
    return str(payload.get("decision") or "NO_TRADE").upper() != "NO_TRADE"


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _price_range(low: object, high: object) -> str:
    if low is None and high is None:
        return "Unavailable"
    if low is None:
        return format_price(high)
    if high is None:
        return format_price(low)
    return f"{format_price(low)}–{format_price(high)}"


__all__ = ["render_futures_scan"]
