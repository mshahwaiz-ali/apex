"""Validate N4.8 futures edge reports across chronological evidence splits."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from apex.backtesting.historical_edge import EvidenceQuality, HistoricalEdgeProfile
from apex.backtesting.historical_edge_validation import (
    HistoricalEdgeValidationPolicy,
    HistoricalEdgeValidationResult,
    validate_out_of_sample_edges,
)

HISTORICAL_FUTURES_EDGE_VALIDATION_SCHEMA_VERSION = 1
_SPLITS = ("train", "validation", "final_test")


def build_historical_futures_edge_validation_report(
    *,
    edge_report_path: Path,
    generated_at: datetime,
    policy: HistoricalEdgeValidationPolicy | None = None,
) -> dict[str, Any]:
    """Validate matching setup segments without allowing split leakage."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("historical edge validation time must be timezone-aware")
    source = _load_object(edge_report_path)
    _verify_source_report(source)
    grouped = _profiles_by_split(source)
    results = validate_out_of_sample_edges(
        grouped["train"],
        grouped["validation"],
        grouped["final_test"],
        policy=policy,
    )
    policy_payload = _policy_payload(policy or HistoricalEdgeValidationPolicy())
    result_payloads = [_validation_payload(item) for item in results]
    identity = {
        "source_report_id": _required_string(source, "report_id"),
        "source_result_hash": _required_string(source, "source_result_hash"),
        "policy": policy_payload,
        "results": result_payloads,
    }
    report_id = f"historical-futures-edge-validation-{_hash_json(identity)[:24]}"
    status_counts = Counter(item["status"] for item in result_payloads)
    promoted = sum(
        item["promoted_evidence_quality"] == EvidenceQuality.VALIDATED_OUT_OF_SAMPLE.value
        for item in result_payloads
    )
    return {
        "schema_version": HISTORICAL_FUTURES_EDGE_VALIDATION_SCHEMA_VERSION,
        "report_id": report_id,
        "generated_at": generated_at.isoformat(),
        "campaign_id": _required_string(source, "campaign_id"),
        "source_report_id": _required_string(source, "report_id"),
        "source_report_path": edge_report_path.as_posix(),
        "source_result_hash": _required_string(source, "source_result_hash"),
        "policy": policy_payload,
        "segment_count": len(result_payloads),
        "status_counts": dict(sorted(status_counts.items())),
        "validated_out_of_sample_count": promoted,
        "results": result_payloads,
        "warnings": [
            "Final-test evidence is used only for untouched out-of-sample evaluation.",
            "Validated out-of-sample evidence still requires forward-paper validation.",
            "This report does not establish funded, production, or live-trading eligibility.",
        ],
    }


