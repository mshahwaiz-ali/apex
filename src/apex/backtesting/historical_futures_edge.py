"""Build setup-specific historical edge reports from completed futures campaigns."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.historical_edge import DEFAULT_EDGE_SEGMENTS, aggregate_historical_edges
from apex.backtesting.historical_edge_io import build_historical_edge_report
from apex.backtesting.historical_futures_shared_io import hash_json
from apex.strategies import StrategyType, TradeDirection

HISTORICAL_FUTURES_EDGE_SOURCE_TYPE = "historical_futures_campaign"
HISTORICAL_FUTURES_EDGE_SEGMENTS = ("split", *DEFAULT_EDGE_SEGMENTS)


def build_historical_futures_edge_report(
    *,
    result_path: Path,
    execution_manifest_path: Path,
    generated_at: datetime,
) -> dict[str, Any]:
    """Verify one completed campaign and build split-isolated edge profiles."""

    result = _load_object(result_path, label="historical futures result")
    manifest = _load_object(
        execution_manifest_path,
        label="historical futures execution manifest",
    )
    _verify_campaign_artifacts(result=result, manifest=manifest)

    trades_payload = result.get("trades")
    if not isinstance(trades_payload, list):
        raise ValueError("historical futures result trades must be a list")
    trades = tuple(_trade_from_payload(item) for item in trades_payload)
    profiles = aggregate_historical_edges(
        trades,
        segment_by=HISTORICAL_FUTURES_EDGE_SEGMENTS,
    ) if trades else ()

    campaign_id = _required_string(result, "campaign_id")
    report = build_historical_edge_report(
        profiles,
        generated_at=generated_at,
        source_type=HISTORICAL_FUTURES_EDGE_SOURCE_TYPE,
        source_id=campaign_id,
    )
    report.update(
        {
            "campaign_id": campaign_id,
            "source_result_path": result_path.as_posix(),
            "source_execution_manifest_path": execution_manifest_path.as_posix(),
            "source_result_hash": _required_string(manifest, "result_hash"),
            "signal_records_hash": _required_string(manifest, "signal_records_hash"),
            "signal_configuration_hash": _required_string(
                manifest,
                "signal_configuration_hash",
            ),
            "wallet_configuration_hash": manifest.get("wallet_configuration_hash"),
            "trade_count": len(trades),
            "split_trade_counts": _split_trade_counts(trades),
            "warnings": [
                "Final-test profiles are reported but must not drive calibration.",
                "Historical evidence does not establish funded or live-trading eligibility.",
                "Forward-paper validation is not included in this report.",
            ],
        }
    )
    return report


def _verify_campaign_artifacts(
    *,
    result: Mapping[str, object],
    manifest: Mapping[str, object],
) -> None:
    result_campaign = _required_string(result, "campaign_id")
    manifest_campaign = _required_string(manifest, "campaign_id")
    if result_campaign != manifest_campaign:
        raise ValueError("historical futures result and manifest campaigns do not match")
    if manifest.get("status") != "completed":
        raise ValueError("historical futures execution manifest is not completed")
    expected_hash = _required_string(manifest, "result_hash")
    if hash_json(result) != expected_hash:
        raise ValueError("historical futures result hash does not match execution manifest")
    trades = result.get("trades")
    if not isinstance(trades, list):
        raise ValueError("historical futures result trades must be a list")
    declared_trade_count = _required_int(manifest, "trade_count")
    if declared_trade_count != len(trades):
        raise ValueError("historical futures manifest trade count does not match result")


def _trade_from_payload(value: object) -> SimulatedTrade:
    if not isinstance(value, Mapping):
        raise ValueError("historical futures trade must be an object")
    target_prices = _positive_float_tuple(value.get("target_prices"), "target prices")
    if not target_prices:
        raise ValueError("historical futures trade requires target prices")
    partials = _equal_partials(len(target_prices))
    split = _required_string(value, "split")
    metadata = _string_key_mapping(value.get("metadata"))
    metadata["split"] = split
    metadata.setdefault("market_type", "futures")

    signal = BacktestSignal(
        symbol=_required_string(value, "symbol"),
        strategy=StrategyType(_required_string(value, "strategy")),
        direction=TradeDirection(_required_string(value, "direction")),
        generated_at=_required_datetime(value, "decision_time"),
        entry_price=_required_positive_float(value, "entry_price"),
        stop_price=_required_positive_float(value, "stop_price"),
        target_price=target_prices[0],
        quantity=_required_positive_float(value, "quantity"),
        risk_amount=_required_positive_float(value, "risk_amount"),
        confidence_score=_confidence_score(metadata),
        target_prices=target_prices,
        partial_close_percentages=partials,
    )
    return SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome(_required_string(value, "outcome")),
        exit_time=_required_datetime(value, "exit_time"),
        exit_price=_required_positive_float(value, "exit_price"),
        gross_pnl=_required_float(value, "gross_pnl"),
        fees=_required_non_negative_float(value, "fees"),
        net_pnl=_required_float(value, "net_pnl"),
        realized_r_multiple=_required_float(value, "realized_r_multiple"),
        holding_candles=_required_positive_int(value, "holding_candles"),
        metadata=metadata,
    )


def _confidence_score(metadata: Mapping[str, str | int | float | bool]) -> float:
    value = metadata.get("confidence_score", metadata.get("score", 0.0))
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    score = float(value)
    return score if math.isfinite(score) and 0.0 <= score <= 100.0 else 0.0


def _equal_partials(count: int) -> tuple[float, ...]:
    if count < 1:
        raise ValueError("target count must be positive")
    base = 100.0 / count
    values = [base] * count
    values[-1] = 100.0 - sum(values[:-1])
    return tuple(values)


def _split_trade_counts(trades: Sequence[SimulatedTrade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        split = str(trade.metadata.get("split", "unknown"))
        counts[split] = counts.get(split, 0) + 1
    return dict(sorted(counts.items()))


def _load_object(path: Path, *, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _string_key_mapping(value: object) -> dict[str, str | int | float | bool]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("historical futures trade metadata must be an object")
    output: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str | int | float | bool):
            raise ValueError("historical futures trade metadata must be scalar")
        output[key] = item
    return output


def _positive_float_tuple(value: object, label: str) -> tuple[float, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"historical futures {label} must be a sequence")
    output = tuple(float(item) for item in value if isinstance(item, int | float) and not isinstance(item, bool))
    if len(output) != len(value) or any(not math.isfinite(item) or item <= 0.0 for item in output):
        raise ValueError(f"historical futures {label} must be positive and finite")
    return output


def _required_string(value: Mapping[str, object], key: str) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"historical futures {key} is required")
    return selected


def _required_datetime(value: Mapping[str, object], key: str) -> datetime:
    parsed = datetime.fromisoformat(_required_string(value, key).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"historical futures {key} must be timezone-aware")
    return parsed


def _required_float(value: Mapping[str, object], key: str) -> float:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int | float):
        raise ValueError(f"historical futures {key} must be numeric")
    result = float(selected)
    if not math.isfinite(result):
        raise ValueError(f"historical futures {key} must be finite")
    return result


def _required_positive_float(value: Mapping[str, object], key: str) -> float:
    result = _required_float(value, key)
    if result <= 0.0:
        raise ValueError(f"historical futures {key} must be positive")
    return result


def _required_non_negative_float(value: Mapping[str, object], key: str) -> float:
    result = _required_float(value, key)
    if result < 0.0:
        raise ValueError(f"historical futures {key} must be non-negative")
    return result


def _required_int(value: Mapping[str, object], key: str) -> int:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int):
        raise ValueError(f"historical futures {key} must be an integer")
    return selected


def _required_positive_int(value: Mapping[str, object], key: str) -> int:
    result = _required_int(value, key)
    if result < 1:
        raise ValueError(f"historical futures {key} must be positive")
    return result
