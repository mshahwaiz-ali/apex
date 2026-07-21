"""Deterministic, dependency-free terminal presentation primitives for Apex."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from math import isfinite
from textwrap import wrap

UNAVAILABLE = "Unavailable"
DEFAULT_SEPARATOR_WIDTH = 78
CONTENT_WIDTH = 74


class OutputMode(StrEnum):
    """Supported CLI output modes."""

    TEXT = "text"
    JSON = "json"


def normalize_cli_output_mode(value: str | OutputMode) -> OutputMode:
    """Normalize the active user-facing CLI output surface."""

    if isinstance(value, OutputMode):
        return value

    normalized = value.strip().lower()
    try:
        return OutputMode(normalized)
    except ValueError as exc:
        raise ValueError("CLI output mode must be one of: text, json") from exc


_LABELS: dict[str, str] = {
    "AGGRESSIVE_NOW": "Aggressive now",
    "BEARISH": "Bearish",
    "BULLISH": "Bullish",
    "CANDIDATE_REJECTED": "Setup did not meet quality requirements",
    "ENVIRONMENT_BLOCKED": "Market conditions blocked trading",
    "FAILED_BREAKOUT_DOWN": "Failed downside breakout",
    "FAILED_BREAKOUT_UP": "Failed upside breakout",
    "INVALIDATED": "Setup invalidated",
    "LATE_OR_CHASING": "Late or chasing",
    "LONG": "Long",
    "NEUTRAL": "Neutral",
    "NO_CANDIDATE_GENERATED": "No valid setup formed",
    "NO_ROUTED_STRATEGY": "No suitable strategy matched current conditions",
    "NO_TRADE": "No trade",
    "PULLBACK_PREFERRED": "Pullback preferred",
    "RANGE": "Range",
    "READY_NOW": "Ready now",
    "SHORT": "Short",
    "STRONGLY_BEARISH": "Strongly bearish",
    "STRONGLY_BULLISH": "Strongly bullish",
    "UNSTABLE": "Unstable",
    "WATCH_NEAR_ENTRY": "Watch near entry",
    "WEAKLY_BEARISH": "Weakly bearish",
    "WEAKLY_BULLISH": "Weakly bullish",
}

_WARNING_LABELS: dict[str, str] = {
    "ENVIRONMENT_TRADEABLE": "Market environment is tradeable",
    "EXTENSION_WARNING": "Price is extended from its normal trading area",
    "HIGHER_TIMEFRAME_BIAS_STRONGLY_BEARISH": "Higher timeframes are strongly bearish",
    "HIGHER_TIMEFRAME_BIAS_STRONGLY_BULLISH": "Higher timeframes are strongly bullish",
    "HIGH_TIMEFRAME_EXTENSION_WARNING": "Higher-timeframe price action is extended",
    "INPUT_COMPLETE": "Required market inputs are complete",
    "PRIMARY_REGIME_FAILED_BREAKOUT_DOWN": "Primary condition is a failed downside breakout",
    "PRIMARY_REGIME_FAILED_BREAKOUT_UP": "Primary condition is a failed upside breakout",
}


def humanize_code(value: object, *, labels: Mapping[str, str] | None = None) -> str:
    """Convert an enum or machine code into stable human-readable text."""

    if value is None:
        return UNAVAILABLE
    raw_value = getattr(value, "value", value)
    text = str(raw_value).strip()
    if not text:
        return UNAVAILABLE
    key = text.upper().replace("-", "_").replace(" ", "_")
    mapping = _LABELS if labels is None else labels
    known = mapping.get(key)
    if known is not None:
        return known
    return key.replace("_", " ").lower().capitalize()


def humanize_warning(value: object) -> str:
    """Translate one warning code without losing unknown warnings."""

    return humanize_code(value, labels=_WARNING_LABELS)


def humanize_warnings(values: Iterable[object]) -> tuple[str, ...]:
    """Translate, deduplicate, and preserve warning order."""

    translated: list[str] = []
    seen: set[str] = set()
    for value in values:
        warning = humanize_warning(value)
        if warning in seen:
            continue
        seen.add(warning)
        translated.append(warning)
    return tuple(translated)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if isfinite(number) else None


def format_amount(value: object, *, currency: str | None = None, decimals: int = 2) -> str:
    """Format a monetary amount while handling missing and invalid values."""

    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    rendered = f"{number:,.{decimals}f}"
    return f"{rendered} {currency.strip()}" if currency and currency.strip() else rendered


def format_price(value: object, *, decimals: int | None = None) -> str:
    """Format a market price with adaptive readable precision.

    Explicit ``decimals`` remains authoritative for exchange-aware callers.
    Without it, the terminal uses stable magnitude-based readability while
    preserving the original numeric value everywhere outside text rendering.
    """

    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE

    precision = decimals
    if precision is None:
        absolute = abs(number)
        if absolute >= 100:
            precision = 2
        elif absolute >= 1:
            precision = 3
        elif absolute >= 0.1:
            precision = 4
        elif absolute >= 0.01:
            precision = 5
        elif absolute >= 0.001:
            precision = 6
        else:
            precision = 8
    return f"{number:,.{precision}f}"


def format_percentage(value: object, *, ratio: bool = False, decimals: int = 1) -> str:
    """Format a percentage supplied either as percent units or a decimal ratio."""

    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    percentage = number * 100.0 if ratio else number
    return f"{percentage:.{decimals}f}%"


def format_score(value: object, *, decimals: int = 1) -> str:
    """Format a normalized score."""

    number = _finite_number(value)
    return UNAVAILABLE if number is None else f"{number:.{decimals}f}"


def format_ratio(value: object, *, decimals: int = 2) -> str:
    """Format a risk/reward or other scalar ratio."""

    number = _finite_number(value)
    return UNAVAILABLE if number is None else f"{number:.{decimals}f}"


def render_title(title: str, *, width: int = DEFAULT_SEPARATOR_WIDTH) -> str:
    """Render a prominent terminal banner."""

    clean_title = title.strip()
    inner_width = max(width - 2, len(clean_title) + 4)
    label = f" {clean_title.upper()} "
    remaining = max(0, inner_width - len(label))
    left = remaining // 2
    right = remaining - left
    return "\n".join(
        (
            f"╭{'─' * left}{label}{'─' * right}╮",
            f"╰{'─' * inner_width}╯",
        )
    )


def render_section(title: str, body: str | Iterable[str]) -> str:
    """Render one clearly separated terminal section."""

    lines = body.splitlines() if isinstance(body, str) else [str(line) for line in body]
    clean_lines = [line.rstrip() for line in lines if line is not None]
    label = f"┌─ {title.strip()} "
    header = label + "─" * max(1, DEFAULT_SEPARATOR_WIDTH - len(label))
    return "\n".join((header, *clean_lines, "└" + "─" * 77))


def render_fields(
    fields: Iterable[tuple[str, object]],
    *,
    indent: int = 2,
    unavailable: str = UNAVAILABLE,
) -> str:
    """Render aligned label/value fields with stable indentation."""

    normalized = [
        (str(label).strip(), unavailable if value is None else str(value))
        for label, value in fields
    ]
    if not normalized:
        return ""
    label_width = max(len(label) for label, _ in normalized)
    prefix = " " * max(indent, 0)
    lines: list[str] = []
    value_width = max(24, CONTENT_WIDTH - len(prefix) - label_width - 3)
    continuation = " " * (len(prefix) + label_width + 2)
    for label, value in normalized:
        wrapped = wrap(
            value,
            width=value_width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        lines.append(f"{prefix}{label.ljust(label_width)}  {wrapped[0]}")
        lines.extend(f"{continuation}{line}" for line in wrapped[1:])
    return "\n".join(lines)


def render_bullets(values: Iterable[object], *, indent: int = 2) -> str:
    """Render a deterministic bullet list."""

    prefix = " " * max(indent, 0)
    lines: list[str] = []
    width = max(24, CONTENT_WIDTH - len(prefix) - 2)
    for value in values:
        wrapped = wrap(
            str(value),
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        lines.append(f"{prefix}• {wrapped[0]}")
        lines.extend(f"{prefix}  {line}" for line in wrapped[1:])
    return "\n".join(lines)


__all__ = [
    "CONTENT_WIDTH",
    "DEFAULT_SEPARATOR_WIDTH",
    "UNAVAILABLE",
    "OutputMode",
    "format_amount",
    "format_percentage",
    "format_price",
    "format_ratio",
    "format_score",
    "humanize_code",
    "humanize_warning",
    "humanize_warnings",
    "normalize_cli_output_mode",
    "render_bullets",
    "render_fields",
    "render_section",
    "render_title",
]
