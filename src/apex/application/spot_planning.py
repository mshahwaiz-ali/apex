"""Deterministic S4 spot entry, allocation, exit, and lifecycle planning."""

from __future__ import annotations

from dataclasses import dataclass

from apex.config.spot import SpotProductConfig
from apex.domain.spot import (
    SpotAccountInput,
    SpotEntryLeg,
    SpotEntryPlan,
    SpotEntryState,
    SpotLifecycleSnapshot,
    SpotLifecycleState,
    SpotPositionPlan,
    SpotStopPlan,
    SpotTargetLeg,
    SpotTargetPlan,
)
from apex.domain.spot_strategy import SpotStrategyCandidate, SpotStrategyDecision
