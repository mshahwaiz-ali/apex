"""Management-aware paper-trade advancement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any

from apex.domain import TradeLifecycleEventType
from apex.domain.models import Candle
from apex.paper_trading.contracts import (
    TERMINAL_STATES,
    PaperTrade,
    PaperTradeConfig,
    PaperTradeState,
)
from apex.paper_trading.engine import update_paper_trade


def advance_paper_trade(
    trade: PaperTrade,
    candles: tuple[Candle, ...],
    *,
    config: PaperTradeConfig | None = None,
) -> PaperTrade:
    """Advance a paper trade while enforcing its explicit entry expiry."""

    current = trade
    active_config = config or PaperTradeConfig()
    for candle in candles:
        current = expire_waiting_trade(current, at=candle.close_time)
        if current.state in TERMINAL_STATES:
            return current
        current = update_paper_trade(current, (candle,), config=active_config)
        if current.state in TERMINAL_STATES:
            return current
    return current


def expire_waiting_trade(trade: PaperTrade, *, at: datetime) -> PaperTrade:
    """Expire a waiting setup once its timezone-aware plan deadline is reached."""

    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("paper expiry evaluation time must be timezone-aware")
    if trade.state is not PaperTradeState.WAITING_FOR_ENTRY:
        return trade
    expires_at = paper_entry_expiry(trade)
    if expires_at is None or at < expires_at:
        return trade
    return replace(
        trade,
        state=PaperTradeState.EXPIRED,
        updated_at=at,
        exit_time=at,
        lifecycle_events=(
            *trade.lifecycle_events,
            {
                "event_type": TradeLifecycleEventType.EXPIRED.value,
                "occurred_at": at.isoformat(),
                "closed_percentage": None,
                "target_label": None,
                "reason": "explicit entry expiry reached before fill",
            },
        ),
        notes=(*trade.notes, "explicit entry expiry reached before fill"),
    )


def paper_entry_expiry(trade: PaperTrade) -> datetime | None:
    """Read the canonical entry expiry from a serialized futures plan."""

    plan = _mapping(trade.futures_plan)
    management = _mapping(plan.get("management_plan"))
    entry = _mapping(management.get("entry"))
    raw_expiry = entry.get("expires_at")
    if raw_expiry is None:
        return None
    if isinstance(raw_expiry, datetime):
        expiry = raw_expiry
    elif isinstance(raw_expiry, str):
        expiry = datetime.fromisoformat(raw_expiry)
    else:
        raise ValueError("paper entry expiry must be an ISO timestamp")
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise ValueError("paper entry expiry must be timezone-aware")
    return expiry


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
