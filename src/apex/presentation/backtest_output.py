"""Readable chronological backtest and research-campaign reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    UNAVAILABLE,
    format_percentage,
    format_ratio,
    render_fields,
    render_section,
    render_title,
)


def render_backtest(payload: Mapping[str, object]) -> str:
    """Render a single-symbol chronological replay report."""

    metrics = _mapping(payload.get("metrics"))
    promotion = _mapping(payload.get("promotion_statistics"))
    study = _mapping(payload.get("study"))
    symbol = str(payload.get("symbol") or "Unknown market")
    trades = _number(metrics.get("total_trades"))
    expectancy = _number(metrics.get("expectancy"))
    verdict = _verdict(trades, expectancy)
    sections = [
        render_title(f"Apex Backtest • {symbol}"),
        render_section(
            "Verdict",
            "\n".join(
                (
                    f"▶  {verdict}",
                    render_fields(
                        (
                            ("Replay timeframe", payload.get("replay_timeframe")),
                            ("Decision points", payload.get("decision_point_count")),
                            ("Signals generated", payload.get("generated_signal_count")),
                            ("Trades executed", metrics.get("total_trades")),
                            ("No-trade decisions", payload.get("no_trade_decision_count")),
                        )
                    ),
                )
            ),
        ),
        render_section(
            "Performance after modeled costs",
            render_fields(
                (
                    ("Win rate", format_percentage(metrics.get("win_rate"), ratio=True)),
                    ("Expectancy", _r(expectancy)),
                    ("Net P&L", _signed(metrics.get("net_profit"))),
                    ("Profit factor", format_ratio(metrics.get("profit_factor"))),
                    ("Average win", _signed(metrics.get("average_win"))),
                    ("Average loss", _signed(metrics.get("average_loss"))),
                    ("Maximum drawdown", _signed(metrics.get("maximum_drawdown"))),
                )
            ),
        ),
        render_section(
            "Robustness checks",
            render_fields(
                (
                    ("Calibration authority", "Not promoted"),
                    (
                        "Deflated Sharpe probability",
                        format_percentage(promotion.get("deflated_sharpe_probability"), ratio=True),
                    ),
                    (
                        "Backtest overfitting risk",
                        format_percentage(
                            promotion.get("probability_backtest_overfitting"), ratio=True
                        ),
                    ),
                    ("Skipped signals", study.get("skipped_signal_count")),
                    ("Dataset fingerprint", _short_hash(study.get("dataset_hash"))),
                )
            ),
        ),
    ]
    return "\n\n".join(sections)


def render_campaign(payload: Mapping[str, object]) -> str:
    """Render a public-data campaign status report."""

    months = payload.get("months")
    month_values = (
        [str(item) for item in months]
        if isinstance(months, Sequence) and not isinstance(months, str | bytes)
        else []
    )
    missing = _number(payload.get("missing_file_count")) or 0.0
    training = payload.get("model_training")
    training_status = (
        "Not requested"
        if training == "not requested"
        else "Completed; inspect JSON report for promotion gates"
    )
    return "\n\n".join(
        (
            render_title("Apex Historical Research Campaign"),
            render_section(
                "Campaign status",
                "\n".join(
                    (
                        f"▶  {'COMPLETE WITH MISSING DATA' if missing else 'COMPLETE'}",
                        render_fields(
                            (
                                ("UTC range", _range(month_values)),
                                ("Complete months", len(month_values)),
                                ("Unique symbols", payload.get("symbol_count")),
                                ("Verified files", payload.get("verified_file_count")),
                                ("Missing files", payload.get("missing_file_count")),
                            )
                        ),
                    )
                ),
            ),
            render_section(
                "Artifacts",
                render_fields(
                    (
                        ("Manifest", payload.get("manifest")),
                        ("Manifest fingerprint", _short_hash(payload.get("manifest_hash"))),
                        ("Model training", training_status),
                        ("Probability authority", "Withheld until every promotion gate passes"),
                    )
                ),
            ),
        )
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _r(value: float | None) -> str:
    return UNAVAILABLE if value is None else f"{value:+.3f}R"


def _signed(value: object) -> str:
    number = _number(value)
    return UNAVAILABLE if number is None else f"{number:+,.4f}"


def _short_hash(value: object) -> str:
    text = str(value or "")
    return f"{text[:12]}…" if len(text) > 12 else text or UNAVAILABLE


def _range(months: Sequence[str]) -> str:
    if not months:
        return UNAVAILABLE
    return months[0] if len(months) == 1 else f"{months[0]} → {months[-1]}"


def _verdict(trades: float | None, expectancy: float | None) -> str:
    if not trades:
        return "INSUFFICIENT EXECUTED TRADES — NO PERFORMANCE CONCLUSION"
    if expectancy is None:
        return "RESULT AVAILABLE — EXPECTANCY UNAVAILABLE"
    if expectancy > 0:
        return "POSITIVE SAMPLE — NOT YET PROOF OF FUTURE PERFORMANCE"
    return "NEGATIVE SAMPLE — STRATEGY DID NOT SHOW AN EDGE"


__all__ = ["render_backtest", "render_campaign"]
