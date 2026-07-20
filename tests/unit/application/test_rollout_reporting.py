"""Tests for operator-facing rollout diagnostic reports."""

from __future__ import annotations

import json

import pytest

from apex.application.rollout_reporting import (
    build_rollout_operator_report,
    write_rollout_operator_report,
)


def test_build_analyze_report_extracts_comparison_only() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "selected_setup": {"strategy": "trend_pullback"},
        "rollout_comparison": {
            "authoritative": False,
            "symbol": "BTCUSDT",
            "differences": [],
        },
    }

    report = build_rollout_operator_report(payload, command="analyze")

    assert report["authoritative"] is False
    assert report["command"] == "analyze"
    assert report["comparison"] == payload["rollout_comparison"]
    assert "selected_setup" not in report


def test_build_scan_report_extracts_summary_and_per_symbol_comparisons() -> None:
    payload = {
        "results": [
            {
                "symbol": "BTCUSDT",
                "rollout_comparison": {
                    "authoritative": False,
                    "symbol": "BTCUSDT",
                },
            },
            {"symbol": "ETHUSDT"},
        ],
        "rollout_comparison_summary": {
            "authoritative": False,
            "total_count": 2,
            "regression_count": 0,
        },
    }

    report = build_rollout_operator_report(payload, command="scan")

    assert report["summary"] == payload["rollout_comparison_summary"]
    assert report["comparisons"] == [
        {
            "symbol": "BTCUSDT",
            "comparison": payload["results"][0]["rollout_comparison"],
        }
    ]


@pytest.mark.parametrize("command", ["analyze", "scan"])
def test_report_refuses_payload_without_diagnostics(command: str) -> None:
    with pytest.raises(ValueError, match="does not contain rollout diagnostics"):
        build_rollout_operator_report({}, command=command)  # type: ignore[arg-type]


def test_write_report_creates_parent_and_stable_json(tmp_path) -> None:
    path = tmp_path / "nested" / "rollout.json"
    payload = {
        "rollout_comparison": {
            "authoritative": False,
            "symbol": "SOLUSDT",
        }
    }

    write_rollout_operator_report(payload, path, command="analyze")

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["command"] == "analyze"
    assert written["comparison"]["symbol"] == "SOLUSDT"
