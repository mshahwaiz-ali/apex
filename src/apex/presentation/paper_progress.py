"""Operator-facing presentation for paper intake, evidence, and review."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_percentage,
    format_ratio,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_paper_intake(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one paper opportunity-intake summary."""

    output_mode = normalize_output_mode(mode)
    accepted = _integer(payload.get("accepted"))
    rejected = _integer(payload.get("rejected"))
    duplicates = _integer(payload.get("duplicates_skipped"))
    persistence_failures = _integer(payload.get("persistence_failures"))
    observed = _integer(payload.get("candidates_observed"))
    reasons = _mapping(payload.get("reason_counts"))
    created_trade_ids = _sequence(payload.get("created_trade_ids"))

    sections = [
        render_title("Paper Opportunity Intake"),
        render_section(
            "Intake result",
            render_fields(
                (
                    ("Market", humanize_code(payload.get("market_type"))),
                    ("Candidates observed", observed),
                    ("Trades accepted", accepted),
                    ("Candidates rejected", rejected),
                    ("Duplicates skipped", duplicates),
                    ("Persistence failures", persistence_failures),
                )
            ),
        ),
        render_section(
            "Operational status",
            _intake_status(
                accepted=accepted,
                observed=observed,
                persistence_failures=persistence_failures,
            ),
        ),
        render_section(
            "Next action",
            _intake_next_action(
                accepted=accepted,
                observed=observed,
                persistence_failures=persistence_failures,
            ),
        ),
    ]

    if reasons:
        sections.append(
            render_section(
                "Rejection summary",
                render_bullets(
                    f"{humanize_code(reason)}: {_integer(count)}"
                    for reason, count in reasons.items()
                ),
            )
        )

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(
            render_section(
                "Created paper trades",
                render_bullets(created_trade_ids or (UNAVAILABLE,)),
            )
        )

    if output_mode is OutputMode.DEBUG:
        sections.append(
            render_section(
                "Diagnostics",
                render_fields(
                    (
                        ("Payload fields", len(payload)),
                        ("Reason categories", len(reasons)),
                        ("Created identifiers", len(created_trade_ids)),
                    )
                ),
            )
        )

    return "\n\n".join(sections)


