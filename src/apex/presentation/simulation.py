"""Trader-facing presentation for one current-setup futures simulation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_futures_simulation(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Explain one current-setup simulation payload without changing its schema."""

    output_mode = normalize_output_mode(mode)
    symbol = str(payload.get("symbol") or _nested(payload, "trade", "signal", "symbol") or UNAVAILABLE)
    title = render_title(f"Futures Setup Simulation — {symbol}")

    if "trade" not in payload:
        reasons = _sequence(payload.get("reasons"))
        sections = [
            title,
            render_section(
                "Simulation Decision",
                render_fields(
                    (
                        ("Setup available", "No"),
                        ("Simulation", humanize_code(payload.get("decision", "NO_BACKTEST"))),
                    )
                ),
            ),
            render_section(
                "Reason",
                render_bullets(reasons or ("No approved setup was available to simulate.",)),
            ),
        ]
        return "\n\n".join(sections)

    trade = _mapping(payload.get("trade"))
    signal = _mapping(trade.get("signal"))
    metrics = _mapping(payload.get("metrics"))
    metadata = _mapping(trade.get("metadata"))
    targets = _sequence(signal.get("target_prices"))
    partials = _sequence(signal.get("partial_close_percentages"))
    if not targets and signal.get("target_price") is not None:
        targets = (signal["target_price"],)

    target_lines = []
    for index, target in enumerate(targets, start=1):
        allocation = partials[index - 1] if index - 1 < len(partials) else None
        suffix = f" ({format_percentage(allocation)} close)" if allocation is not None else ""
        target_lines.append(f"TP{index}: {format_price(target)}{suffix}")

    sections = [
        title,
        render_section(
            "Setup",
            render_fields(
                (
                    ("Setup available", "Yes"),
                    ("Direction", humanize_code(signal.get("direction"))),
                    ("Strategy", humanize_code(signal.get("strategy"))),
                    ("Confidence", format_score(signal.get("confidence_score"))),
                    ("Entry", format_price(signal.get("entry_price"))),
                    ("Stop", format_price(signal.get("stop_price"))),
                )
            ),
        ),
        render_section("Targets", render_bullets(target_lines or (UNAVAILABLE,))),
        render_section(
            "Simulated Outcome",
            render_fields(
                (
                    ("Outcome", humanize_code(trade.get("outcome"))),
                    ("Exit price", format_price(trade.get("exit_price"))),
                    ("Holding period", _holding_period(trade.get("holding_candles"))),
                    ("Exit time", trade.get("exit_time") or UNAVAILABLE),
                    ("Exit reason", humanize_code(metadata.get("exit_reason") or trade.get("outcome"))),
                )
            ),
        ),
        render_section(
            "Performance",
            render_fields(
                (
                    ("Gross PnL", format_amount(trade.get("gross_pnl"))),
                    ("Fees", format_amount(trade.get("fees"))),
                    ("Net PnL", format_amount(trade.get("net_pnl"))),
                    ("Realized return", _return_text(trade, signal)),
                    ("Realized R", f"{format_ratio(trade.get('realized_r_multiple'))}R"),
                )
            ),
        ),
        render_section(
            "Risk Impact",
            render_fields(
                (
                    ("Modeled risk", format_amount(signal.get("risk_amount"))),
                    ("Quantity", format_ratio(signal.get("quantity"), decimals=6)),
                    ("Risk consumed", _risk_consumed(trade, signal)),
                )
            ),
        ),
    ]

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(
            render_section(
                "Simulation Assumptions",
                render_fields(
                    (
                        ("Slippage modeled", _metadata_value(metadata, "slippage_pct")),
                        ("Fee rate", _metadata_value(metadata, "fee_pct")),
                        ("Maximum holding candles", _metadata_value(metadata, "maximum_holding_candles")),
                        ("Conservative intrabar", _metadata_value(metadata, "conservative_intrabar")),
                        ("Total trades", metrics.get("total_trades", 1)),
                    )
                ),
            )
        )
    if output_mode is OutputMode.DEBUG and metadata:
        sections.append(
            render_section(
                "Diagnostics",
                render_fields((humanize_code(key), value) for key, value in sorted(metadata.items())),
            )
        )

    return "\n\n".join(sections)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(value)
    return ()


def _nested(payload: Mapping[str, object], *keys: str) -> object | None:
    current: object = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _holding_period(value: object) -> str:
    return f"{value} candles" if isinstance(value, int) else UNAVAILABLE


def _return_text(trade: Mapping[str, object], signal: Mapping[str, object]) -> str:
    net_pnl = trade.get("net_pnl")
    risk_amount = signal.get("risk_amount")
    if isinstance(net_pnl, int | float) and isinstance(risk_amount, int | float) and risk_amount:
        return format_percentage(float(net_pnl) / float(risk_amount), ratio=True)
    return UNAVAILABLE


def _risk_consumed(trade: Mapping[str, object], signal: Mapping[str, object]) -> str:
    net_pnl = trade.get("net_pnl")
    risk_amount = signal.get("risk_amount")
    if isinstance(net_pnl, int | float) and isinstance(risk_amount, int | float) and risk_amount:
        consumed = max(0.0, -float(net_pnl) / float(risk_amount))
        return format_percentage(consumed, ratio=True)
    return UNAVAILABLE


def _metadata_value(metadata: Mapping[str, object], key: str) -> object:
    value = metadata.get(key)
    if value is None:
        return UNAVAILABLE
    if key.endswith("_pct") and isinstance(value, int | float):
        return format_percentage(value)
    return humanize_code(value) if isinstance(value, bool) else value


__all__ = ["render_futures_simulation"]
