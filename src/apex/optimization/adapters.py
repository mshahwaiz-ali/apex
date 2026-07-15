"""Adapters from Apex historical result payloads into optimization summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from apex.optimization.contracts import PerformanceSummary
from apex.optimization.engine import performance_from_mapping


def performance_from_spot_historical_payload(payload: Mapping[str, Any]) -> PerformanceSummary:
    """Build optimization input from a persisted spot historical backtest payload."""

    metrics = _mapping(payload, "metrics")
    normalized = {
        "total_trades": int(metrics.get("trade_count", metrics.get("total_trades", 0))),
        "win_rate": float(metrics.get("win_rate") or 0.0),
        "expectancy": float(metrics.get("expectancy", 0.0)),
        "profit_factor": metrics.get("profit_factor"),
        "maximum_drawdown": float(metrics.get("maximum_drawdown", 0.0)),
        "net_profit": float(metrics.get("net_profit", 0.0)),
        "by_symbol": _group_trade_counts(metrics.get("performance_by_symbol")),
        "by_strategy": _group_trade_counts(metrics.get("performance_by_strategy")),
        "by_regime": _group_trade_counts(metrics.get("performance_by_market_regime")),
        "by_score_band": _group_trade_counts(metrics.get("performance_by_score_band")),
    }
    return performance_from_mapping(normalized)


def performance_from_futures_historical_payload(
    payload: Mapping[str, Any],
    *,
    split: str | None = None,
) -> PerformanceSummary:
    """Build optimization input from a futures historical result or split payload."""

    selected: Mapping[str, Any] = payload
    if split is not None:
        split_metrics = payload.get("split_metrics")
        if not isinstance(split_metrics, Mapping):
            raise ValueError("futures historical payload does not contain split metrics")
        candidate = split_metrics.get(split)
        if not isinstance(candidate, Mapping):
            raise ValueError(f"futures historical payload does not contain split: {split}")
        selected = cast(Mapping[str, Any], candidate)

    metrics = selected.get("metrics", selected)
    if not isinstance(metrics, Mapping):
        raise TypeError("futures historical metrics must be an object")
    normalized = dict(metrics)
    if "total_trades" not in normalized and "trade_count" in normalized:
        normalized["total_trades"] = normalized["trade_count"]
    if "by_symbol" not in normalized:
        normalized["by_symbol"] = _group_trade_counts(
            normalized.get("performance_by_symbol")
        )
    if "by_strategy" not in normalized:
        normalized["by_strategy"] = _group_trade_counts(
            normalized.get("performance_by_strategy")
        )
    if "by_regime" not in normalized:
        normalized["by_regime"] = _group_trade_counts(
            normalized.get("performance_by_market_regime")
        )
    if "by_score_band" not in normalized:
        normalized["by_score_band"] = _group_trade_counts(
            normalized.get("performance_by_score_band")
        )
    return performance_from_mapping(cast(dict[str, Any], normalized))


def _mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"historical result field must be an object: {key}")
    return cast(Mapping[str, Any], value)


def _group_trade_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            count = item.get("trade_count", item.get("total_trades", 0))
        else:
            count = item
        counts[str(key)] = int(count)
    return counts
