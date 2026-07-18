"""Project selected Phase 5 candidate evidence into methodology contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from apex.application.methodology_contracts import (
    Contradiction,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)

_SUPPORT_STRENGTH = 0.6
_CONTRADICTION_STRENGTH = 0.55
_NEUTRAL_STRENGTH = 0.4


def selected_candidate_methodology_evidence(
    phase5_diagnostics: Mapping[str, Any] | None,
    *,
    candidate_id: str,
) -> tuple[tuple[EvidenceObservation, ...], tuple[Contradiction, ...]]:
    """Return canonical evidence for exactly one selected Phase 5 candidate."""

    if phase5_diagnostics is None:
        return (), ()
    candidates = phase5_diagnostics.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, str | bytes):
        return (), ()

    selected: Mapping[str, Any] | None = None
    for item in candidates:
        if isinstance(item, Mapping) and item.get("candidate_id") == candidate_id:
            selected = item
            break
    if selected is None:
        return (), ()

    raw_evidence = selected.get("evidence")
    if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, str | bytes):
        return (), ()

    observations: list[EvidenceObservation] = []
    contradictions: list[Contradiction] = []
    seen_observations: set[EvidenceObservation] = set()
    seen_contradictions: set[Contradiction] = set()
    for index, record in enumerate(raw_evidence, start=1):
        if not isinstance(record, Mapping):
            continue
        kind = str(record.get("kind", "")).strip().lower()
        code = str(record.get("code", "")).strip() or f"EVIDENCE_{index:03d}"
        detail = str(record.get("detail", "")).strip()
        if not detail:
            continue
        family = _family_for_record(kind=kind, detail=detail)
        effect, strength = _effect_and_strength(kind)
        source = f"phase5:{candidate_id}:{code.lower()}"
        observation = EvidenceObservation(
            family=family,
            source=source,
            normalized_strength=strength,
            freshness=1.0,
            independence_group=_independence_group(family, detail),
            effect=effect,
            reason=detail,
        )
        if observation not in seen_observations:
            seen_observations.add(observation)
            observations.append(observation)
        if effect is EvidenceEffect.CONTRADICTS:
            contradiction = Contradiction(
                code=code,
                family=family,
                severity=strength,
                reason=detail,
            )
            if contradiction not in seen_contradictions:
                seen_contradictions.add(contradiction)
                contradictions.append(contradiction)
    return tuple(observations), tuple(contradictions)


def _effect_and_strength(kind: str) -> tuple[EvidenceEffect, float]:
    if kind == "contradiction":
        return EvidenceEffect.CONTRADICTS, _CONTRADICTION_STRENGTH
    if kind == "supporting":
        return EvidenceEffect.SUPPORTS, _SUPPORT_STRENGTH
    return EvidenceEffect.NEUTRAL, _NEUTRAL_STRENGTH


def _family_for_record(*, kind: str, detail: str) -> EvidenceFamily:
    normalized = detail.lower()
    if kind == "structure_reference":
        return EvidenceFamily.STRUCTURE
    if kind == "liquidity_reference":
        return EvidenceFamily.LIQUIDITY
    if kind == "warning":
        return EvidenceFamily.DATA_QUALITY

    keyword_groups: tuple[tuple[EvidenceFamily, tuple[str, ...]], ...] = (
        (EvidenceFamily.DERIVATIVES, ("funding", "open interest", "liquidation")),
        (EvidenceFamily.PARTICIPATION, ("volume", "rvol", "participation", "taker")),
        (EvidenceFamily.VOLATILITY, ("atr", "volatility", "compression", "expansion")),
        (EvidenceFamily.LIQUIDITY, ("liquidity", "sweep", "order book", "imbalance")),
        (EvidenceFamily.TREND, ("trend", "ema", "moving average", "vwap")),
        (EvidenceFamily.MOMENTUM, ("rsi", "macd", "momentum", "roc", "stochastic")),
        (EvidenceFamily.CANDLE, ("candle", "wick", "engulf", "close", "rejection")),
        (EvidenceFamily.BROAD_CONTEXT, ("higher timeframe", "htf", "market context")),
        (
            EvidenceFamily.STRUCTURE,
            (
                "breakout",
                "breakdown",
                "range",
                "support",
                "resistance",
                "swing",
                "retest",
                "reclaim",
            ),
        ),
    )
    for family, keywords in keyword_groups:
        if any(_contains_keyword(normalized, keyword) for keyword in keywords):
            return family
    return EvidenceFamily.STRUCTURE


def _contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def _independence_group(family: EvidenceFamily, detail: str) -> str:
    normalized = detail.lower()
    if family is EvidenceFamily.MOMENTUM:
        if "rsi" in normalized or "stochastic" in normalized:
            return "momentum_oscillators"
        if "macd" in normalized or "roc" in normalized:
            return "momentum_rate_of_change"
    if family is EvidenceFamily.TREND:
        if "ema" in normalized or "moving average" in normalized:
            return "trend_averages"
        if "vwap" in normalized:
            return "trend_vwap"
    if family is EvidenceFamily.PARTICIPATION:
        return "participation_volume"
    if family is EvidenceFamily.STRUCTURE:
        return "price_structure"
    return family.value


__all__ = ["selected_candidate_methodology_evidence"]
