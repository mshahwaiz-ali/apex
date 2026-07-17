"""Build precision-entry plans from discovery-neutral setups."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apex.application.discovery_contracts import DiscoverySetup
from apex.domain import (
    EntryClassificationInput,
    FuturesDirection,
    PrecisionEntryPlan,
    classify_entry_state,
    weighted_precision_score,
)
from apex.strategies import TimeframeContext, TimeframeRole


@dataclass(frozen=True, slots=True)
class PrecisionTriggerContext:
   