def write_historical_futures_edge_validation_report(
    path: Path,
    payload: Mapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Atomically persist and reload-verify a validation report."""

    normalized = _normalize_validation_report(payload)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing validation report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    if load_historical_futures_edge_validation_report(path) != normalized:
        path.unlink(missing_ok=True)
        raise ValueError("historical futures edge validation report changed after reload")


def load_historical_futures_edge_validation_report(path: Path) -> dict[str, Any]:
    """Load and validate one persisted N4.9 report."""

    return _normalize_validation_report(_load_object(path))


def _profiles_by_split(
    source: Mapping[str, object],
) -> dict[str, tuple[HistoricalEdgeProfile, ...]]:
    profiles = source.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("historical edge report profiles must be a list")
    grouped: dict[str, list[HistoricalEdgeProfile]] = {name: [] for name in _SPLITS}
    for value in profiles:
        profile = _profile_from_payload(value)
        dimensions = dict(profile.dimensions)
        split = dimensions.pop("split", None)
        if split not in grouped:
            raise ValueError(f"unsupported historical edge split: {split}")
        grouped[split].append(_replace_dimensions(profile, dimensions))
    return {
        key: tuple(sorted(values, key=lambda item: tuple(sorted(item.dimensions.items()))))
        for key, values in grouped.items()
    }


def _replace_dimensions(
    profile: HistoricalEdgeProfile,
    dimensions: Mapping[str, str],
) -> HistoricalEdgeProfile:
    return HistoricalEdgeProfile(
        dimensions=dimensions,
        sample_size=profile.sample_size,
        win_rate=profile.win_rate,
        loss_rate=profile.loss_rate,
        breakeven_rate=profile.breakeven_rate,
        average_r=profile.average_r,
        median_r=profile.median_r,
        expectancy=profile.expectancy,
        profit_factor=profile.profit_factor,
        maximum_drawdown_r=profile.maximum_drawdown_r,
        maximum_losing_streak=profile.maximum_losing_streak,
        average_holding_candles=profile.average_holding_candles,
        average_execution_cost_r=profile.average_execution_cost_r,
        evidence_quality=profile.evidence_quality,
        warnings=profile.warnings,
    )


def _profile_from_payload(value: object) -> HistoricalEdgeProfile:
    if not isinstance(value, Mapping):
        raise ValueError("historical edge profile must be an object")
    dimensions = value.get("dimensions")
    warnings = value.get("warnings", [])
    if not isinstance(dimensions, Mapping) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in dimensions.items()
    ):
        raise ValueError("historical edge profile dimensions must be string mappings")
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise ValueError("historical edge profile warnings must be strings")
    profit_factor = value.get("profit_factor")
    return HistoricalEdgeProfile(
        dimensions=dict(dimensions),
        sample_size=_required_int(value, "sample_size"),
        win_rate=_required_float(value, "win_rate"),
        loss_rate=_required_float(value, "loss_rate"),
        breakeven_rate=_required_float(value, "breakeven_rate"),
        average_r=_required_float(value, "average_r"),
        median_r=_required_float(value, "median_r"),
        expectancy=_required_float(value, "expectancy"),
        profit_factor=None if profit_factor is None else _required_float(value, "profit_factor"),
        maximum_drawdown_r=_required_float(value, "maximum_drawdown_r"),
        maximum_losing_streak=_required_int(value, "maximum_losing_streak"),
        average_holding_candles=_required_float(value, "average_holding_candles"),
        average_execution_cost_r=_required_float(value, "average_execution_cost_r"),
        evidence_quality=EvidenceQuality(_required_string(value, "evidence_quality")),
        warnings=tuple(warnings),
    )


def _validation_payload(result: HistoricalEdgeValidationResult) -> dict[str, Any]:
    return {
        "dimensions": dict(result.dimensions),
        "status": result.status.value,
        "out_of_sample_sample_size": result.out_of_sample_sample_size,
        "train_expectancy": result.train_expectancy,
        "validation_expectancy": result.validation_expectancy,
        "final_test_expectancy": result.test_expectancy,
        "validation_profit_factor": result.validation_profit_factor,
        "final_test_profit_factor": result.test_profit_factor,
        "validation_expectancy_degradation": result.validation_expectancy_degradation,
        "final_test_expectancy_degradation": result.test_expectancy_degradation,
        "consistent_edge_direction": result.consistent_edge_direction,
        "evidence_stable": result.evidence_stable,
        "promoted_evidence_quality": (
            result.promoted_evidence_quality.value
            if result.promoted_evidence_quality is not None
            else None
        ),
        "rejection_reasons": [item.value for item in result.rejection_reasons],
        "warnings": [item.value for item in result.warnings],
    }


def _policy_payload(policy: HistoricalEdgeValidationPolicy) -> dict[str, Any]:
    return {
        "minimum_validation_trades": policy.minimum_validation_trades,
        "minimum_final_test_trades": policy.minimum_test_trades,
        "minimum_out_of_sample_trades": policy.minimum_out_of_sample_trades,
        "minimum_profit_factor": policy.minimum_profit_factor,
        "maximum_validation_expectancy_degradation": policy.maximum_validation_expectancy_degradation,
        "maximum_final_test_expectancy_degradation": policy.maximum_test_expectancy_degradation,
        "eligible_train_qualities": sorted(item.value for item in policy.eligible_train_qualities),
    }


def _verify_source_report(source: Mapping[str, object]) -> None:
    if source.get("source_type") != "historical_futures_campaign":
        raise ValueError("N4.9 requires a historical futures edge report")
    if source.get("schema_version") != 1:
        raise ValueError("unsupported historical edge report schema version")
    _required_string(source, "report_id")
    _required_string(source, "campaign_id")
    _required_string(source, "source_result_hash")


def _normalize_validation_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    loaded = json.loads(json.dumps(payload))
    if not isinstance(loaded, dict):
        raise ValueError("historical edge validation report must be an object")
    normalized = cast(dict[str, Any], loaded)
    required = {
        "schema_version",
        "report_id",
        "generated_at",
        "campaign_id",
        "source_report_id",
        "source_result_hash",
        "policy",
        "segment_count",
        "status_counts",
        "validated_out_of_sample_count",
        "results",
        "warnings",
    }
    missing = required.difference(normalized)
    if missing:
        raise ValueError(f"historical edge validation fields are missing: {sorted(missing)}")
    if normalized["schema_version"] != HISTORICAL_FUTURES_EDGE_VALIDATION_SCHEMA_VERSION:
        raise ValueError("unsupported historical futures edge validation schema version")
    results = normalized["results"]
    if not isinstance(results, list) or normalized["segment_count"] != len(results):
        raise ValueError("historical edge validation segment count must match results")
    return normalized


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _required_string(value: Mapping[str, object], key: str) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"historical edge {key} is required")
    return selected


def _required_int(value: Mapping[str, object], key: str) -> int:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int):
        raise ValueError(f"historical edge {key} must be an integer")
    return selected


def _required_float(value: Mapping[str, object], key: str) -> float:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int | float):
        raise ValueError(f"historical edge {key} must be numeric")
    return float(selected)


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
