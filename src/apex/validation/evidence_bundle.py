"""Canonical artifact-to-approval evidence bundle integration."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any


class EvidenceBundleStatus(StrEnum):
    """Stable outcome of resolving one exact setup evidence chain."""

    COMPLETE = "COMPLETE"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    MISSING_SEGMENT = "MISSING_SEGMENT"
    SEGMENT_MISMATCH = "SEGMENT_MISMATCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    STALE = "STALE"


class HistoricalValidationStatus(StrEnum):
    """Protocol-compatible historical validation states."""

    PASSED_VALIDATION = "PASSED_VALIDATION"
    INSUFFICIENT_OUT_OF_SAMPLE = "INSUFFICIENT_OUT_OF_SAMPLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    DEGRADED_VALIDATION = "DEGRADED_VALIDATION"


class ForwardValidationStatus(StrEnum):
    """Protocol-compatible forward-paper validation states."""

    PASSED_VALIDATION = "PASSED_VALIDATION"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class EvidenceQuality(StrEnum):
    VALIDATED_OUT_OF_SAMPLE = "VALIDATED_OUT_OF_SAMPLE"
    VALIDATED_FORWARD_PAPER = "VALIDATED_FORWARD_PAPER"


class EvidenceReason(StrEnum):
    HISTORICAL_SEGMENT_MISSING = "HISTORICAL_SEGMENT_MISSING"
    FORWARD_SEGMENT_MISSING = "FORWARD_SEGMENT_MISSING"
    HISTORICAL_SEGMENT_NOT_VALIDATED = "HISTORICAL_SEGMENT_NOT_VALIDATED"
    FORWARD_SEGMENT_NOT_VALIDATED = "FORWARD_SEGMENT_NOT_VALIDATED"
    REPORT_LINEAGE_MISMATCH = "REPORT_LINEAGE_MISMATCH"
    REPORT_STALE = "REPORT_STALE"
    SEGMENT_DIMENSIONS_MISMATCH = "SEGMENT_DIMENSIONS_MISMATCH"


@dataclass(frozen=True, slots=True)
class HistoricalValidationView:
    """Typed structural view consumed by historical strategy approval."""

    dimensions: Mapping[str, str]
    status: HistoricalValidationStatus
    out_of_sample_sample_size: int
    evidence_stable: bool
    promoted_evidence_quality: EvidenceQuality | None
    rejection_reasons: tuple[EvidenceReason, ...]
    warnings: tuple[EvidenceReason, ...]

    def __post_init__(self) -> None:
        if self.out_of_sample_sample_size < 0:
            raise ValueError("historical out-of-sample sample size cannot be negative")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class ForwardPaperProfile:
    """Forward-paper metrics exposed to the approval protocol."""

    dimensions: Mapping[str, str]
    sample_size: int
    win_rate: float
    expectancy: float
    profit_factor: float | None
    maximum_drawdown_r: float

    def __post_init__(self) -> None:
        if self.sample_size < 1:
            raise ValueError("forward-paper profile sample size must be positive")
        if not 0.0 <= self.win_rate <= 1.0:
            raise ValueError("forward-paper win rate must be in the unit interval")
        for value in (self.expectancy, self.maximum_drawdown_r):
            if not math.isfinite(value):
                raise ValueError("forward-paper profile metrics must be finite")
        if self.profit_factor is not None and (
            not math.isfinite(self.profit_factor) or self.profit_factor < 0.0
        ):
            raise ValueError("forward-paper profit factor must be finite and non-negative")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class ForwardValidationView:
    """Typed structural view consumed by forward-paper strategy approval."""

    dimensions: Mapping[str, str]
    status: ForwardValidationStatus
    forward_profile: ForwardPaperProfile | None
    expectancy_degradation_from_test: float | None
    consistent_edge_direction: bool
    evidence_stable: bool
    promoted_evidence_quality: EvidenceQuality | None
    rejection_reasons: tuple[EvidenceReason, ...]
    warnings: tuple[EvidenceReason, ...]

    def __post_init__(self) -> None:
        if self.expectancy_degradation_from_test is not None and (
            not math.isfinite(self.expectancy_degradation_from_test)
            or self.expectancy_degradation_from_test < 0.0
        ):
            raise ValueError("forward-paper expectancy degradation must be non-negative")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Verified exact-segment evidence chain ready for futures approval."""

    bundle_id: str
    campaign_id: str
    dimensions: Mapping[str, str]
    status: EvidenceBundleStatus
    historical_report_id: str
    forward_report_id: str | None
    historical: HistoricalValidationView | None
    forward: ForwardValidationView | None
    reasons: tuple[EvidenceReason, ...]
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.bundle_id.strip() or not self.campaign_id.strip():
            raise ValueError("evidence bundle identifiers cannot be empty")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(self.source_hashes)))

    def to_payload(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "campaign_id": self.campaign_id,
            "dimensions": dict(self.dimensions),
            "status": self.status.value,
            "historical_report_id": self.historical_report_id,
            "forward_report_id": self.forward_report_id,
            "historical": _historical_payload(self.historical),
            "forward": _forward_payload(self.forward),
            "reasons": [reason.value for reason in self.reasons],
            "source_hashes": dict(self.source_hashes),
        }


