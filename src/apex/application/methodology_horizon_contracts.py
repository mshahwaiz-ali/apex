"""Shared holding-horizon and higher-timeframe authority contracts."""

from __future__ import annotations

from enum import StrEnum


class HoldingHorizon(StrEnum):
    SCALP = "scalp"
    SHORT = "short"
    STRUCTURED = "structured"
    RUNNER = "runner"


class HigherTimeframeAuthority(StrEnum):
    WARNING_AND_TARGET_CEILING = "warning_and_target_ceiling"
    CONTEXTUAL_PENALTY = "contextual_penalty"
    STRICT = "strict"


__all__ = [
    "HigherTimeframeAuthority",
    "HoldingHorizon",
]
