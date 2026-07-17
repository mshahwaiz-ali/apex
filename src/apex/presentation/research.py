"""Trader-facing presentation for research and historical validation workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_ratio,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_backtest(payload: Mapping[str, object], *, mode: str | OutputMode = "text") -> str:
    """Render one chronological backtest report."""

    normalize_output_mode(mode)
    metrics = _mapping(payload.get("metrics")) or {}
    metadata = _mapping(payload.get("metadata")) or {}
    failures = _mapping(payload.get("failures")) or {}
    diagnostics = _mapping(payload.get("diagnostics")) or {}
    sections = [
        render_title(f"Historical Backtest — {payload.get('symbol', UNAVAILABLE)}"),
        render_section(
            "Run Summary",
            render_fields(
                (
                    ("Risk mode", humanize_code(payload.get("risk_mode"))),
                    ("Dataset", payload.get("dataset_source", UNAVAILABLE)),
                    ("Replay timeframe", metadata.get("replay_timeframe", UNAVAILABLE)),
                    ("Decisions", payload.get("decision_count", UNAVAILABLE)),
                    ("Approved", payload.get("approved_count", UNAVAILABLE)),
                    ("Skipped", payload.get("skipped_count", UNAVAILABLE)),
                    ("Failures", payload.get("failure_count", len(failures))),
                )
            ),
        ),
        render_section("Performance", _metric_fields(metrics)),
    ]
    if failures:
        sections.append(render_section("Failures", render_bullets(_mapping_rows(failures))))
    if diagnostics:
        sections.append(
            render_section("Execution Diagnostics", _diagnostic_summary(diagnostics))
        )
    if metadata:
        sections.append(render_section("Metadata", _mapping_fields(metadata)))
    return "\n\n".join(sections)


def render_campaign(payload: Mapping[str, object], *, mode: str | OutputMode = "text") -> str:
    """Render one chronological campaign payload."""

    normalize_output_mode(mode)
    variants = _variant_items(payload)
    sections = [
        render_title("Historical Backtest Campaign"),
        render_section(
            "Campaign Summary",
            render_fields(
                (
                    ("Campaign", payload.get("campaign_id", payload.get("run_id", UNAVAILABLE))),
                    ("Risk mode", humanize_code(payload.get("risk_mode"))),
                    ("Dataset", payload.get("dataset_source", UNAVAILABLE)),
                    ("Variants", len(variants)),
                )
            ),
        ),
    ]
    if variants:
        sections.append(render_section("Variant Results", render_bullets(_variant_rows(variants))))
    else:
        sections.append(render_section("Variant Results", "  No campaign variants were returned."))
    sections.append(render_section("Campaign Details", _mapping_fields(payload)))
    return "\n\n".join(sections)


def render_comparison(payload: Mapping[str, object], *, mode: str | OutputMode = "text") -> str:
    """Render comparison data from two saved backtest reports."""

    normalize_output_mode(mode)
    sections = [
        render_title("Backtest Comparison"),
        render_section("Comparison", _mapping_fields(payload)),
    ]
    return "\n\n".join(sections)


def render_edge_report(
    report: Mapping[str, object],
    *,
    output_path: object,
    mode: str | OutputMode = "text",
) -> str:
    """Render one historical futures edge report summary."""

    normalize_output_mode(mode)
    sections = [
        render_title("Historical Futures Edge Report"),
        render_section(
            "Report Summary",
            render_fields(
                (
                    ("Campaign", report.get("campaign_id", UNAVAILABLE)),
                    ("Trades", report.get("trade_count", UNAVAILABLE)),
                    ("Profiles", report.get("profile_count", UNAVAILABLE)),
                    ("Report ID", report.get("report_id", UNAVAILABLE)),
                    ("Output", output_path),
                )
            ),
        ),
    ]
    sections.append(render_section("Report Details", _mapping_fields(report)))
    return "\n\n".join(sections)


def render_edge_validation(
    report: Mapping[str, object],
    *,
    output_path: object,
    mode: str | OutputMode = "text",
) -> str:
    """Render one out-of-sample historical edge validation summary."""

    normalize_output_mode(mode)
    sections = [
        render_title("Historical Edge Validation"),
        render_section(
            "Validation Summary",
            render_fields(
                (
                    ("Campaign", report.get("campaign_id", UNAVAILABLE)),
                    ("Segments", report.get("segment_count", UNAVAILABLE)),
                    (
                        "Validated out-of-sample",
                        report.get("validated_out_of_sample_count", UNAVAILABLE),
                    ),
                    ("Report ID", report.get("report_id", UNAVAILABLE)),
                    ("Output", output_path),
                )
            ),
        ),
    ]
    sections.append(render_section("Validation Details", _mapping_fields(report)))
    return "\n\n".join(sections)


def render_dataset_export(
    payload: Mapping[str, object],
    *,
    output_path: object,
    mode: str | OutputMode = "text",
) -> str:
    """Render historical dataset export completion."""

    normalize_output_mode(mode)
    candles = _sequence(payload.get("candles"))
    sections = [
        render_title("Historical Dataset Export"),
        render_section(
            "Export Summary",
            render_fields(
                (
                    ("Symbol", payload.get("symbol", UNAVAILABLE)),
                    ("Source", payload.get("source", UNAVAILABLE)),
                    ("Closed candles", len(candles)),
                    ("Output", output_path),
                )
            ),
        ),
    ]
    timeframes = sorted(
        {
            str(item.get("timeframe"))
            for item in candles
            if isinstance(item, Mapping) and item.get("timeframe") is not None
        }
    )
    sections.append(
        render_section(
            "Dataset Details",
            render_fields((("Timeframes", ", ".join(timeframes) or UNAVAILABLE),)),
        )
    )
    return "\n\n".join(sections)


def _metric_fields(metrics: Mapping[str, object]) -> str:
    preferred = (
        "trade_count",
        "win_rate",
        "net_return_percentage",
        "total_return_percentage",
        "expectancy",
        "expectancy_r",
        "profit_factor",
        "maximum_drawdown_percentage",
        "max_drawdown_percentage",
        "liquidation_count",
    )
    fields: list[tuple[str, object]] = []
    for key in preferred:
        if key not in metrics:
            continue
        fields.append((humanize_code(key), _format_metric(key, metrics[key])))
    return render_fields(fields) if fields else _mapping_fields(metrics)


def _format_metric(key: str, value: object) -> object:
    if "percentage" in key or key == "win_rate":
        return format_percentage(value)
    if "factor" in key or key.endswith("_r"):
        return format_ratio(value)
    if isinstance(value, float):
        return format_amount(value)
    return value


def _diagnostic_summary(diagnostics: Mapping[str, object]) -> str:
    fields: list[tuple[str, object]] = []
    for key, value in sorted(diagnostics.items()):
        if isinstance(value, Mapping):
            fields.append((humanize_code(key), len(value)))
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
            fields.append((humanize_code(key), len(value)))
        else:
            fields.append((humanize_code(key), value))
    return render_fields(fields)


def _variant_items(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    for key in ("variants", "results", "runs", "campaign_results"):
        items = _mapping_sequence(payload.get(key))
        if items:
            return items
    return []


def _variant_rows(items: Sequence[Mapping[str, object]]) -> list[str]:
    rows: list[str] = []
    for index, item in enumerate(items, start=1):
        identifier = item.get("variant_id", item.get("id", item.get("name", index)))
        metrics = _mapping(item.get("metrics")) or _mapping(item.get("report")) or item
        trades = metrics.get("trade_count", item.get("trade_count", UNAVAILABLE))
        profit_factor = metrics.get("profit_factor", UNAVAILABLE)
        expectancy = metrics.get("expectancy_r", metrics.get("expectancy", UNAVAILABLE))
        rows.append(
            f"{identifier} — trades {trades}; profit factor {format_ratio(profit_factor)}; "
            f"expectancy {format_ratio(expectancy)}"
        )
    return rows


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _sequence(value: object) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return []
    return list(value)


def _mapping_sequence(value: object) -> list[Mapping[str, object]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _mapping_rows(value: Mapping[str, object]) -> list[str]:
    return [f"{humanize_code(key)}: {item}" for key, item in sorted(value.items())]


def _mapping_fields(value: Mapping[str, object]) -> str:
    if not value:
        return render_fields((("Status", UNAVAILABLE),))
    fields = []
    for key, item in sorted(value.items()):
        if isinstance(item, Mapping):
            display: object = f"{len(item)} fields"
        elif isinstance(item, Sequence) and not isinstance(item, str | bytes):
            display = f"{len(item)} items"
        else:
            display = item
        fields.append((humanize_code(key), display))
    return render_fields(fields)


__all__ = [
    "render_backtest",
    "render_campaign",
    "render_comparison",
    "render_dataset_export",
    "render_edge_report",
    "render_edge_validation",
]
