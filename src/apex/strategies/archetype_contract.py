"""Typed strategy-archetype compatibility contracts for Batch 6."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.contracts import (
    EntryMode,
    InvalidationType,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.strategy_types import StrategyType


class ArchetypeFamily(StrEnum):
    MOMENTUM_CONTINUATION = "momentum_continuation"
    BREAKOUT_RETEST = "breakout_retest"
    FIRST_PULLBACK = "first_pullback"
    VWAP_RECLAIM_REJECTION = "vwap_reclaim_rejection"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    FAILED_BREAKOUT = "failed_breakout"
    COMPRESSION_EXPANSION = "compression_expansion"
    EXHAUSTION_REVERSAL = "exhaustion_reversal"


@dataclass(frozen=True, slots=True)
class StrategyArchetypeProfile:
    archetype: ArchetypeFamily
    strategy: StrategyType
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    contradictions: tuple[str, ...]
    entry_modes: tuple[EntryMode, ...]
    invalidation_type: InvalidationType
    target_types: tuple[TargetType, ...]
    confirmation_complete: bool
    provisional: bool
    regime_eligible: bool
    explanation_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.required_evidence:
            raise ValueError("archetype profile requires evidence")
        if not self.entry_modes:
            raise ValueError("archetype profile requires at least one entry mode")
        if not self.target_types:
            raise ValueError("archetype profile requires at least one target type")
        if not self.explanation_labels:
            raise ValueError("archetype profile requires explanation labels")
        for name, values in (
            ("required evidence", self.required_evidence),
            ("optional evidence", self.optional_evidence),
            ("contradictions", self.contradictions),
            ("entry modes", self.entry_modes),
            ("target types", self.target_types),
            ("explanation labels", self.explanation_labels),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")


def breakout_retest_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt the current breakout-retest candidate into the common contract."""

    if candidate.strategy is not StrategyType.BREAKOUT_RETEST:
        raise ValueError("breakout-retest profile requires a breakout-retest candidate")

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    has_breakout_context = bool(
        metadata.get("higher_timeframe_breakout_continuation", False)
    ) or any(
        "breakout context" in item or "breakout expansion" in item
        for item in candidate.evidence.supporting
    )
    has_retest_geometry = any(
        item.mode in {EntryMode.RETEST, EntryMode.PULLBACK}
        for item in candidate.entry_opportunities
    ) or any("retest" in item or "reclaim" in item for item in candidate.evidence.supporting)

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    confirmation_complete = (
        has_breakout_context and has_retest_geometry and not candidate.provisional
    )

    optional_evidence = tuple(
        item
        for item, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit breakout-retest family metadata",
                family == StrategyType.BREAKOUT_RETEST.value,
            ),
            (
                "higher-timeframe breakout continuation",
                bool(metadata.get("higher_timeframe_breakout_continuation", False)),
            ),
            ("liquidity evidence", bool(candidate.evidence.liquidity_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.BREAKOUT_RETEST,
        strategy=candidate.strategy,
        required_evidence=(
            "confirmed breakout context",
            "lower-timeframe retest or reclaim geometry",
            "valid directional invalidation and target geometry",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=has_breakout_context,
        explanation_labels=(
            "breakout retest",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def first_pullback_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt a first-pullback continuation candidate into the common contract."""

    if candidate.strategy is not StrategyType.FIRST_PULLBACK_CONTINUATION:
        raise ValueError("first-pullback profile requires a first-pullback-continuation candidate")

    metadata = candidate.metadata
    reference_count = int(metadata.get("reference_count", 0))
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    close_to_cmp = candidate.entry.atr_distance <= 1.0
    not_extended = not candidate.entry.is_extended
    has_reference = reference_count >= 1 or any(
        "continuation reference" in item for item in candidate.evidence.supporting
    )

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    confirmation_complete = (
        has_reference and close_to_cmp and not_extended and not candidate.provisional
    )

    optional_evidence = tuple(
        item
        for item, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit first-pullback family metadata",
                family == StrategyType.FIRST_PULLBACK_CONTINUATION.value,
            ),
            ("EMA continuation reference", "ema_fast" in candidate.evidence.feature_references),
            ("VWAP continuation reference", "vwap" in candidate.evidence.feature_references),
            ("liquidity evidence", bool(candidate.evidence.liquidity_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.FIRST_PULLBACK,
        strategy=candidate.strategy,
        required_evidence=(
            "first actionable pullback near current price",
            "at least one structural, EMA, or VWAP continuation reference",
            "entry remains within one ATR and is not extended",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=has_reference and close_to_cmp and not_extended,
        explanation_labels=(
            "first pullback continuation",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def vwap_reclaim_rejection_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt a VWAP reclaim/rejection candidate into the common contract."""

    if candidate.strategy is not StrategyType.VWAP_RECLAIM_REJECTION:
        raise ValueError("VWAP profile requires a VWAP-reclaim-rejection candidate")

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    has_vwap_reference = "vwap" in candidate.evidence.feature_references or any(
        "VWAP" in item for item in candidate.evidence.supporting
    )
    close_to_vwap = candidate.entry.atr_distance <= 1.25
    not_extended = not candidate.entry.is_extended

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    confirmation_complete = (
        has_vwap_reference and close_to_vwap and not_extended and not candidate.provisional
    )

    optional_evidence = tuple(
        item
        for item, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit VWAP family metadata",
                family == StrategyType.VWAP_RECLAIM_REJECTION.value,
            ),
            ("EMA confluence", "ema_fast" in candidate.evidence.feature_references),
            ("liquidity evidence", bool(candidate.evidence.liquidity_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.VWAP_RECLAIM_REJECTION,
        strategy=candidate.strategy,
        required_evidence=(
            "VWAP is present as the active reclaim or rejection reference",
            "entry remains within one and one-quarter ATR of the reference",
            "entry is not extended",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=has_vwap_reference and close_to_vwap and not_extended,
        explanation_labels=(
            "VWAP reclaim or rejection",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def liquidity_sweep_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt a liquidity-rejection reversal into the common contract."""

    if candidate.strategy is not StrategyType.LIQUIDITY_REJECTION_REVERSAL:
        raise ValueError(
            "liquidity-sweep profile requires a liquidity-rejection-reversal candidate"
        )

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    has_sweep_rejection = any(
        "liquidity sweep" in item and "rejection" in item for item in candidate.evidence.supporting
    )
    boundary_recovered = any(
        "recovered the swept boundary" in item for item in candidate.evidence.supporting
    )
    has_liquidity_reference = bool(candidate.evidence.liquidity_references)

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    confirmation_complete = (
        has_sweep_rejection
        and boundary_recovered
        and has_liquidity_reference
        and not candidate.provisional
    )

    optional_evidence = tuple(
        item
        for item, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit liquidity-rejection family metadata",
                family == StrategyType.LIQUIDITY_REJECTION_REVERSAL.value,
            ),
            ("structure evidence", bool(candidate.evidence.structure_references)),
            ("momentum evidence", bool(candidate.evidence.feature_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.LIQUIDITY_SWEEP,
        strategy=candidate.strategy,
        required_evidence=(
            "confirmed liquidity sweep and trap rejection",
            "recovery of the swept boundary before entry",
            "explicit liquidity reference",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=(has_sweep_rejection and boundary_recovered and has_liquidity_reference),
        explanation_labels=(
            "liquidity sweep reversal",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def exhaustion_reversal_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt exhaustion-reversal evidence into the common contract."""

    if candidate.strategy is not StrategyType.EXHAUSTION_REVERSAL:
        raise ValueError("exhaustion-reversal profile requires an exhaustion-reversal candidate")

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    raw_exhaustion_rsi = metadata.get("exhaustion_rsi")
    exhaustion_rsi = (
        float(raw_exhaustion_rsi) if isinstance(raw_exhaustion_rsi, int | float) else None
    )
    directionally_exhausted = exhaustion_rsi is not None and (
        (candidate.direction is TradeDirection.LONG and exhaustion_rsi <= 35.0)
        or (candidate.direction is TradeDirection.SHORT and exhaustion_rsi >= 65.0)
    )
    has_rsi_evidence = any(
        item.startswith("RSI exhaustion is confirmed at ") for item in candidate.evidence.supporting
    )
    has_liquidity_trigger = any(
        "liquidity rejection provides the reversal trigger" in item
        for item in candidate.evidence.supporting
    )
    has_rsi_reference = "rsi" in candidate.evidence.feature_references
    has_liquidity_reference = bool(candidate.evidence.liquidity_references)

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    regime_eligible = (
        directionally_exhausted
        and has_rsi_evidence
        and has_liquidity_trigger
        and has_rsi_reference
        and has_liquidity_reference
    )
    confirmation_complete = regime_eligible and not candidate.provisional

    optional_evidence = tuple(
        label
        for label, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit exhaustion-reversal family metadata",
                family == StrategyType.EXHAUSTION_REVERSAL.value,
            ),
            (
                "structure evidence",
                bool(candidate.evidence.structure_references),
            ),
            (
                "additional momentum evidence",
                any(item != "rsi" for item in candidate.evidence.feature_references),
            ),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.EXHAUSTION_REVERSAL,
        strategy=candidate.strategy,
        required_evidence=(
            "directional RSI exhaustion",
            "explicit RSI exhaustion evidence",
            "liquidity rejection reversal trigger",
            "RSI feature reference",
            "liquidity reference",
        ),
        optional_evidence=optional_evidence,
        contradictions=(candidate.evidence.contradictions + candidate.evidence.warnings),
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=regime_eligible,
        explanation_labels=(
            "exhaustion reversal",
            (f"RSI {exhaustion_rsi:.2f}" if exhaustion_rsi is not None else "missing RSI"),
            ("confirmation complete" if confirmation_complete else "confirmation incomplete"),
            ("provisional evidence" if candidate.provisional else "closed evidence"),
        ),
    )


def compression_expansion_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt compression-expansion evidence into the common contract."""

    if candidate.strategy is not StrategyType.COMPRESSION_EXPANSION:
        raise ValueError("compression-expansion profile requires a compression-expansion candidate")

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    regime = str(metadata.get("compression_expansion_regime", ""))
    has_supported_regime = regime in {"compression", "breakout_expansion"}
    has_regime_evidence = any(
        item == f"{regime} context supports directional expansion"
        for item in candidate.evidence.supporting
    )
    has_release_evidence = any(
        "confirmed breakout provides release from the prior volatility state" in item
        for item in candidate.evidence.supporting
    )
    has_structure_reference = "compression_expansion" in candidate.evidence.structure_references

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    regime_eligible = (
        has_supported_regime
        and has_regime_evidence
        and has_release_evidence
        and has_structure_reference
    )
    confirmation_complete = regime_eligible and not candidate.provisional

    optional_evidence = tuple(
        label
        for label, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit compression-expansion family metadata",
                family == StrategyType.COMPRESSION_EXPANSION.value,
            ),
            ("momentum evidence", bool(candidate.evidence.feature_references)),
            ("liquidity evidence", bool(candidate.evidence.liquidity_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.COMPRESSION_EXPANSION,
        strategy=candidate.strategy,
        required_evidence=(
            "supported compression or breakout-expansion regime",
            "directional expansion context",
            "confirmed breakout release",
            "explicit compression-expansion structure reference",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=regime_eligible,
        explanation_labels=(
            "compression expansion",
            regime or "missing regime",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def failed_breakout_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt a failed-breakout reversal into the common contract."""

    if candidate.strategy is not StrategyType.FAILED_BREAKOUT_REVERSAL:
        raise ValueError("failed-breakout profile requires a failed-breakout-reversal candidate")

    metadata = candidate.metadata
    source_strategy = str(metadata.get("source_strategy", ""))
    family = str(metadata.get("strategy_family", ""))
    confirmed_failed_breakout = metadata.get("confirmed_failed_breakout") is True
    rejected_beyond_boundary = any(
        "failed breakout rejected beyond the range boundary" in item
        for item in candidate.evidence.supporting
    )
    returned_inside_range = any(
        "returned into the prior range before entry selection" in item
        for item in candidate.evidence.supporting
    )
    has_failed_breakout_structure = "failed_breakout" in candidate.evidence.structure_references

    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))
    confirmation_complete = (
        confirmed_failed_breakout
        and rejected_beyond_boundary
        and returned_inside_range
        and has_failed_breakout_structure
        and not candidate.provisional
    )

    optional_evidence = tuple(
        item
        for item, present in (
            ("source strategy lineage", bool(source_strategy)),
            (
                "explicit failed-breakout family metadata",
                family == StrategyType.FAILED_BREAKOUT_REVERSAL.value,
            ),
            ("momentum evidence", bool(candidate.evidence.feature_references)),
            ("liquidity evidence", bool(candidate.evidence.liquidity_references)),
        )
        if present
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.FAILED_BREAKOUT,
        strategy=candidate.strategy,
        required_evidence=(
            "confirmed failed-breakout state",
            "rejection beyond the attempted range boundary",
            "return inside the prior range before entry",
            "explicit failed-breakout structure reference",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=(
            confirmed_failed_breakout
            and rejected_beyond_boundary
            and returned_inside_range
            and has_failed_breakout_structure
        ),
        explanation_labels=(
            "failed breakout reversal",
            "confirmation complete" if confirmation_complete else "confirmation incomplete",
            "provisional evidence" if candidate.provisional else "closed evidence",
        ),
    )


def momentum_continuation_archetype_profile(
    candidate: TradeCandidate,
) -> StrategyArchetypeProfile:
    """Adapt the current momentum candidate into the common archetype contract."""

    if candidate.strategy is not StrategyType.MOMENTUM_BREAKOUT:
        raise ValueError("momentum continuation profile requires a momentum-breakout candidate")

    metadata = candidate.metadata
    confirmation_complete = bool(metadata.get("entry_confirmation_complete", False))
    has_trend_or_break = bool(metadata.get("recent_continuation_break", False)) or any(
        "directional trend" in item for item in candidate.evidence.supporting
    )
    entry_modes = tuple(dict.fromkeys(item.mode for item in candidate.entry_opportunities))
    target_types = tuple(dict.fromkeys(item.kind for item in candidate.targets.levels))

    optional_evidence = tuple(
        item
        for item in (
            "relative volume",
            "fast EMA continuation reference",
            "VWAP continuation reference",
            "higher-timeframe alignment",
        )
        if (
            item == "relative volume" and "relative_volume" in candidate.evidence.feature_references
        )
        or (
            item == "fast EMA continuation reference"
            and "ema_fast" in candidate.evidence.feature_references
        )
        or (
            item == "VWAP continuation reference"
            and "vwap" in candidate.evidence.feature_references
        )
        or (
            item == "higher-timeframe alignment"
            and not bool(metadata.get("higher_timeframe_conflict", False))
        )
    )

    explanation_labels = (
        "momentum continuation",
        "confirmation complete" if confirmation_complete else "confirmation incomplete",
        "provisional evidence" if candidate.provisional else "closed evidence",
    )

    return StrategyArchetypeProfile(
        archetype=ArchetypeFamily.MOMENTUM_CONTINUATION,
        strategy=candidate.strategy,
        required_evidence=(
            "directional trend or confirmed continuation break",
            "majority momentum alignment",
            "valid directional invalidation and target geometry",
        ),
        optional_evidence=optional_evidence,
        contradictions=candidate.evidence.contradictions + candidate.evidence.warnings,
        entry_modes=entry_modes,
        invalidation_type=candidate.invalidation.kind,
        target_types=target_types,
        confirmation_complete=confirmation_complete,
        provisional=candidate.provisional,
        regime_eligible=has_trend_or_break,
        explanation_labels=explanation_labels,
    )


__all__ = [
    "ArchetypeFamily",
    "StrategyArchetypeProfile",
    "breakout_retest_archetype_profile",
    "compression_expansion_archetype_profile",
    "exhaustion_reversal_archetype_profile",
    "failed_breakout_archetype_profile",
    "first_pullback_archetype_profile",
    "liquidity_sweep_archetype_profile",
    "momentum_continuation_archetype_profile",
    "vwap_reclaim_rejection_archetype_profile",
]
