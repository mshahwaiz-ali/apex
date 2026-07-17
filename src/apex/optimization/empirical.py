"""Deterministic empirical calibration reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)
from apex.optimization.engine import (
    calibration_to_payload,
    compare_performance,
    evaluate_walk_forward_calibration,
    result_to_payload,
)

S10_EMPIRICAL_REPORT_SCHEMA_VERSION = 2
S10_SUPPORTED_EMPIRICAL_REPORT_SCHEMA_VERSIONS = frozenset({1, 2})


@dataclass(frozen=True, slots=True)
class StabilityPolicy:
    """Sample-distribution gates applied after train/validation selection."""

    minimum_symbols: int = 2
    minimum_regimes: int = 1
    minimum_score_bands: int = 1
    require_entry_actionability_distribution: bool = False
    minimum_entry_actionabilities: int = 1
    maximum_symbol_trade_share: float = 0.70
    maximum_regime_trade_share: float = 0.90
    maximum_score_band_trade_share: float = 0.90
    maximum_entry_actionability_trade_share: float = 0.90

    def __post_init__(self) -> None:
        for name in (
            "minimum_symbols",
            "minimum_regimes",
            "minimum_score_bands",
            "minimum_entry_actionabilities",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name.replace('_', ' ')} must be positive")
        for name in (
            "maximum_symbol_trade_share",
            "maximum_regime_trade_share",
            "maximum_score_band_trade_share",
            "maximum_entry_actionability_trade_share",
        ):
            value = getattr(self, name)
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name.replace('_', ' ')} must be in the interval (0, 1]")


@dataclass(frozen=True, slots=True)
class EmpiricalCalibrationReport:
    """Immutable selection, stability, and isolated final-test audit artifact."""

    payload: dict[str, Any]
    report_sha256: str


def build_empirical_calibration_report(
    *,
    split: WalkForwardSplit,
    run_config: OptimizationRunConfig,
    parameter_set: CandidateParameterSet,
    train_baseline: PerformanceSummary,
    train_candidate: PerformanceSummary,
    validation_baseline: PerformanceSummary,
    validation_candidate: PerformanceSummary,
    final_test_baseline: PerformanceSummary | None = None,
    final_test_candidate: PerformanceSummary | None = None,
    stability_policy: StabilityPolicy = StabilityPolicy(),
) -> EmpiricalCalibrationReport:
    """Select only on train/validation and audit final-test performance afterwards."""

    calibration = evaluate_walk_forward_calibration(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_baseline=train_baseline,
        train_candidate=train_candidate,
        validation_baseline=validation_baseline,
        validation_candidate=validation_candidate,
        final_test_baseline=final_test_baseline,
        final_test_candidate=final_test_candidate,
    )
    stability = _stability_payload(validation_candidate, stability_policy)
    selected = calibration.decision is OptimizationDecision.ACCEPTED and stability["passed"]

    final_test_audit: dict[str, Any] | None = None
    if selected and final_test_baseline is not None and final_test_candidate is not None:
        audit = compare_performance(
            final_test_baseline,
            final_test_candidate,
            run_config=run_config,
            parameter_set=parameter_set,
        )
        final_test_audit = {
            "decision": audit.decision.value,
            "reasons": list(audit.reasons),
            "used_for_selection": False,
            "comparison": result_to_payload(audit),
        }

    payload: dict[str, Any] = {
        "schema_version": S10_EMPIRICAL_REPORT_SCHEMA_VERSION,
        "selection": calibration_to_payload(calibration),
        "stability": stability,
        "selected_for_final_test_audit": selected,
        "final_test_audit": final_test_audit,
        "warnings": [
            "Final-test results are excluded from parameter selection.",
            "This report does not establish profitability or production readiness.",
        ],
    }
    report_hash = _hash_payload(payload)
    payload["report_sha256"] = report_hash
    return EmpiricalCalibrationReport(payload=payload, report_sha256=report_hash)


def write_empirical_calibration_report(
    report: EmpiricalCalibrationReport,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist one deterministic report without silent overwrite."""

    _validate_report_integrity(report)
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite empirical calibration report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validate_report_integrity(report: EmpiricalCalibrationReport) -> None:
    payload = dict(report.payload)
    embedded_hash = payload.pop("report_sha256", None)
    if not isinstance(embedded_hash, str) or not embedded_hash:
        raise ValueError("empirical calibration report embedded hash is missing")
    if embedded_hash != report.report_sha256:
        raise ValueError("empirical calibration report hash attribute does not match payload")
    if _hash_payload(payload) != embedded_hash:
        raise ValueError("empirical calibration report hash does not match its payload")
    _validate_report_schema_version(payload)