def render_evidence_progress(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render accumulated paper evidence and collection readiness."""

    output_mode = normalize_output_mode(mode)
    segments = tuple(
        item for value in _sequence(payload.get("segments")) if (item := _mapping(value))
    )
    total_closed = _integer(payload.get("total_closed_trades"))
    minimum_closed = _integer(payload.get("minimum_closed_trades"))
    all_sufficient = payload.get("all_segments_sufficient") is True
    ready_count = sum(segment.get("sample_sufficient") is True for segment in segments)
    missing_count = len(segments) - ready_count

    sections = [
        render_title("Paper Evidence Progress"),
        render_section(
            "Collection status",
            render_fields(
                (
                    ("Closed trades collected", total_closed),
                    ("Minimum per segment", minimum_closed),
                    ("Segments tracked", len(segments)),
                    ("Segments ready", ready_count),
                    ("Segments missing evidence", missing_count),
                    ("Overall readiness", "Ready" if all_sufficient else "Not ready"),
                )
            ),
        ),
        render_section(
            "Coverage",
            _coverage_summary(
                segment_count=len(segments),
                ready_count=ready_count,
                all_sufficient=all_sufficient,
            ),
        ),
        render_section(
            "Missing evidence",
            render_bullets(_missing_evidence_lines(segments) or ("No sample gaps remain.",)),
        ),
        render_section(
            "Next action",
            _evidence_next_action(
                segments=segments,
                all_sufficient=all_sufficient,
            ),
        ),
    ]

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(
            render_section(
                "Segment evidence",
                render_bullets(_segment_detail_lines(segments) or (UNAVAILABLE,)),
            )
        )

    if output_mode is OutputMode.DEBUG:
        sections.append(
            render_section(
                "Diagnostics",
                render_fields(
                    (
                        ("Payload fields", len(payload)),
                        ("Segment records", len(segments)),
                        ("Ready segment records", ready_count),
                    )
                ),
            )
        )

    return "\n\n".join(sections)


def render_operational_review(
    payload: Mapping[str, object],
    *,
    output_path: object,
    anomaly_count: int,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render the persisted forward-paper operational review."""

    output_mode = normalize_output_mode(mode)
    review_state = payload.get("review_state")
    production_eligible = payload.get("production_eligible") is True
    blockers = _review_blockers(payload, anomaly_count=anomaly_count)

    sections = [
        render_title("Paper Trading Operational Review"),
        render_section(
            "Review status",
            render_fields(
                (
                    ("Status", humanize_code(review_state)),
                    ("Operationally ready", "Yes" if production_eligible else "No"),
                    ("Lifecycle anomalies", anomaly_count),
                    ("Report file", output_path),
                )
            ),
        ),
        render_section(
            "Readiness",
            (
                "The collected evidence and lifecycle checks support operational use."
                if production_eligible
                else "The system is not yet ready for operational use."
            ),
        ),
        render_section(
            "Blockers",
            render_bullets(blockers or ("No blocking conditions were reported.",)),
        ),
        render_section(
            "Operational recommendation",
            (
                "Continue controlled paper operation and preserve monitoring controls."
                if production_eligible
                else "Keep execution disabled and continue controlled paper validation."
            ),
        ),
        render_section(
            "Next action",
            _review_next_action(
                production_eligible=production_eligible,
                anomaly_count=anomaly_count,
                blockers=blockers,
            ),
        ),
    ]

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(
            render_section(
                "Evidence quality",
                render_fields(_review_evidence_fields(payload)),
            )
        )

    if output_mode is OutputMode.DEBUG:
        sections.append(
            render_section(
                "Diagnostics",
                render_fields(
                    (
                        ("Payload fields", len(payload)),
                        ("Blocking conditions", len(blockers)),
                        ("Lifecycle anomalies", anomaly_count),
                    )
                ),
            )
        )

    return "\n\n".join(sections)


def _intake_status(*, accepted: int, observed: int, persistence_failures: int) -> str:
    if persistence_failures:
        return "Intake completed with persistence failures that require investigation."
    if accepted:
        return "Actionable opportunities were admitted to the paper-trading store."
    if observed:
        return "The scan completed, but no candidate met paper-admission requirements."
    return "The scan completed without observing an actionable candidate."


def _intake_next_action(*, accepted: int, observed: int, persistence_failures: int) -> str:
    if persistence_failures:
        return "Inspect storage permissions and retry the failed persistence operations."
    if accepted:
        return "Run the paper lifecycle cycle to monitor entries, stops, and targets."
    if observed:
        return "Review rejection reasons and continue evidence collection."
    return "Verify symbol eligibility and market-data availability before the next intake."


def _coverage_summary(
    *,
    segment_count: int,
    ready_count: int,
    all_sufficient: bool,
) -> str:
    if segment_count == 0:
        return "No completed-trade segments are available yet."
    coverage = ready_count / segment_count
    state = "complete" if all_sufficient else "incomplete"
    return f"Segment readiness coverage is {format_percentage(coverage, ratio=True)} ({state})."


def _missing_evidence_lines(
    segments: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for segment in segments:
        remaining = _integer(segment.get("remaining_closed_trades"))
        if remaining <= 0:
            continue
        lines.append(f"{_segment_label(segment)}: {remaining} additional closed trades required")
    return tuple(lines)


def _segment_detail_lines(
    segments: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for segment in segments:
        status = "ready" if segment.get("sample_sufficient") is True else "collecting"
        lines.append(
            f"{_segment_label(segment)} | status={status} "
            f"| closed={_integer(segment.get('closed_trade_count'))} "
            f"| remaining={_integer(segment.get('remaining_closed_trades'))} "
            f"| win_rate={format_percentage(segment.get('win_rate'), ratio=True)} "
            f"| expectancy={_r_multiple(segment.get('expectancy_r'))} "
            f"| profit_factor={format_ratio(segment.get('profit_factor'))} "
            f"| maximum_drawdown={_r_multiple(segment.get('maximum_drawdown_r'))}"
        )
    return tuple(lines)


def _evidence_next_action(
    *,
    segments: Sequence[Mapping[str, object]],
    all_sufficient: bool,
) -> str:
    if all_sufficient:
        return "Proceed to operational review using the completed evidence sample."
    if not segments:
        return "Continue paper trading until completed trades create measurable segments."
    largest_gap = max(
        segments,
        key=lambda segment: _integer(segment.get("remaining_closed_trades")),
    )
    remaining = _integer(largest_gap.get("remaining_closed_trades"))
    if remaining <= 0:
        return "Review segment definitions because readiness remains incomplete without a sample gap."
    return (
        f"Prioritize {_segment_label(largest_gap)} and collect "
        f"{remaining} additional closed trades."
    )


def _segment_label(segment: Mapping[str, object]) -> str:
    dimensions = _mapping(segment.get("dimensions"))
    if not dimensions:
        return "Unclassified segment"
    return ", ".join(
        f"{humanize_code(key)}={humanize_code(value)}"
        for key, value in dimensions.items()
    )


def _review_blockers(
    payload: Mapping[str, object],
    *,
    anomaly_count: int,
) -> tuple[str, ...]:
    blockers: list[str] = []

    for key in ("blockers", "blocking_reasons", "reasons"):
        for value in _sequence(payload.get(key)):
            text = str(value).strip()
            if text and text not in blockers:
                blockers.append(text)

    if payload.get("sample_sufficient") is False:
        blockers.append("The forward-paper sample is below the required minimum.")
    if payload.get("manual_execution_usable") is False:
        blockers.append("Manual execution usability has not been confirmed.")
    if anomaly_count:
        blockers.append(f"{anomaly_count} lifecycle anomalies require resolution.")

    return tuple(blockers)


def _review_evidence_fields(
    payload: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    return (
        ("Review state", humanize_code(payload.get("review_state"))),
        ("Sample sufficient", _yes_no(payload.get("sample_sufficient"))),
        (
            "Manual execution usable",
            _yes_no(payload.get("manual_execution_usable")),
        ),
        (
            "Historical comparison acceptable",
            _yes_no(
                payload.get("historical_comparison_acceptable")
                or payload.get("deviation_acceptable")
            ),
        ),
        (
            "Lifecycle integrity acceptable",
            _yes_no(
                payload.get("lifecycle_integrity_acceptable")
                or payload.get("lifecycle_audit_passed")
            ),
        ),
    )


def _review_next_action(
    *,
    production_eligible: bool,
    anomaly_count: int,
    blockers: Sequence[str],
) -> str:
    if anomaly_count:
        return "Resolve lifecycle anomalies, rebuild the review, and verify the new report."
    if blockers:
        return "Resolve the listed blockers and regenerate the operational review."
    if production_eligible:
        return "Maintain controlled operation and monitor evidence stability."
    return "Continue forward-paper evidence collection and regenerate the review."


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(value)
    return ()


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _yes_no(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return UNAVAILABLE


def _r_multiple(value: object) -> str:
    rendered = format_ratio(value, decimals=4)
    return rendered if rendered == UNAVAILABLE else f"{rendered}R"


__all__ = [
    "render_evidence_progress",
    "render_operational_review",
    "render_paper_intake",
]
