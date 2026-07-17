"""Deterministic, dependency-free terminal presentation primitives for Apex."""

from __future__ import annotations

from enum import StrEnum
from math import isfinite
from typing import Iterable, Mapping

UNAVAILABLE = "Unavailable"
DEFAULT_SEPARATOR_WIDTH = 40


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
    "AGGRESSIVE": "Aggressive",
    "APPROACHING_ENTRY": "Approaching entry",
    "AUTOMATIC": "Automatic",
    "BEARISH": "Bearish",
    "BULLISH": "Bullish",
    "CANDIDATE_REJECTED": "Setup did not meet quality requirements",
    "ENVIRONMENT_BLOCKED": "Market conditions blocked trading",
    "EXTREME": "Extreme",
    "FAILED_BREAKOUT_DOWN": "Failed downside breakout",
    "FAILED_BREAKOUT_UP": "Failed upside breakout",
    "INVALIDATED": "Setup invalidated",
    "ISOLATED": "Isolated",
    "LONG": "Long",
    "MANUAL": "Manual",
    "MISSED_ENTRY": "Entry already missed",
    "NEUTRAL": "Neutral",
    "NO_CANDIDATE_GENERATED": "No valid setup formed",
    "NO_ROUTED_STRATEGY": "No suitable strategy matched current conditions",
    "NO_TRADE": "No trade",
    "NORMAL": "Normal",
    "RANGE": "Range",
    "READY_NOW": "Ready now",
    "SHORT": "Short",
    "STANDARD": "Standard",
    "STRONGLY_BEARISH": "Strongly bearish",
    "STRONGLY_BULLISH": "Strongly bullish",
    "UNSTABLE": "Unstable",
    "WAIT_FOR_RECLAIM": "Wait for reclaim",
    "WAIT_FOR_RETEST": "Wait for retest",
    "WATCH": "Watch",
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
    """Format a market price with useful precision and no scientific notation."""

    number = _finite_number(value)
    if number is None:
        return UNAVAILABLE
    precision = decimals
    if precision is None:
        absolute = abs(number)
        if absolute >= 1_000:
            precision = 2
        elif absolute >= 1:
            precision = 4
        elif absolute >= 0.01:
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
    """Render a top-level title and deterministic separator."""

    clean_title = title.strip()
    return f"{clean_title}\n{'─' * max(width, len(clean_title))}"


def render_section(title: str, body: str | Iterable[str]) -> str:
    """Render one titled terminal section."""

    lines = body.splitlines() if isinstance(body, str) else [str(line) for line in body]
    clean_lines = [line.rstrip() for line in lines if line is not None]
    return "\n".join((title.strip(), *clean_lines))


def render_fields(
    fields: Iterable[tuple[str, object]],
    *,
    indent: int = 2,
    unavailable: str = UNAVAILABLE,
) -> str:
    """Render aligned label/value fields with stable indentation."""

    normalized = [(str(label).strip(), unavailable if value is None else str(value)) for label, value in fields]
    if not normalized:
        return ""
    label_width = max(len(label) for label, _ in normalized)
    prefix = " " * max(indent, 0)
    return "\n".join(
        f"{prefix}{label.ljust(label_width)}: {value}" for label, value in normalized
    )


def render_bullets(values: Iterable[object], *, indent: int = 2) -> str:
    """Render a deterministic bullet list."""

    prefix = " " * max(indent, 0)
    return "\n".join(f"{prefix}- {value}" for value in values)


__all__ = [
    "DEFAULT_SEPARATOR_WIDTH",
    "OutputMode",
    "UNAVAILABLE",
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
