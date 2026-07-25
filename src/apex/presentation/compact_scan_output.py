"""Compact confidence-ranked renderer for Apex market scans."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    humanize_code,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)
from apex.presentation.compact_analysis_output import _trade_card
from apex.presentation.scan_groups import flatten_existing_scan_groups


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _setup(item: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(item.get("setup")) or _mapping(item.get("developing_setup"))


def _ranking_score(item: Mapping[str, object]) -> tuple[float, float, float]:
    """Rank by displayed confidence, then overall quality and final rank score."""

    setup = _setup(item)
    quality = _mapping(setup.get("quality_dimensions"))
    return (
        _number(setup.get("confidence_score")) or float("-inf"),
        _number(quality.get("overall_trade_quality")) or float("-inf"),
        _number(item.get("final_score")) or float("-inf"),
    )


def _identity(item: Mapping[str, object]) -> tuple[str, str, str, str]:
    setup = _setup(item)
    entry = _mapping(setup.get("entry"))
    identity = setup.get("candidate_id") or item.get("candidate_id") or entry.get("preferred")
    return (
        str(item.get("symbol") or setup.get("symbol") or ""),
        str(setup.get("direction") or item.get("direction") or ""),
        str(setup.get("strategy") or item.get("strategy") or ""),
        str(identity),
    )


def _scan_items(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    seen: set[tuple[str, str, str, str]] = set()
    items: list[Mapping[str, object]] = []
    for item in flatten_existing_scan_groups(payload):
        identity = _identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        items.append(item)
    return tuple(items)


def _trade_items(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    items = (item for item in _scan_items(payload) if _setup(item))
    return tuple(sorted(items, key=_ranking_score, reverse=True))


def _no_trade_items(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    return tuple(item for item in _scan_items(payload) if not _setup(item))


def _summary(
    payload: Mapping[str, object],
    *,
    trade_count: int,
    no_trade_count: int,
) -> str:
    screening = _mapping(payload.get("screening"))
    failures = _mapping(payload.get("failures"))
    return render_section(
        "SCAN SUMMARY",
        render_fields(
            (
                (
                    "Markets discovered",
                    screening.get("total_contracts") or payload.get("attempted_symbol_count"),
                ),
                (
                    "Markets screened",
                    screening.get("candle_screened_count") or payload.get("attempted_symbol_count"),
                ),
                (
                    "Symbols shortlisted",
                    screening.get("shortlisted_count") or payload.get("attempted_symbol_count"),
                ),
                ("Symbols analyzed", payload.get("total_analysis_count")),
                ("Trade plans", trade_count),
                ("No valid setup", no_trade_count),
                ("Symbols failed", len(failures)),
                ("Ranking", "Highest published confidence first"),
            )
        ),
    )


def _no_trade_section(items: Sequence[Mapping[str, object]]) -> str:
    lines: list[str] = []
    for item in items:
        symbol = str(item.get("symbol") or "Unknown market")
        plan = _mapping(item.get("setup_plan"))
        reason = (
            plan.get("current_state")
            or item.get("primary_rejection_reason")
            or item.get("reason")
            or "No structurally valid setup"
        )
        lines.append(f"{symbol} — {humanize_code(reason)}")
    return render_section("NO VALID SETUP", render_bullets(lines))


def _display_limit_section(payload: Mapping[str, object]) -> str:
    displayed = _number(payload.get("displayed_symbol_count"))
    total = _number(payload.get("total_analysis_count"))
    if displayed is None or total is None or displayed >= total:
        return ""
    return render_section(
        "DISPLAY LIMIT",
        render_bullets(
            (
                f"Showing {int(displayed)} of {int(total)} analyzed symbols.",
                "Use --output json for the complete structured record.",
            )
        ),
    )


def render_compact_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render one globally ranked sequence of analyze-style trade cards."""

    trades = _trade_items(payload)
    no_trades = _no_trade_items(payload)
    sections = [render_title("Apex Market Scan")]
    sections.append(
        _summary(
            payload,
            trade_count=len(trades),
            no_trade_count=len(no_trades),
        )
    )

    generated_at = payload.get("generated_at")
    sections.extend(
        _trade_card(
            item,
            index=index,
            symbol=str(item.get("symbol") or _setup(item).get("symbol") or "Unknown market"),
            generated_at=item.get("generated_at") or generated_at,
            explain=explain,
        )
        for index, item in enumerate(trades, start=1)
    )

    if no_trades:
        sections.append(_no_trade_section(no_trades))
    display_limit = _display_limit_section(payload)
    if display_limit:
        sections.append(display_limit)
    return "\n\n".join(section for section in sections if section)


__all__ = ["render_compact_scan"]
