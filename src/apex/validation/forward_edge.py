"""Attach forward-paper evidence to validated historical setup segments."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, cast

from apex.backtesting.historical_edge import EvidenceQuality
from apex.paper_trading import PaperTrade

FORWARD_EDGE_REPORT_SCHEMA_VERSION = 1


class _ForwardMetrics(TypedDict):
    sample_size: int
    win_rate: float
    expectancy: float
    profit_factor: float | None


@dataclass(frozen=True, slots=True)
class ForwardEdgePolicy:
    """Thresholds required before forward-paper evidence is promoted."""

    minimum_closed_trades: int = 30
    minimum_expectancy: float = 0.0
    minimum_profit_factor: float = 1.0
    maximum_expectancy_degradation: float = 0.50

    def __post_init__(self) -> None:
        if self.minimum_closed_trades < 1:
            raise ValueError("minimum forward closed trades must be positive")
        for name in (
            "minimum_expectancy",
            "minimum_profit_factor",
            "maximum_expectancy_degradation",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")


def build_forward_edge_report(
    *,
    historical_validation_path: Path,
    paper_trades: Sequence[PaperTrade],
    generated_at: datetime,
    policy: ForwardEdgePolicy | None = None,
) -> dict[str, Any]:
    """Evaluate closed paper trades against validated setup segments."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("forward edge report time must be timezone-aware")
    source = _load_object(historical_validation_path)
    _verify_historical_validation(source)
    resolved = policy or ForwardEdgePolicy()
    grouped = _group_closed_trades(paper_trades)
    results: list[dict[str, Any]] = []

    for item in source["results"]:
        if not isinstance(item, Mapping):
            raise ValueError("historical validation results must be objects")
        dimensions = _string_mapping(item.get("dimensions"), "historical dimensions")
        key = tuple(sorted(dimensions.items()))
        trades = grouped.get(key, ())
        metrics = _forward_metrics(trades)
        sample_size = cast(int, metrics["sample_size"])
        expectancy = cast(float, metrics["expectancy"])
        win_rate = cast(float, metrics["win_rate"])
        profit_factor = cast(float | None, metrics["profit_factor"])
        historical_expectancy = _optional_float(item.get("final_test_expectancy"))
        degradation = _expectancy_degradation(historical_expectancy, expectancy)
        historically_validated = (
            item.get("promoted_evidence_quality")
            == EvidenceQuality.VALIDATED_OUT_OF_SAMPLE.value
        )
        reasons: list[str] = []
        if not historically_validated:
            reasons.append("HISTORICAL_OUT_OF_SAMPLE_REQUIRED")
        if sample_size < resolved.minimum_closed_trades:
            reasons.append("FORWARD_SAMPLE_INSUFFICIENT")
        if expectancy < resolved.minimum_expectancy:
            reasons.append("FORWARD_EXPECTANCY_INADEQUATE")
        if profit_factor is not None and profit_factor < resolved.minimum_profit_factor:
            reasons.append("FORWARD_PROFIT_FACTOR_INADEQUATE")
        if degradation is not None and degradation > resolved.maximum_expectancy_degradation:
            reasons.append("FORWARD_EXPECTANCY_DEGRADATION_EXCESSIVE")
        passed = not reasons
        results.append(
            {
                "dimensions": dimensions,
                "status": "PASSED_FORWARD_PAPER" if passed else "FAILED_FORWARD_PAPER",
                "historically_validated": historically_validated,
                "forward_sample_size": sample_size,
                "forward_win_rate": win_rate,
                "forward_expectancy": expectancy,
                "forward_profit_factor": profit_factor,
                "historical_final_test_expectancy": historical_expectancy,
                "expectancy_degradation": degradation,
                "promoted_evidence_quality": (
                    EvidenceQuality.VALIDATED_FORWARD_PAPER.value if passed else None
                ),
                "rejection_reasons": reasons,
            }
        )

    policy_payload = {
        "minimum_closed_trades": resolved.minimum_closed_trades,
        "minimum_expectancy": resolved.minimum_expectancy,
        "minimum_profit_factor": resolved.minimum_profit_factor,
        "maximum_expectancy_degradation": resolved.maximum_expectancy_degradation,
    }
    identity = {
        "source_report_id": source["report_id"],
        "policy": policy_payload,
        "results": results,
    }
    report_id = f"forward-edge-{_hash_json(identity)[:24]}"
    promoted = sum(
        item["promoted_evidence_quality"] == EvidenceQuality.VALIDATED_FORWARD_PAPER.value
        for item in results
    )
    return {
        "schema_version": FORWARD_EDGE_REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "generated_at": generated_at.isoformat(),
        "campaign_id": source["campaign_id"],
        "source_validation_report_id": source["report_id"],
        "source_validation_path": historical_validation_path.as_posix(),
        "policy": policy_payload,
        "segment_count": len(results),
        "validated_forward_paper_count": promoted,
        "results": results,
        "warnings": [
            "Forward-paper validation does not establish production or funded eligibility.",
            "Only closed auditable paper trades are included.",
        ],
    }


