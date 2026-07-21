"""Shared target-quality scoring with explicit source credibility."""

from __future__ import annotations

import math

from apex.strategies.contracts import TargetType

_SOURCE_CREDIBILITY = {
    TargetType.LIQUIDITY: 0.95,
    TargetType.STRUCTURAL: 0.90,
    TargetType.RANGE: 0.85,
    TargetType.PARTIAL: 0.75,
    TargetType.EXPANSION: 0.55,
}


def target_space_quality(
    *,
    current: float,
    invalidation: float,
    target: float,
    target_type: TargetType,
) -> float:
    """Score usable reward and target provenance without rewarding distance alone.

    A target reaches full reward adequacy at 1.5R. Additional distance does not
    improve adequacy and very distant objectives receive a modest reachability
    penalty. Source credibility prevents an ATR projection from being treated as
    equivalent to observed liquidity or structure.
    """

    risk = abs(current - invalidation)
    reward = abs(target - current)
    if risk <= 0.0 or not all(math.isfinite(value) for value in (risk, reward)):
        return 0.0

    risk_multiple = reward / risk
    reward_adequacy = min(1.0, risk_multiple / 1.5)
    source_credibility = _SOURCE_CREDIBILITY[target_type]
    distant_penalty = min(0.25, max(0.0, risk_multiple - 3.0) / 6.0)
    score = reward_adequacy * 0.55 + source_credibility * 0.45 - distant_penalty
    return max(0.0, min(1.0, score))


__all__ = ["target_space_quality"]
