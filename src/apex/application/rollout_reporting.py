"""Operator-facing, non-authoritative rollout diagnostic reports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from apex.application.rollout_acceptance import (
    evaluate_rollout_acceptance,
    rollout_acceptance_payload,
)
from apex.application.rollout_comparison import AnalysisComparisonSummary

RolloutCommand = Literal["analyze", "scan"]


def _validated_comparison(value: object) -> dict[str, Any]:
    """Require evidence that diagnostics compare two distinct projection sources."""

    if not isinstance(value, Mapping):
        raise ValueError("rollout comparison is missing or malformed")
    if value.get("distinct_projection_sources") is not True:
        raise ValueError("rollout comparison does not prove distinct projection sources")

    legacy_kind = value.get("legacy_projection_kind")
    new_kind = value.get("new_projection_kind")
    if not isinstance(legacy_kind, str) or not legacy_kind.strip():
        raise ValueError("rollout comparison legacy projection kind is missing")
    if not isinstance(new_kind, str) or not new_kind.strip():
        raise ValueError("rollout comparison portfolio projection kind is missing")
    if legacy_kind == new_kind:
        raise ValueError("rollout comparison projection kinds are not distinct")
    return dict(value)


def build_rollout_operator_report(
    payload: Mapping[str, Any],
    *,
    command: RolloutCommand,
) -> dict[str, Any]:
    """Extract rollout diagnostics without changing the normal CLI payload."""

    report: dict[str, Any] = {
        "schema_version": 1,
        "command": command,
        "authoritative": False,
        "interpretation": (
            "operator diagnostic only; this report does not affect selection, "
            "ranking, scoring, actionability, or execution"
        ),
    }

    if command == "analyze":
        comparison = payload.get("rollout_comparison")
        if not isinstance(comparison, Mapping):
            raise ValueError("analyze payload does not contain rollout diagnostics")
        report["comparison"] = _validated_comparison(comparison)
        return report

    summary = payload.get("rollout_comparison_summary")
    if not isinstance(summary, Mapping):
        raise ValueError("scan payload does not contain rollout diagnostics")
    report["summary"] = dict(summary)
    comparison_summary = AnalysisComparisonSummary(
        total_count=int(summary.get("total_count", 0)),
        match_count=int(summary.get("match_count", 0)),
        difference_count=int(summary.get("difference_count", 0)),
        compatibility_only_count=int(summary.get("compatibility_only_count", 0)),
        regression_count=int(summary.get("regression_count", 0)),
        field_difference_counts=dict(summary.get("field_difference_counts", {})),
        regression_field_counts=dict(summary.get("regression_field_counts", {})),
        compatibility_fixture_ids=tuple(
            str(item) for item in summary.get("compatibility_fixture_ids", [])
        ),
        regression_fixture_ids=tuple(
            str(item) for item in summary.get("regression_fixture_ids", [])
        ),
    )
    report["acceptance"] = rollout_acceptance_payload(
        evaluate_rollout_acceptance(comparison_summary)
    )

    comparisons: list[dict[str, Any]] = []
    results = payload.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, Mapping):
                continue
            comparison = item.get("rollout_comparison")
            if not isinstance(comparison, Mapping):
                continue
            comparisons.append(
                {
                    "symbol": item.get("symbol"),
                    "comparison": _validated_comparison(comparison),
                }
            )
    report["comparisons"] = comparisons
    return report


def write_rollout_operator_report(
    payload: Mapping[str, Any],
    path: Path,
    *,
    command: RolloutCommand,
) -> None:
    """Write a dedicated rollout diagnostic JSON artifact."""

    report = build_rollout_operator_report(payload, command=command)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "RolloutCommand",
    "build_rollout_operator_report",
    "write_rollout_operator_report",
]