def write_forward_edge_report(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Atomically persist and reload-verify a forward evidence report."""

    normalized = _normalize_report(payload)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing forward edge report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    if load_forward_edge_report(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("forward edge report changed after reload")


def load_forward_edge_report(path: Path) -> dict[str, Any]:
    """Load and validate one persisted forward evidence report."""

    return _normalize_report(_load_object(path))


def _group_closed_trades(
    trades: Sequence[PaperTrade],
) -> dict[tuple[tuple[str, str], ...], tuple[PaperTrade, ...]]:
    grouped: dict[tuple[tuple[str, str], ...], list[PaperTrade]] = defaultdict(list)
    for trade in trades:
        if trade.is_open:
            continue
        dimensions = _paper_dimensions(trade)
        grouped[tuple(sorted(dimensions.items()))].append(trade)
    return {
        key: tuple(sorted(values, key=lambda item: (item.exit_time or item.updated_at, item.trade_id)))
        for key, values in grouped.items()
    }


def _paper_dimensions(trade: PaperTrade) -> dict[str, str]:
    payload = trade.analysis_payload
    market_regime = payload.get("market_regime", "unknown")
    entry_state = payload.get("entry_state", payload.get("entry_status", "unknown"))
    risk_mode = payload.get("risk_mode", payload.get("active_risk_mode", "STANDARD"))
    score = trade.signal.confidence_score
    lower = int(score // 10) * 10
    return {
        "market_type": "futures",
        "strategy": trade.signal.strategy.value,
        "direction": trade.signal.direction.value,
        "symbol": trade.signal.symbol,
        "market_regime": str(market_regime),
        "score_band": f"{lower:02d}_{min(lower + 9, 100):02d}",
        "entry_state": str(entry_state),
        "risk_mode": str(risk_mode),
    }


def _forward_metrics(trades: Sequence[PaperTrade]) -> dict[str, int | float | None]:
    values = tuple(trade.realized_r_multiple for trade in trades)
    wins = tuple(value for value in values if value > 0.0)
    losses = tuple(value for value in values if value < 0.0)
    size = len(values)
    expectancy = sum(values) / size if size else 0.0
    gross_loss = abs(sum(losses))
    profit_factor = sum(wins) / gross_loss if gross_loss > 0.0 else None
    return {
        "sample_size": size,
        "win_rate": len(wins) / size if size else 0.0,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
    }


def _expectancy_degradation(historical: float | None, forward: float) -> float | None:
    if historical is None or historical <= 0.0:
        return None
    return max(0.0, (historical - forward) / historical)


def _verify_historical_validation(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported historical validation schema version")
    for key in ("report_id", "campaign_id", "results"):
        if key not in value:
            raise ValueError(f"historical validation {key} is required")
    if not isinstance(value["results"], list):
        raise ValueError("historical validation results must be a list")


def _normalize_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    loaded = json.loads(json.dumps(payload))
    if not isinstance(loaded, dict):
        raise ValueError("forward edge report must be an object")
    normalized = cast(dict[str, Any], loaded)
    required = {
        "schema_version",
        "report_id",
        "generated_at",
        "campaign_id",
        "source_validation_report_id",
        "policy",
        "segment_count",
        "validated_forward_paper_count",
        "results",
        "warnings",
    }
    missing = required.difference(normalized)
    if missing:
        raise ValueError(f"forward edge report fields are missing: {sorted(missing)}")
    if normalized["schema_version"] != FORWARD_EDGE_REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported forward edge report schema version")
    if not isinstance(normalized["results"], list):
        raise ValueError("forward edge results must be a list")
    if normalized["segment_count"] != len(normalized["results"]):
        raise ValueError("forward edge segment count must match results")
    return normalized


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return value


def _string_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError(f"{label} must be a string mapping")
    return dict(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("historical expectancy must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("historical expectancy must be finite")
    return result


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