def load_and_verify_empirical_calibration_report(path: Path) -> EmpiricalCalibrationReport:
    """Reload a report and verify its deterministic hash."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("empirical calibration report must be a JSON object")
    payload = dict(value)
    report_hash = payload.pop("report_sha256", None)
    if not isinstance(report_hash, str) or not report_hash:
        raise ValueError("empirical calibration report hash is missing")
    if _hash_payload(payload) != report_hash:
        raise ValueError("empirical calibration report hash does not match its payload")
    _validate_report_schema_version(payload)
    payload["report_sha256"] = report_hash
    return EmpiricalCalibrationReport(payload=payload, report_sha256=report_hash)


def _validate_report_schema_version(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in S10_SUPPORTED_EMPIRICAL_REPORT_SCHEMA_VERSIONS
    ):
        raise ValueError("empirical calibration report schema version is unsupported")


def _stability_payload(
    summary: PerformanceSummary,
    policy: StabilityPolicy,
) -> dict[str, Any]:
    reasons: list[str] = []
    checks = [
        ("symbols", summary.by_symbol, policy.minimum_symbols, policy.maximum_symbol_trade_share),
        ("regimes", summary.by_regime, policy.minimum_regimes, policy.maximum_regime_trade_share),
        (
            "score_bands",
            summary.by_score_band,
            policy.minimum_score_bands,
            policy.maximum_score_band_trade_share,
        ),
    ]
    if summary.by_entry_actionability or policy.require_entry_actionability_distribution:
        checks.append(
            (
                "entry_actionabilities",
                summary.by_entry_actionability,
                policy.minimum_entry_actionabilities,
                policy.maximum_entry_actionability_trade_share,
            )
        )
    distributions: dict[str, dict[str, float | int]] = {}
    for label, counts, minimum_groups, maximum_share in checks:
        positive = {key: count for key, count in counts.items() if count > 0}
        largest_share = max(positive.values(), default=0) / summary.total_trades if summary.total_trades else 0.0
        distributions[label] = {
            "group_count": len(positive),
            "largest_trade_share": largest_share,
        }
        if len(positive) < minimum_groups:
            reasons.append(f"candidate does not cover enough {label.replace('_', ' ')}")
        if largest_share > maximum_share:
            reasons.append(f"candidate is too concentrated in one {label.replace('_', ' ')} group")
    return {
        "passed": not reasons,
        "reasons": reasons or ["candidate sample distribution passes stability gates"],
        "policy": {
            "minimum_symbols": policy.minimum_symbols,
            "minimum_regimes": policy.minimum_regimes,
            "minimum_score_bands": policy.minimum_score_bands,
            "require_entry_actionability_distribution": (
                policy.require_entry_actionability_distribution
            ),
            "minimum_entry_actionabilities": policy.minimum_entry_actionabilities,
            "maximum_symbol_trade_share": policy.maximum_symbol_trade_share,
            "maximum_regime_trade_share": policy.maximum_regime_trade_share,
            "maximum_score_band_trade_share": policy.maximum_score_band_trade_share,
            "maximum_entry_actionability_trade_share": (
                policy.maximum_entry_actionability_trade_share
            ),
        },
        "distributions": distributions,
    }


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
