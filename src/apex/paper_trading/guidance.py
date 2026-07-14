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
    completed = tuple(
        str(target.get("label", ""))
        for target in targets[:completed_count]
        if str(target.get("label", "")).strip()
    )
    next_target = targets[completed_count] if completed_count < len(targets) else None
    active_stop = _optional_float(protection.get("stop_loss_price"))

    if trade.state is PaperTradeState.WAITING_FOR_ENTRY:
        return PaperTradeGuidance(
            current_action=CurrentAction.WAIT,
            instruction="wait for the validated entry condition; cancel on plan invalidation or expiry",
            active_stop_price=active_stop,
            next_target_label=_optional_text(next_target, "label"),
            next_target_price=_optional_number(next_target, "price"),
            completed_targets=completed,
        )
    if trade.state is PaperTradeState.ENTERED:
        return PaperTradeGuidance(
            current_action=CurrentAction.HOLD,
            instruction="hold under the active structural stop and wait for the next target",
            active_stop_price=active_stop,
            next_target_label=_optional_text(next_target, "label"),
            next_target_price=_optional_number(next_target, "price"),
            completed_targets=completed,
        )
    if trade.state is PaperTradeState.PARTIALLY_CLOSED:
        return PaperTradeGuidance(
            current_action=CurrentAction.MOVE_STOP,
            instruction="protect the remaining position according to the plan stop-management rule",
            active_stop_price=trade.entry_price or active_stop,
            next_target_label=_optional_text(next_target, "label"),
            next_target_price=_optional_number(next_target, "price"),
            completed_targets=completed,
        )
    if trade.state is PaperTradeState.GENERATED:
        return PaperTradeGuidance(
            current_action=CurrentAction.WAIT,
            instruction="prepare the approved setup; no entry is active yet",
            active_stop_price=active_stop,
            next_target_label=_optional_text(next_target, "label"),
            next_target_price=_optional_number(next_target, "price"),
            completed_targets=completed,
        )
    if trade.state in {PaperTradeState.CANCELLED, PaperTradeState.INVALIDATED}:
        return PaperTradeGuidance(
            current_action=CurrentAction.CANCEL_SETUP,
            instruction="setup is no longer valid; do not enter or reopen it",
            active_stop_price=None,
            next_target_label=None,
            next_target_price=None,
            completed_targets=completed,
        )
    if trade.state is PaperTradeState.EXPIRED:
        return PaperTradeGuidance(
            current_action=CurrentAction.DO_NOT_ENTER,
            instruction="setup expired; generate a fresh analysis before considering entry",
            active_stop_price=None,
            next_target_label=None,
            next_target_price=None,
            completed_targets=completed,
        )
    return PaperTradeGuidance(
        current_action=CurrentAction.CLOSE_ALL,
        instruction="trade lifecycle is complete; no open position should remain",
        active_stop_price=None,
        next_target_label=None,
        next_target_price=None,
        completed_targets=completed,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _targets(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _optional_text(value: Mapping[str, Any] | None, key: str) -> str | None:
    if value is None:
        return None
    candidate = value.get(key)
    return str(candidate) if candidate is not None else None


def _optional_number(value: Mapping[str, Any] | None, key: str) -> float | None:
    if value is None:
        return None
    return _optional_float(value.get(key))
