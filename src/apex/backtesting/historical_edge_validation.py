"""Deterministic out-of-sample validation for historical edge profiles."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from apex.backtesting.historical_edge import (
    DEFAULT_EDGE_SEGMENTS,
    EvidenceQuality,
    HistoricalEdgeProfile,
    aggregate_historical_edges,
)
from apex.backtesting.historical_edge_split import HistoricalEdgeSplitSet


class HistoricalEdgeValidationStatus(StrEnum):
    """Stable outcome of one train/validation/test edge evaluation."""

    INSUFFICIENT_OUT_OF_SAMPLE = "INSUFFICIENT_OUT_OF_SAMPLE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    DEGRADED_VALIDATION = "DEGRADED_VALIDATION"
    PASSED_VALIDATION = "PASSED_VALIDATION"


class HistoricalEdgeValidationReason(StrEnum):
    """Machine-readable validation rejection and warning codes."""

    MISSING_TRAIN_SEGMENT = "MISSING_TRAIN_SEGMENT"
    MISSING_VALIDATION_SEGMENT = "MISSING_VALIDATION_SEGMENT"
    MISSING_TEST_SEGMENT = "MISSING_TEST_SEGMENT"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    TRAIN_EVIDENCE_INADEQUATE = "TRAIN_EVIDENCE_INADEQUATE"
    VALIDATION_SAMPLE_INSUFFICIENT = "VALIDATION_SAMPLE_INSUFFICIENT"
    TEST_SAMPLE_INSUFFICIENT = "TEST_SAMPLE_INSUFFICIENT"
    OUT_OF_SAMPLE_SAMPLE_INSUFFICIENT = "OUT_OF_SAMPLE_SAMPLE_INSUFFICIENT"
    VALIDATION_EXPECTANCY_NOT_POSITIVE = "VALIDATION_EXPECTANCY_NOT_POSITIVE"
    TEST_EXPECTANCY_NOT_POSITIVE = "TEST_EXPECTANCY_NOT_POSITIVE"
    VALIDATION_PROFIT_FACTOR_INADEQUATE = "VALIDATION_PROFIT_FACTOR_INADEQUATE"
    TEST_PROFIT_FACTOR_INADEQUATE = "TEST_PROFIT_FACTOR_INADEQUATE"
    VALIDATION_EXPECTANCY_DEGRADATION_EXCESSIVE = "VALIDATION_EXPECTANCY_DEGRADATION_EXCESSIVE"
    TEST_EXPECTANCY_DEGRADATION_EXCESSIVE = "TEST_EXPECTANCY_DEGRADATION_EXCESSIVE"
    EDGE_DIRECTION_INCONSISTENT = "EDGE_DIRECTION_INCONSISTENT"
    FORWARD_PAPER_VALIDATION_REQUIRED = "FORWARD_PAPER_VALIDATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class HistoricalEdgeValidationPolicy:
    """Typed thresholds for deterministic out-of-sample evidence promotion."""

    minimum_validation_trades: int = 50
    minimum_test_trades: int = 50
    minimum_out_of_sample_trades: int = 100
    minimum_profit_factor: float = 1.0
    maximum_validation_expectancy_degradation: float = 0.50
    maximum_test_expectancy_degradation: float = 0.60
    eligible_train_qualities: frozenset[EvidenceQuality] = field(
        default_factory=lambda: frozenset(
            {EvidenceQuality.PROMISING, EvidenceQuality.VALIDATED_BACKTEST}
        )
    )

    def __post_init__(self) -> None:
        for name in (
            "minimum_validation_trades",
            "minimum_test_trades",
            "minimum_out_of_sample_trades",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name.replace('_', ' ')} must be positive")
        for name in (
            "minimum_profit_factor",
            "maximum_validation_expectancy_degradation",
            "maximum_test_expectancy_degradation",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} must be finite and non-negative")
        if not self.eligible_train_qualities:
            raise ValueError("eligible train qualities cannot be empty")
        forbidden = self.eligible_train_qualities & {
            EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
            EvidenceQuality.VALIDATED_FORWARD_PAPER,
            EvidenceQuality.PRODUCTION_ELIGIBLE,
        }
        if forbidden:
            raise ValueError("train eligibility cannot depend on externally promoted evidence")


@dataclass(frozen=True, slots=True)
class HistoricalEdgeValidationResult:
    """Immutable out-of-sample evaluation preserving all source profiles."""

    dimensions: Mapping[str, str]
    status: HistoricalEdgeValidationStatus
    train_profile: HistoricalEdgeProfile | None
    validation_profile: HistoricalEdgeProfile | None
    test_profile: HistoricalEdgeProfile | None
    out_of_sample_sample_size: int
    train_expectancy: float | None
    validation_expectancy: float | None
    test_expectancy: float | None
    validation_profit_factor: float | None
    test_profit_factor: float | None
    validation_expectancy_degradation: float | None
    test_expectancy_degradation: float | None
    consistent_edge_direction: bool
    evidence_stable: bool
    promoted_evidence_quality: EvidenceQuality | None
    rejection_reasons: tuple[HistoricalEdgeValidationReason, ...] = field(default_factory=tuple)
    warnings: tuple[HistoricalEdgeValidationReason, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.out_of_sample_sample_size < 0:
            raise ValueError("out-of-sample sample size cannot be negative")
        for name in (
            "train_expectancy",
            "validation_expectancy",
            "test_expectancy",
            "validation_profit_factor",
            "test_profit_factor",
            "validation_expectancy_degradation",
            "test_expectancy_degradation",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite when present")
        if self.promoted_evidence_quality not in {
            None,
            EvidenceQuality.VALIDATED_OUT_OF_SAMPLE,
        }:
            raise ValueError("V1.4 can only promote evidence to validated out-of-sample")
        if self.status is HistoricalEdgeValidationStatus.PASSED_VALIDATION:
            if self.promoted_evidence_quality is not EvidenceQuality.VALIDATED_OUT_OF_SAMPLE:
                raise ValueError("passed validation must promote out-of-sample evidence")
            if self.rejection_reasons:
                raise ValueError("passed validation cannot contain rejection reasons")
        elif self.promoted_evidence_quality is not None:
            raise ValueError("failed or incomplete validation cannot promote evidence")
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


def evaluate_historical_edge_splits(
    split_set: HistoricalEdgeSplitSet,
    *,
    segment_by: Sequence[str] = DEFAULT_EDGE_SEGMENTS,
    policy: HistoricalEdgeValidationPolicy | None = None,
) -> tuple[HistoricalEdgeValidationResult, ...]:
    """Aggregate and evaluate matching segments across leakage-guarded splits."""

    dimensions = tuple(segment_by)
    train_profiles = aggregate_historical_edges(split_set.train.trades, segment_by=dimensions)
    validation_profiles = aggregate_historical_edges(
        split_set.validation.trades, segment_by=dimensions
    )
    test_profiles = aggregate_historical_edges(split_set.test.trades, segment_by=dimensions)
    return validate_out_of_sample_edges(
        train_profiles,
        validation_profiles,
        test_profiles,
        policy=policy,
    )


def validate_out_of_sample_edges(
    train_profiles: Sequence[HistoricalEdgeProfile],
    validation_profiles: Sequence[HistoricalEdgeProfile],
    test_profiles: Sequence[HistoricalEdgeProfile],
    *,
    policy: HistoricalEdgeValidationPolicy | None = None,
) -> tuple[HistoricalEdgeValidationResult, ...]:
    """Match immutable profiles by dimensions and evaluate each stable segment key."""

    resolved_policy = policy or HistoricalEdgeValidationPolicy()
    train = _profile_index(train_profiles, "train")
    validation = _profile_index(validation_profiles, "validation")
    test = _profile_index(test_profiles, "test")
    keys = sorted(set(train) | set(validation) | set(test))
    return tuple(
        _evaluate_segment(
            key,
            train.get(key),
            validation.get(key),
            test.get(key),
            resolved_policy,
        )
        for key in keys
    )


SegmentKey = tuple[tuple[str, str], ...]


def _profile_index(
    profiles: Sequence[HistoricalEdgeProfile], role: str
) -> dict[SegmentKey, HistoricalEdgeProfile]:
    indexed: dict[SegmentKey, HistoricalEdgeProfile] = {}
    for profile in profiles:
        key = tuple(sorted(profile.dimensions.items()))
        if key in indexed:
            raise ValueError(f"duplicate {role} historical edge segment")
        indexed[key] = profile
    return indexed


def _evaluate_segment(
    key: SegmentKey,
    train: HistoricalEdgeProfile | None,
    validation: HistoricalEdgeProfile | None,
    test: HistoricalEdgeProfile | None,
    policy: HistoricalEdgeValidationPolicy,
) -> HistoricalEdgeValidationResult:
    dimensions = dict(key)
    reasons: list[HistoricalEdgeValidationReason] = []
    warnings: list[HistoricalEdgeValidationReason] = []

    if train is None:
        reasons.append(HistoricalEdgeValidationReason.MISSING_TRAIN_SEGMENT)
    if validation is None:
        reasons.append(HistoricalEdgeValidationReason.MISSING_VALIDATION_SEGMENT)
    if test is None:
        reasons.append(HistoricalEdgeValidationReason.MISSING_TEST_SEGMENT)

    profiles = tuple(profile for profile in (train, validation, test) if profile is not None)
    if any(dict(profile.dimensions) != dimensions for profile in profiles):
        reasons.append(HistoricalEdgeValidationReason.DIMENSION_MISMATCH)

    if train is not None and train.evidence_quality not in policy.eligible_train_qualities:
        reasons.append(HistoricalEdgeValidationReason.TRAIN_EVIDENCE_INADEQUATE)
    if validation is not None and validation.sample_size < policy.minimum_validation_trades:
        reasons.append(HistoricalEdgeValidationReason.VALIDATION_SAMPLE_INSUFFICIENT)
    if test is not None and test.sample_size < policy.minimum_test_trades:
        reasons.append(HistoricalEdgeValidationReason.TEST_SAMPLE_INSUFFICIENT)

    out_of_sample_size = (validation.sample_size if validation else 0) + (
        test.sample_size if test else 0
    )
    if out_of_sample_size < policy.minimum_out_of_sample_trades:
        reasons.append(HistoricalEdgeValidationReason.OUT_OF_SAMPLE_SAMPLE_INSUFFICIENT)

    if validation is not None:
        if validation.expectancy <= 0.0:
            reasons.append(HistoricalEdgeValidationReason.VALIDATION_EXPECTANCY_NOT_POSITIVE)
        if not _profit_factor_exceeds(validation.profit_factor, policy.minimum_profit_factor):
            reasons.append(HistoricalEdgeValidationReason.VALIDATION_PROFIT_FACTOR_INADEQUATE)
    if test is not None:
        if test.expectancy <= 0.0:
            reasons.append(HistoricalEdgeValidationReason.TEST_EXPECTANCY_NOT_POSITIVE)
        if not _profit_factor_exceeds(test.profit_factor, policy.minimum_profit_factor):
            reasons.append(HistoricalEdgeValidationReason.TEST_PROFIT_FACTOR_INADEQUATE)

    validation_degradation = _expectancy_degradation(train, validation)
    test_degradation = _expectancy_degradation(train, test)
    if (
        validation_degradation is not None
        and validation_degradation > policy.maximum_validation_expectancy_degradation
    ):
        reasons.append(HistoricalEdgeValidationReason.VALIDATION_EXPECTANCY_DEGRADATION_EXCESSIVE)
    if (
        test_degradation is not None
        and test_degradation > policy.maximum_test_expectancy_degradation
    ):
        reasons.append(HistoricalEdgeValidationReason.TEST_EXPECTANCY_DEGRADATION_EXCESSIVE)

    consistent_direction = bool(
        train is not None
        and validation is not None
        and test is not None
        and train.expectancy > 0.0
        and validation.expectancy > 0.0
        and test.expectancy > 0.0
    )
    if profiles and not consistent_direction:
        reasons.append(HistoricalEdgeValidationReason.EDGE_DIRECTION_INCONSISTENT)

    reasons = list(dict.fromkeys(reasons))
    insufficient_codes = {
        HistoricalEdgeValidationReason.MISSING_TRAIN_SEGMENT,
        HistoricalEdgeValidationReason.MISSING_VALIDATION_SEGMENT,
        HistoricalEdgeValidationReason.MISSING_TEST_SEGMENT,
        HistoricalEdgeValidationReason.TRAIN_EVIDENCE_INADEQUATE,
        HistoricalEdgeValidationReason.VALIDATION_SAMPLE_INSUFFICIENT,
        HistoricalEdgeValidationReason.TEST_SAMPLE_INSUFFICIENT,
        HistoricalEdgeValidationReason.OUT_OF_SAMPLE_SAMPLE_INSUFFICIENT,
    }
    degradation_codes = {
        HistoricalEdgeValidationReason.VALIDATION_EXPECTANCY_DEGRADATION_EXCESSIVE,
        HistoricalEdgeValidationReason.TEST_EXPECTANCY_DEGRADATION_EXCESSIVE,
    }
    if any(reason in insufficient_codes for reason in reasons):
        status = HistoricalEdgeValidationStatus.INSUFFICIENT_OUT_OF_SAMPLE
    elif any(reason not in degradation_codes for reason in reasons):
        status = HistoricalEdgeValidationStatus.FAILED_VALIDATION
    elif reasons:
        status = HistoricalEdgeValidationStatus.DEGRADED_VALIDATION
    else:
        status = HistoricalEdgeValidationStatus.PASSED_VALIDATION

    evidence_stable = status is HistoricalEdgeValidationStatus.PASSED_VALIDATION
    promoted = EvidenceQuality.VALIDATED_OUT_OF_SAMPLE if evidence_stable else None
    if promoted is EvidenceQuality.VALIDATED_OUT_OF_SAMPLE:
        warnings.append(HistoricalEdgeValidationReason.FORWARD_PAPER_VALIDATION_REQUIRED)

    return HistoricalEdgeValidationResult(
        dimensions=dimensions,
        status=status,
        train_profile=train,
        validation_profile=validation,
        test_profile=test,
        out_of_sample_sample_size=out_of_sample_size,
        train_expectancy=train.expectancy if train else None,
        validation_expectancy=validation.expectancy if validation else None,
        test_expectancy=test.expectancy if test else None,
        validation_profit_factor=validation.profit_factor if validation else None,
        test_profit_factor=test.profit_factor if test else None,
        validation_expectancy_degradation=validation_degradation,
        test_expectancy_degradation=test_degradation,
        consistent_edge_direction=consistent_direction,
        evidence_stable=evidence_stable,
        promoted_evidence_quality=promoted,
        rejection_reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def _profit_factor_exceeds(value: float | None, minimum: float) -> bool:
    return value is None or value > minimum


def _expectancy_degradation(
    train: HistoricalEdgeProfile | None,
    later: HistoricalEdgeProfile | None,
) -> float | None:
    if train is None or later is None or train.expectancy <= 0.0:
        return None
    return (train.expectancy - later.expectancy) / train.expectancy
