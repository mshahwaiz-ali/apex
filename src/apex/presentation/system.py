"""Trader-facing presentation for Apex system and market-data commands."""

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


def render_ticker(payload: Mapping[str, object], *, mode: str | OutputMode = "text") -> str:
    """Render one normalized ticker snapshot."""

    normalize_output_mode(mode)
    bid = _number(payload.get("bid_price"))
    ask = _number(payload.get("ask_price"))
    spread = ask - bid if bid is not None and ask is not None else None
    midpoint = (ask + bid) / 2 if bid is not None and ask is not None else None
    spread_pct = spread / midpoint * 100 if spread is not None and midpoint else None
    sections = [
        render_title(f"Market Ticker — {payload.get('symbol', UNAVAILABLE)}"),
        render_section(
            "Current Market",
            render_fields(
                (
                    ("Last price", format_price(payload.get("last_price"))),
                    ("Best bid", format_price(payload.get("bid_price"))),
                    ("Best ask", format_price(payload.get("ask_price"))),
                    ("Spread", format_price(spread)),
                    ("Spread percentage", _format_spread_percentage(spread_pct)),
                    ("24h quote volume", format_amount(payload.get("quote_volume_24h"))),
                )
            ),
        ),
        render_section(
            "Snapshot",
            render_fields(
                (
                    ("Provider", humanize_code(payload.get("source"))),
                    ("Captured at", payload.get("captured_at", UNAVAILABLE)),
                )
            ),
        ),
    ]
    return "\n\n".join(sections)


def render_candles(
    payload: Sequence[Mapping[str, object]],
    *,
    mode: str | OutputMode = "text",
) -> str:
    """Render a concise OHLCV candle summary with optional detailed rows."""

    normalize_output_mode(mode)
    if not payload:
        return "\n\n".join(
            (
                render_title("Market Candles"),
                render_section("Result", render_fields((("Candles returned", 0),))),
            )
        )
    first = payload[0]
    last = payload[-1]
    closes = [_number(item.get("close")) for item in payload]
    valid_closes = [value for value in closes if value is not None]
    change_pct = None
    if len(valid_closes) >= 2 and valid_closes[0]:
        change_pct = (valid_closes[-1] / valid_closes[0] - 1) * 100
    sections = [
        render_title(f"Market Candles — {last.get('symbol', UNAVAILABLE)}"),
        render_section(
            "Dataset",
            render_fields(
                (
                    ("Timeframe", last.get("timeframe", UNAVAILABLE)),
                    ("Candles returned", len(payload)),
                    ("First open", first.get("open_time", UNAVAILABLE)),
                    ("Latest close", last.get("close_time", UNAVAILABLE)),
                    ("Provider", humanize_code(last.get("source"))),
                )
            ),
        ),
        render_section(
            "Latest Candle",
            render_fields(
                (
                    ("Open", format_price(last.get("open"))),
                    ("High", format_price(last.get("high"))),
                    ("Low", format_price(last.get("low"))),
                    ("Close", format_price(last.get("close"))),
                    ("Volume", format_amount(last.get("volume"))),
                    ("Closed", humanize_code(last.get("is_closed"))),
                    ("Period change", format_percentage(change_pct)),
                )
            ),
        ),
    ]
    rows = [
        f"{item.get('close_time', UNAVAILABLE)} | O {format_price(item.get('open'))} | "
        f"H {format_price(item.get('high'))} | L {format_price(item.get('low'))} | "
        f"C {format_price(item.get('close'))} | V {format_amount(item.get('volume'))}"
        for item in payload
    ]
    sections.append(render_section("Candles", render_bullets(rows)))
    return "\n\n".join(sections)


def render_config(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
    provider: str = "binance",
) -> str:
    """Render resolved configuration without exposing machine-style JSON by default."""

    normalize_output_mode(mode)
    sections = [
        render_title("Apex Configuration"),
        render_section(
            "Validation",
            render_fields(
                (
                    ("Status", "Valid"),
                    ("Environment", humanize_code(payload.get("environment"))),
                    ("Provider", humanize_code(provider)),
                    ("Analysis timeframes", _join(payload.get("analysis_timeframes"))),
                    ("Data directory", payload.get("data_dir", UNAVAILABLE)),
                )
            ),
        ),
    ]
    sections.append(render_section("Resolved Settings", _mapping_fields(payload)))
    return "\n\n".join(sections)


def render_smoke(payload: Mapping[str, object]) -> str:
    """Render the minimal application bootstrap result."""

    return "\n\n".join(
        (
            render_title("Apex System Check"),
            render_section(
                "Status",
                render_fields(
                    (
                        ("Application", "Ready" if payload.get("status") == "ok" else "Failed"),
                        ("Version", payload.get("version", UNAVAILABLE)),
                        ("Environment", humanize_code(payload.get("environment"))),
                    )
                ),
            ),
        )
    )


def render_version(version: str) -> str:
    """Render installed version information."""

    return "\n".join((render_title("Apex Trading Agent"), render_fields((("Version", version),))))


def _mapping_fields(payload: Mapping[str, object]) -> str:
    return render_fields((humanize_code(key), _display(value)) for key, value in sorted(payload.items()))


def _display(value: object) -> object:
    if isinstance(value, Mapping):
        return f"{len(value)} configured entries"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return ", ".join(str(item) for item in value) or UNAVAILABLE
    return value if value is not None else UNAVAILABLE


def _join(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return ", ".join(str(item) for item in value) or UNAVAILABLE
    return UNAVAILABLE if value is None else str(value)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _format_spread_percentage(value: float | None) -> str:
    if value is None:
        return UNAVAILABLE
    if abs(value) < 0.01:
        decimals = 6
    elif abs(value) < 0.1:
        decimals = 4
    else:
        decimals = 2
    return format_percentage(value, decimals=decimals)


__all__ = [
    "render_candles",
    "render_config",
    "render_smoke",
    "render_ticker",
    "render_version",
]
