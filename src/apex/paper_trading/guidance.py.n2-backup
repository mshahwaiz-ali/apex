"""Derive one operational instruction from a paper trade and its canonical plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.domain import CurrentAction
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.engine import paper_lifecycle_snapshot
from apex.paper_trading.management import paper_entry_expiry


@dataclass(frozen=True, slots=True)
class PaperTradeGuidance:
    """One unambiguous operator action for the current paper-trade state."""

    current_action: CurrentAction
    instruction: str
    active_stop_price: float | None
    next_target_label: str | None
    next_target_price: float | None
    completed_targets: tuple[str, ...]
    entry_expires_at: datetime | None = None
    runner_active: bool = False
    trailing_stop_price: float | None = None
    lifecycle_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Return a stable JSON-compatible guidance payload."""

        return {
            "current_action": self.current_action.value,
            "instruction": self.instruction,
            "active_stop_price": self.active_stop_price,
            "next_target_label": self.next_target_label,
            "next_target_price": self.next_target_price,
            "completed_targets": list(self.completed_targets),
            "entry_expires_at": (
                None if self.entry_expires_at is None else self.entry_expires_at.isoformat()
            ),
            "runner_active": self.runner_active,
            "trailing_stop_price": self.trailing_stop_price,
            "lifecycle_reason": self.lifecycle_reason,
        }


def derive_paper_trade_guidance(trade: PaperTrade) -> PaperTradeGuidance:
    """Derive guidance from the canonical paper state and lifecycle replay."""

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
    initial_stop = _optional_float(protection.get("stop_loss_price"))
    lifecycle = paper_lifecycle_snapshot(trade)
    active_stop = lifecycle.trailing_stop_price or lifecycle.active_stop_price or initial_stop
    expires_at = paper_entry_expiry(trade)

    common = {
        "active_stop_price": active_stop,
        "next_target_label": _optional_text(next_target, "label"),
        "next_target_price": _optional_number(next_target, "price"),
        "completed_targets": completed,
        "entry_expires_at": expires_at,
        "runner_active": lifecycle.runner_active,
        "trailing_stop_price": lifecycle.trailing_stop_price,
        "lifecycle_reason": lifecycle.reason,
    }

    if trade.state is PaperTradeState.WAITING_FOR_ENTRY:
        instruction = "wait for the validated entry condition"
        if expires_at is not None:
            instruction += f" before {expires_at.isoformat()}"
        instruction += "; cancel on invalidation, chase breach, account lockout, or expiry"
        return PaperTradeGuidance(
            current_action=CurrentAction.WAIT,
            instruction=instruction,
            **common,
        )
    if trade.state is PaperTradeState.GENERATED:
        return PaperTradeGuidance(
            current_action=CurrentAction.WAIT,
            instruction="prepare the approved setup; no entry is active yet",
            **common,
        )
    if trade.state in {PaperTradeState.ENTERED, PaperTradeState.PARTIALLY_CLOSED}:
        if lifecycle.trailing_stop_price is not None:
            return PaperTradeGuidance(
                current_action=CurrentAction.MOVE_STOP,
                instruction=(
                    "maintain the active trailing stop and only ratchet it in the profitable "
                    "direction; never loosen it"
                ),
                **common,
            )
        if lifecycle.runner_active:
            return PaperTradeGuidance(
                current_action=CurrentAction.HOLD,
                instruction="hold the allocated runner under the active stop and trailing policy",
                **common,
            )
        if trade.state is PaperTradeState.PARTIALLY_CLOSED:
            breakeven_stop = lifecycle.active_stop_price or trade.entry_price or initial_stop
            return PaperTradeGuidance(
                current_action=CurrentAction.MOVE_STOP,
                instruction=(
                    "protect the remaining position according to the triggered stop-management "
                    "rule"
                ),
                **(common | {"active_stop_price": breakeven_stop}),
            )
        return PaperTradeGuidance(
            current_action=CurrentAction.HOLD,
            instruction="hold under the active structural stop and wait for the next target",
            **common,
        )
    if trade.state in {PaperTradeState.CANCELLED, PaperTradeState.INVALIDATED}:
        return PaperTradeGuidance(
            current_action=CurrentAction.CANCEL_SETUP,
            instruction="setup is no longer valid; do not enter or reopen it",
            **_terminal_common(common),
        )
    if trade.state is PaperTradeState.EXPIRED:
        return PaperTradeGuidance(
            current_action=CurrentAction.DO_NOT_ENTER,
            instruction="setup expired; generate a fresh analysis before considering entry",
            **_terminal_common(common),
        )
    if trade.state is PaperTradeState.STOPPED and _is_emergency_reason(lifecycle.reason):
        instruction = "emergency exit completed; verify no residual position or open order remains"
    else:
        instruction = "trade lifecycle is complete; no open position should remain"
    return PaperTradeGuidance(
        current_action=CurrentAction.CLOSE_ALL,
        instruction=instruction,
        **_terminal_common(common),
    )


def build_paper_guidance_report(
    trades: tuple[PaperTrade, ...],
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a deterministic operational report for stored paper trades."""

    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("paper guidance report time must be timezone-aware")
    return {
        "schema_version": 2,
        "generated_at": timestamp.isoformat(),
        "trade_count": len(trades),
        "trades": [
            {
                "trade_id": trade.trade_id,
                "symbol": trade.signal.symbol,
                "paper_state": trade.state.value,
                **derive_paper_trade_guidance(trade).to_payload(),
            }
            for trade in trades
        ],
    }


def _terminal_common(common: dict[str, object]) -> dict[str, object]:
    return common | {
        "active_stop_price": None,
        "next_target_label": None,
        "next_target_price": None,
        "runner_active": False,
        "trailing_stop_price": None,
    }


def _is_emergency_reason(reason: str | None) -> bool:
    if reason is None:
        return False
    normalized = reason.lower()
    return "emergency" in normalized or "momentum failure" in normalized


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
