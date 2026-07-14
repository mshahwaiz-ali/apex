"""Derive one operational instruction from a paper trade and its canonical plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.domain import CurrentAction
from apex.paper_trading.contracts import PaperTrade, PaperTradeState


@dataclass(frozen=True, slots=True)
class PaperTradeGuidance:
    """One unambiguous operator action for the current paper-trade state."""

    current_action: CurrentAction
    instruction: str
    active_stop_price: float | None
    next_target_label: str | None
    next_target_price: float | None
    completed_targets: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        """Return a stable JSON-compatible guidance payload."""

        return {
            "current_action": self.current_action.value,
            "instruction": self.instruction,
            "active_stop_price": self.active_stop_price,
            "next_target_label": self.next_target_label,
            "next_target_price": self.next_target_price,
            "completed_targets": list(self.completed_targets),
        }


def derive_paper_trade_guidance(trade: PaperTrade) -> PaperTradeGuidance:
    """Derive guidance without creating a second lifecycle state machine."""

    plan = _mapping(trade.futures_plan)
    management = _mapping(plan.get("management_plan"))
    protection = _mapping(management.get("initial_protection"))
    targets = _targets(management.get("targets"))
    completed_count = min(trade.partial_target_count, len(targets))
    completed = tuple(str(target.get("label", "")) for target in targets[:completed_count])
    next_target = targets[completed_count] if completed_count < len(targets) else None
    active_stop = _optional