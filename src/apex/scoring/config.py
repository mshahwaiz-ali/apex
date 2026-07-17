"""Immutable configuration for deterministic candidate scoring and selection."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from types import MappingProxyType

from apex.strategies.strategy_types import StrategyType

QUALITY_COMPONENTS: tuple[str, ...] = (
    "trend_alignment",
    "structure_quality",
    "entry_quality",
    "momentum_quality",
    "volume_quality",
    "liquidity_quality",
    "target_space_quality",
)

PENALTY_COMPONENTS: tuple[str, ...] = (
    "extension_penalty",
    "conflict_penalty",
    "provisional_penalty",
    "higher_timeframe_contradiction",
)


def _validate_unit(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between zero and one")


def _validate_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


def score_band_for(score: float) -> str:
    """Return the canonical deterministic score band for an opportunity score."""

    if not math.isfinite(score):
        raise ValueError("score must be finite")
    if not 0.0 <= score <= 100.0:
        raise ValueError("score must be between zero and 100")

    if score < 55.0:
        return "00_54"
    if score < 65.0:
        return "55_64"
    if score < 75.0:
        return "65_74"
    if score < 85.0:
        return "75_84"
    if score < 90.0:
        return "85_89"
    if score < 95.0:
        return "90_94"
    return "95_100"


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Explicit weights used by the bounded candidate score."""

    trend_alignment: float = 0.16
    structure_quality: float = 0.17
    entry_quality: float = 0.18
    momentum_quality: float = 0.12
    volume_quality: float = 0.09
    liquidity_quality: float = 0.11
    target_space_quality: float = 0.17

    def __post_init__(self) -> None:
        values = tuple(getattr(self, name) for name in QUALITY_COMPONENTS)
        for name, value in zip(QUALITY_COMPONENTS, values, strict=True):
            _validate_non_negative(name, value)
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("quality weights must sum to one")

    def as_mapping(self) -> Mapping[str, float]:
        return MappingProxyType({name: getattr(self, name) for name in QUALITY_COMPONENTS})


@dataclass(frozen=True, slots=True)
class PenaltyWeights:
    """Maximum deductions, expressed as score points on a 0-100 scale."""

    extension_penalty: float = 12.0
    conflict_penalty: float = 15.0
    provisional_penalty: float = 8.0
    higher_timeframe_contradiction: float = 18.0

    def __post_init__(self) -> None:
        for name in PENALTY_COMPONENTS:
            _validate_non_negative(name, getattr(self, name))

    def as_mapping(self) -> Mapping[str, float]:
        return MappingProxyType({name: getattr(self, name) for name in PENALTY_COMPONENTS})


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    """Centralized metric availability and neutral handling for one strategy."""

    neutral_metrics: frozenset[str] = frozenset()
    neutral_value: float = 0.5

    def __post_init__(self) -> None:
        unknown = self.neutral_metrics.difference(QUALITY_COMPONENTS)
        if unknown:
            raise ValueError(f"unknown neutral metrics: {sorted(unknown)}")
        _validate_unit("neutral value", self.neutral_value)


_DEFAULT_PROFILES: Mapping[StrategyType, StrategyProfile] = MappingProxyType(
    {
        StrategyType.MOMENTUM_BREAKOUT: StrategyProfile(
            neutral_metrics=frozenset({"liquidity_quality"})
        ),
        StrategyType.BREAKOUT_CONTINUATION: StrategyProfile(
            neutral_metrics=frozenset({"liquidity_quality"})
        ),
        StrategyType.BREAKOUT_RETEST: StrategyProfile(),
        StrategyType.FIRST_PULLBACK_CONTINUATION: StrategyProfile(
            neutral_metrics=frozenset({"liquidity_quality"})
        ),
        StrategyType.TREND_PULLBACK: StrategyProfile(),
        StrategyType.COMPRESSION_EXPANSION: StrategyProfile(),
        StrategyType.RANGE_REVERSAL: StrategyProfile(neutral_metrics=frozenset({"volume_quality"})),
        StrategyType.FAILED_BREAKOUT_REVERSAL: StrategyProfile(),
        StrategyType.LIQUIDITY_REJECTION_REVERSAL: StrategyProfile(
            neutral_metrics=frozenset({"volume_quality"})
        ),
        StrategyType.VWAP_RECLAIM_REJECTION: StrategyProfile(),
        StrategyType.MOMENTUM_SCALP: StrategyProfile(
            neutral_metrics=frozenset({"liquidity_quality"})
        ),
        StrategyType.EXHAUSTION_REVERSAL: StrategyProfile(),
    }
)


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Complete immutable candidate-scoring configuration snapshot."""

    identifier: str = "phase5-default-v1"
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    penalties: PenaltyWeights = field(default_factory=PenaltyWeights)
    strategy_profiles: Mapping[StrategyType, StrategyProfile] = field(
        default_factory=lambda: _DEFAULT_PROFILES
    )
    minimum_accept_score: float = 58.0
    warning_accept_score: float = 52.0
    unresolved_conflict_margin: float = 4.0
    consensus_bonus_per_supporter: float = 2.0
    maximum_consensus_bonus: float = 6.0
    duplicate_entry_overlap: float = 0.60
    duplicate_price_tolerance: float = 0.35

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("configuration identifier cannot be empty")
        for name in (
            "minimum_accept_score",
            "warning_accept_score",
            "unresolved_conflict_margin",
            "consensus_bonus_per_supporter",
            "maximum_consensus_bonus",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be finite and between zero and 100")
        if self.warning_accept_score > self.minimum_accept_score:
            raise ValueError("warning accept score cannot exceed minimum accept score")
        _validate_unit("duplicate entry overlap", self.duplicate_entry_overlap)
        _validate_unit("duplicate price tolerance", self.duplicate_price_tolerance)

        profiles = dict(self.strategy_profiles)
        if set(profiles) != set(StrategyType):
            raise ValueError("strategy profiles must cover every registered strategy type")
        object.__setattr__(self, "strategy_profiles", MappingProxyType(profiles))

    def fingerprint(self) -> str:
        """Return a stable hash for reproducible scoring reports."""

        payload = {
            "identifier": self.identifier,
            "weights": asdict(self.weights),
            "penalties": asdict(self.penalties),
            "strategy_profiles": {
                strategy.value: {
                    "neutral_metrics": sorted(profile.neutral_metrics),
                    "neutral_value": profile.neutral_value,
                }
                for strategy, profile in sorted(
                    self.strategy_profiles.items(),
                    key=lambda item: item[0].value,
                )
            },
            "minimum_accept_score": self.minimum_accept_score,
            "warning_accept_score": self.warning_accept_score,
            "unresolved_conflict_margin": self.unresolved_conflict_margin,
            "consensus_bonus_per_supporter": self.consensus_bonus_per_supporter,
            "maximum_consensus_bonus": self.maximum_consensus_bonus,
            "duplicate_entry_overlap": self.duplicate_entry_overlap,
            "duplicate_price_tolerance": self.duplicate_price_tolerance,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_SCORING_CONFIG = ScoringConfig()
