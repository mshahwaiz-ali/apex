"""Comparison helpers for saved chronological backtest reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apex.application.backtest_report_io import load_backtest_report

_METRICS = (
    ("trade_count", "total_trades"),
    ("net_profit", "net_profit"),
    ("expectancy", "expectancy"),
    ("profit_factor", "profit_factor"),
    ("maximum_drawdown", "maximum_drawdown"),
    ("win_rate", "win_rate"),
)


def compare_backtest_reports(left_path: Path, right_path: Path) -> dict[str, Any]:
    """Compare reproducibility identities and selected aggregate metrics."""
    left = load_backtest_report(left_path)
    right = load_backtest_report(right_path)
    left_metadata = _mapping(left.get("metadata"), "left metadata")
    right_metadata = _mapping(right.get("metadata"), "right metadata")
    left_metrics = _mapping(left.get("metrics"), "left metrics")
    right_metrics = _mapping(right.get("metrics"), "right metrics")

    metric_comparison = {
        output_name: {
            "left": left_metrics.get(report_name),
            "right": right_metrics.get(report_name),
            "delta": _numeric_delta(
                left_metrics.get(report_name),
                right_metrics.get(report_name),
            ),
        }
        for output_name, report_name in _METRICS
    }
    return {
        "left": str(left_path),
        "right": str(right_path),
        "dataset_hash": {
            "left": left_metadata.get("dataset_hash"),
            "right": right_metadata.get("dataset_hash"),
            "matches": left_metadata.get("dataset_hash") == right_metadata.get("dataset_hash"),
        },
        "config_hash": {
            "left": left_metadata.get("config_hash"),
            "right": right_metadata.get("config_hash"),
            "matches": left_metadata.get("config_hash") == right_metadata.get("config_hash"),
        },
        "metrics": metric_comparison,
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"backtest report is missing {label}")
    return value


def _numeric_delta(left: Any, right: Any) -> float | int | None:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return right - left
    return None
