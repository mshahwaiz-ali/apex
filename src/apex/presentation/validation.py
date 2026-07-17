"""Operator-facing presentation for validation, evidence, and readiness workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_percentage,
    format_ratio,
    humanize_code,
    normalize_cli_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_validation(
    payload: Mapping[str, object],
    *,
    title: str = "Validation Readiness",
    mode: str | OutputMode = "text",
) -> str:
    """Render one validation, evidence, or readiness payload."""

    normalize_cli_output_mode(mode)
    report = _mapping(payload.get("report")) or payload
    daily = _mapping(payload.get("daily_history"))
    record = _mapping(payload.get("record"))
    if record is not None:
        report = _mapping(record.get("report")) or report

    sections = [
        render_title(title),
        render_section("Status", _status_fields(report, payload)),
    ]

    reasons = _reason_values(report)
    if reasons:
        sections.append(render_section("Blocking Reasons", render_bullets(reasons)))

    evidence = _mapping(payload.get("evidence")) or _mapping(report.get("evidence"))
    if evidence:
        sections.append(render_section("Evidence", _mapping_fields(evidence)))

    history = daily or record
    if history:
        sections.append(render_section("History", _history_fields(history, payload)))

    shortfalls = _mapping(payload.get("strategy_sample_shortfalls"))
    if daily is not None:
        shortfalls = _mapping(daily.get("strategy_sample_shortfalls")) or shortfalls
    if shortfalls:
        sections.append(render_section("Strategy Sample Shortfalls", render_bullets(_mapping_rows(shortfalls))))

    sections.append(render_section("Validation Details", _mapping_fields(report)))
    return "\n\n".join(sections)


def render_evidence_bundle(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = "text",
) -> str:
    """Render one setup-specific evidence bundle."""

    normalize_cli_output_mode(mode)
    dimensions = _mapping(payload.get("dimensions")) or {}
    sections = [
        render_title("Evidence Bundle"),
        render_section(
            "Bundle Summary",
            render_fields(
                (
                    ("Status", humanize_code(_first(payload, "status", "eligibility", "decision"))),
                    ("Setup", _first(payload, "setup_id", "segment_id", "profile_id")),
                    ("Dimensions", len(dimensions)),
                    ("Historical evidence", _presence(payload, "historical_validation", "historical")),
                    ("Forward evidence", _presence(payload, "forward_validation", "forward")),
                )
            ),
        ),
    ]
    if dimensions:
        sections.append(render_section("Setup Dimensions", _mapping_fields(dimensions)))
    reasons = _reason_values(payload)
    if reasons:
        sections.append(render_section("Evidence Gaps", render_bullets(reasons)))
    sections.append(render_section("Bundle Details", _mapping_fields(payload)))
    return "\n\n".join(sections)


def _status_fields(report: Mapping[str, object], payload: Mapping[str, object]) -> str:
    eligibility = _first(report, "eligibility", "status", "decision")
    ready = report.get("ready")
    fields: list[tuple[str, object]] = []
    if ready is not None:
        fields.append(("Ready", str(bool(ready)).lower()))
    if eligibility is not None:
        fields.append(("Eligibility", humanize_code(eligibility)))
    provider = _first(report, "provider_name", "provider")
    if provider is not None:
        fields.append(("Provider", provider))
    _append_metric(fields, report, "closed_paper_trades", "Closed paper trades")
    _append_metric(fields, report, "modeled_trades", "Modeled trades")
    _append_metric(fields, report, "segment_count", "Segments")
    _append_metric(fields, report, "validated_out_of_sample_count", "Validated out-of-sample")
    _append_ratio(fields, report, "win_rate_deviation", "Win-rate deviation", percentage=True)
    _append_ratio(fields, report, "expectancy_deviation", "Expectancy deviation")
    _append_ratio(fields, report, "drawdown_increase", "Drawdown increase", percentage=True)
    if not fields:
        fields.extend(_summary_fields(payload))
    return render_fields(fields)


def _summary_fields(payload: Mapping[str, object]) -> list[tuple[str, object]]:
    preferred = (
        "history_count",
        "minimum_per_strategy",
        "campaign_id",
        "report_id",
        "generated_at",
    )
    return [
        (humanize_code(key), payload[key])
        for key in preferred
        if key in payload
    ] or [("Status", UNAVAILABLE)]


def _history_fields(history: Mapping[str, object], payload: Mapping[str, object]) -> str:
    fields: list[tuple[str, object]] = []
    for key in ("trading_date", "history_count", "minimum_per_strategy", "generated_at"):
        value = history.get(key, payload.get(key))
        if value is not None:
            fields.append((humanize_code(key), value))
    counts = _mapping(history.get("closed_trades_by_strategy"))
    if counts:
        fields.append(("Observed strategies", len(counts)))
        fields.append(("Closed strategy samples", sum(_integer_values(counts))))
    return render_fields(fields or [("Status", UNAVAILABLE)])


def _append_metric(
    fields: list[tuple[str, object]],
    report: Mapping[str, object],
    key: str,
    label: str,
) -> None:
    if key in report:
        fields.append((label, report[key]))


def _append_ratio(
    fields: list[tuple[str, object]],
    report: Mapping[str, object],
    key: str,
    label: str,
    *,
    percentage: bool = False,
) -> None:
    if key not in report:
        return
    value = report[key]
    rendered = format_percentage(value, ratio=True) if percentage else format_ratio(value)
    fields.append((label, rendered))


def _reason_values(payload: Mapping[str, object]) -> list[str]:
    for key in ("reasons", "blocking_reasons", "failures", "gaps", "warnings"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return _mapping_rows(value)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            return [humanize_code(item) for item in value]
    return []


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _mapping_rows(value: Mapping[str, object]) -> list[str]:
    return [f"{humanize_code(key)}: {item}" for key, item in sorted(value.items())]


def _mapping_fields(value: Mapping[str, object]) -> str:
    fields: list[tuple[str, object]] = []
    for key, item in sorted(value.items()):
        if isinstance(item, Mapping):
            display: object = f"{len(item)} fields"
        elif isinstance(item, Sequence) and not isinstance(item, str | bytes):
            display = f"{len(item)} items"
        else:
            display = item
        fields.append((humanize_code(key), display))
    return render_fields(fields or [("Status", UNAVAILABLE)])


def _first(payload: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return UNAVAILABLE


def _presence(payload: Mapping[str, object], *keys: str) -> str:
    return "Available" if any(payload.get(key) is not None for key in keys) else "Unavailable"


def _integer_values(payload: Mapping[str, object]) -> list[int]:
    return [value for value in payload.values() if isinstance(value, int) and not isinstance(value, bool)]


__all__ = ["render_evidence_bundle", "render_validation"]