def load_evidence_bundle(
    *,
    historical_validation_path: Path,
    forward_validation_path: Path | None,
    dimensions: Mapping[str, str],
    as_of: datetime,
    maximum_age: timedelta | None = None,
) -> EvidenceBundle:
    """Load, verify, and resolve one exact setup evidence segment."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("evidence bundle as-of time must be timezone-aware")
    expected = _normalize_dimensions(dimensions)
    historical_document = _load_object(historical_validation_path)
    _verify_historical_document(historical_document)
    forward_document = (
        _load_object(forward_validation_path) if forward_validation_path is not None else None
    )
    if forward_document is not None:
        _verify_forward_document(forward_document)

    reasons: list[EvidenceReason] = []
    campaign_id = _required_string(historical_document, "campaign_id")
    historical_report_id = _required_string(historical_document, "report_id")
    forward_report_id: str | None = None

    if forward_document is not None:
        forward_report_id = _required_string(forward_document, "report_id")
        if (
            _required_string(forward_document, "campaign_id") != campaign_id
            or _required_string(forward_document, "source_validation_report_id")
            != historical_report_id
        ):
            reasons.append(EvidenceReason.REPORT_LINEAGE_MISMATCH)

    if maximum_age is not None:
        if maximum_age <= timedelta(0):
            raise ValueError("evidence maximum age must be positive")
        for document in tuple(
            item for item in (historical_document, forward_document) if item is not None
        ):
            generated_at = _required_datetime(document, "generated_at")
            if generated_at > as_of or as_of - generated_at > maximum_age:
                reasons.append(EvidenceReason.REPORT_STALE)
                break

    historical_item = _find_segment(historical_document, expected)
    if historical_item is None:
        reasons.append(EvidenceReason.HISTORICAL_SEGMENT_MISSING)
    forward_item = _find_segment(forward_document, expected) if forward_document else None
    if forward_document is not None and forward_item is None:
        reasons.append(EvidenceReason.FORWARD_SEGMENT_MISSING)

    historical = _historical_view(historical_item, expected) if historical_item else None
    forward = _forward_view(forward_item, expected) if forward_item else None
    if historical is not None and dict(historical.dimensions) != expected:
        reasons.append(EvidenceReason.SEGMENT_DIMENSIONS_MISMATCH)
    if forward is not None and dict(forward.dimensions) != expected:
        reasons.append(EvidenceReason.SEGMENT_DIMENSIONS_MISMATCH)
    if historical is not None and historical.promoted_evidence_quality is None:
        reasons.append(EvidenceReason.HISTORICAL_SEGMENT_NOT_VALIDATED)
    if forward is not None and forward.promoted_evidence_quality is None:
        reasons.append(EvidenceReason.FORWARD_SEGMENT_NOT_VALIDATED)

    deduplicated = tuple(dict.fromkeys(reasons))
    status = _bundle_status(
        reasons=deduplicated,
        historical=historical,
        forward=forward,
        forward_requested=forward_document is not None,
    )
    source_hashes = {
        "historical_validation": _hash_json(historical_document),
        **(
            {"forward_validation": _hash_json(forward_document)}
            if forward_document is not None
            else {}
        ),
    }
    identity = {
        "campaign_id": campaign_id,
        "dimensions": expected,
        "historical_report_id": historical_report_id,
        "forward_report_id": forward_report_id,
        "source_hashes": source_hashes,
    }
    return EvidenceBundle(
        bundle_id=f"evidence-bundle-{_hash_json(identity)[:24]}",
        campaign_id=campaign_id,
        dimensions=expected,
        status=status,
        historical_report_id=historical_report_id,
        forward_report_id=forward_report_id,
        historical=historical,
        forward=forward,
        reasons=deduplicated,
        source_hashes=source_hashes,
    )


def _historical_view(
    value: Mapping[str, Any], dimensions: Mapping[str, str]
) -> HistoricalValidationView:
    promoted = value.get("promoted_evidence_quality")
    status = HistoricalValidationStatus(_required_string(value, "status"))
    return HistoricalValidationView(
        dimensions=dimensions,
        status=status,
        out_of_sample_sample_size=_required_int(value, "out_of_sample_sample_size"),
        evidence_stable=bool(value.get("evidence_stable", False)),
        promoted_evidence_quality=(
            EvidenceQuality(str(promoted)) if promoted is not None else None
        ),
        rejection_reasons=_reason_tuple(value.get("rejection_reasons")),
        warnings=_reason_tuple(value.get("warnings")),
    )


def _forward_view(value: Mapping[str, Any], dimensions: Mapping[str, str]) -> ForwardValidationView:
    raw_status = _required_string(value, "status")
    sample_size = _required_int(value, "forward_sample_size")
    promoted = value.get("promoted_evidence_quality")
    passed = raw_status == "PASSED_FORWARD_PAPER"
    status = (
        ForwardValidationStatus.PASSED_VALIDATION
        if passed
        else (
            ForwardValidationStatus.INSUFFICIENT_SAMPLE
            if "FORWARD_SAMPLE_INSUFFICIENT" in value.get("rejection_reasons", [])
            else ForwardValidationStatus.FAILED_VALIDATION
        )
    )
    profile = None
    if sample_size > 0:
        profile = ForwardPaperProfile(
            dimensions=dimensions,
            sample_size=sample_size,
            win_rate=_required_float(value, "forward_win_rate"),
            expectancy=_required_float(value, "forward_expectancy"),
            profit_factor=_optional_float(value.get("forward_profit_factor")),
            maximum_drawdown_r=float(value.get("forward_maximum_drawdown_r", 0.0)),
        )
    return ForwardValidationView(
        dimensions=dimensions,
        status=status,
        forward_profile=profile,
        expectancy_degradation_from_test=_optional_float(value.get("expectancy_degradation")),
        consistent_edge_direction=passed,
        evidence_stable=passed,
        promoted_evidence_quality=(
            EvidenceQuality(str(promoted)) if promoted is not None else None
        ),
        rejection_reasons=_reason_tuple(value.get("rejection_reasons")),
        warnings=(),
    )


def _find_segment(
    document: Mapping[str, Any] | None,
    dimensions: Mapping[str, str],
) -> Mapping[str, Any] | None:
    if document is None:
        return None
    values = document.get("results")
    if not isinstance(values, list):
        raise ValueError("evidence report results must be a list")
    matches = [
        item
        for item in values
        if isinstance(item, Mapping)
        and _normalize_dimensions(_string_mapping(item.get("dimensions"))) == dimensions
    ]
    if len(matches) > 1:
        raise ValueError("evidence report contains duplicate setup segments")
    return matches[0] if matches else None


def _bundle_status(
    *,
    reasons: Sequence[EvidenceReason],
    historical: HistoricalValidationView | None,
    forward: ForwardValidationView | None,
    forward_requested: bool,
) -> EvidenceBundleStatus:
    if EvidenceReason.REPORT_LINEAGE_MISMATCH in reasons:
        return EvidenceBundleStatus.LINEAGE_MISMATCH
    if EvidenceReason.REPORT_STALE in reasons:
        return EvidenceBundleStatus.STALE
    if EvidenceReason.SEGMENT_DIMENSIONS_MISMATCH in reasons:
        return EvidenceBundleStatus.SEGMENT_MISMATCH
    if historical is None or (forward_requested and forward is None):
        return EvidenceBundleStatus.MISSING_SEGMENT
    if forward is None:
        return EvidenceBundleStatus.HISTORICAL_ONLY
    return EvidenceBundleStatus.COMPLETE


def _verify_historical_document(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported historical validation schema version")
    for key in ("report_id", "campaign_id", "generated_at", "results"):
        if key not in value:
            raise ValueError(f"historical validation {key} is required")


def _verify_forward_document(value: Mapping[str, Any]) -> None:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported forward validation schema version")
    for key in (
        "report_id",
        "campaign_id",
        "generated_at",
        "source_validation_report_id",
        "results",
    ):
        if key not in value:
            raise ValueError(f"forward validation {key} is required")


def _historical_payload(value: HistoricalValidationView | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "dimensions": dict(value.dimensions),
        "status": value.status.value,
        "out_of_sample_sample_size": value.out_of_sample_sample_size,
        "evidence_stable": value.evidence_stable,
        "promoted_evidence_quality": (
            value.promoted_evidence_quality.value
            if value.promoted_evidence_quality is not None
            else None
        ),
        "rejection_reasons": [item.value for item in value.rejection_reasons],
        "warnings": [item.value for item in value.warnings],
    }


def _forward_payload(value: ForwardValidationView | None) -> dict[str, Any] | None:
    if value is None:
        return None
    profile = value.forward_profile
    return {
        "dimensions": dict(value.dimensions),
        "status": value.status.value,
        "forward_profile": (
            {
                "dimensions": dict(profile.dimensions),
                "sample_size": profile.sample_size,
                "win_rate": profile.win_rate,
                "expectancy": profile.expectancy,
                "profit_factor": profile.profit_factor,
                "maximum_drawdown_r": profile.maximum_drawdown_r,
            }
            if profile is not None
            else None
        ),
        "expectancy_degradation_from_test": value.expectancy_degradation_from_test,
        "consistent_edge_direction": value.consistent_edge_direction,
        "evidence_stable": value.evidence_stable,
        "promoted_evidence_quality": (
            value.promoted_evidence_quality.value
            if value.promoted_evidence_quality is not None
            else None
        ),
        "rejection_reasons": [item.value for item in value.rejection_reasons],
        "warnings": [item.value for item in value.warnings],
    }


def _reason_tuple(value: object) -> tuple[EvidenceReason, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("evidence reasons must be a string list")
    output: list[EvidenceReason] = []
    for item in value:
        try:
            output.append(EvidenceReason(item))
        except ValueError:
            continue
    return tuple(output)


def _normalize_dimensions(value: Mapping[str, str]) -> dict[str, str]:
    # Ignore retired persisted keys while keeping new evidence canonical.
    if not value:
        raise ValueError("evidence dimensions cannot be empty")
    return dict(
        sorted(
            (key.strip(), item.strip())
            for key, item in value.items()
            if key.strip() != "scanner_type"
        )
    )


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("evidence dimensions must be a string mapping")
    return dict(value)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence artifact must contain a JSON object: {path}")
    return value


def _required_string(value: Mapping[str, Any], key: str) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"evidence {key} is required")
    return selected


def _required_int(value: Mapping[str, Any], key: str) -> int:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int):
        raise ValueError(f"evidence {key} must be an integer")
    return selected


def _required_float(value: Mapping[str, Any], key: str) -> float:
    selected = value.get(key)
    if isinstance(selected, bool) or not isinstance(selected, int | float):
        raise ValueError(f"evidence {key} must be numeric")
    result = float(selected)
    if not math.isfinite(result):
        raise ValueError(f"evidence {key} must be finite")
    return result


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("optional evidence metric must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("optional evidence metric must be finite")
    return result


def _required_datetime(value: Mapping[str, Any], key: str) -> datetime:
    parsed = datetime.fromisoformat(_required_string(value, key).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"evidence {key} must be timezone-aware")
    return parsed


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
