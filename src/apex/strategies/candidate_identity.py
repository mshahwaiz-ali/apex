"""Stable candidate identities shared before and during scoring."""

from __future__ import annotations

from collections.abc import Sequence

from apex.strategies.contracts import TradeCandidate


def candidate_identity(candidate: TradeCandidate, occurrence: int) -> str:
    """Return a stable identity within one ordered candidate collection."""

    return f"{candidate.strategy.value}:{candidate.direction.value}:{occurrence}"


def candidate_identities(candidates: Sequence[TradeCandidate]) -> tuple[str, ...]:
    """Assign stable identities while preserving candidate order."""

    occurrences: dict[tuple[str, str], int] = {}
    identities: list[str] = []
    for candidate in candidates:
        key = (candidate.strategy.value, candidate.direction.value)
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        identities.append(candidate_identity(candidate, occurrence))
    return tuple(identities)


__all__ = ["candidate_identities", "candidate_identity"]
