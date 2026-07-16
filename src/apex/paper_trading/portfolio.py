"""Account-aware portfolio accounting for persisted paper trades."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from apex.paper_trading.contracts import TERMINAL_STATES, PaperTrade, PaperTradeState


@dataclass(frozen=True, slots=True)
class PaperPortfolioSnapshot:
    """Portfolio state derived from canonical paper-trade records."""

    initial_wallet_balance: float
    realized_net_pnl: float
    wallet_equity: float
    reserved_margin: float
    available_balance: float
    open_risk: float
    wallet_exposure_pct: float
    open_trade_count: int
    entered_trade_count: int
    waiting_trade_count: int
    locked: bool
    lock_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "initial_wallet_balance",
            "realized_net_pnl",
            "wallet_equity",
            "reserved_margin",
            "available_balance",
            "open_risk",
            "wallet_exposure_pct",
        ):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        if self.initial_wallet_balance <= 0.0:
            raise ValueError("initial wallet balance must be positive")
        if self.reserved_margin < 0.0 or self.open_risk < 0.0:
            raise ValueError("paper portfolio margin and risk cannot be negative")
        if min(self.open_trade_count, self.entered_trade_count, self.waiting_trade_count) < 0:
            raise ValueError("paper portfolio counts cannot be negative")


def build_paper_portfolio_snapshot(
    trades: tuple[PaperTrade, ...],
    *,
    initial_wallet_balance: float,
    maximum_wallet_exposure_pct: float = 100.0,
    maximum_open_risk_pct: float = 100.0,
) -> PaperPortfolioSnapshot:
    """Derive wallet, margin, exposure, and lockout state from stored trades."""

    if not math.isfinite(initial_wallet_balance) or initial_wallet_balance <= 0.0:
        raise ValueError("initial wallet balance must be positive and finite")
    for name, value in (
        ("maximum wallet exposure percentage", maximum_wallet_exposure_pct),
        ("maximum open risk percentage", maximum_open_risk_pct),
    ):
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(f"{name} must be between zero and 100")

    realized_net_pnl = sum(trade.net_pnl for trade in trades if trade.state in TERMINAL_STATES)
    wallet_equity = initial_wallet_balance + realized_net_pnl
    open_trades = tuple(trade for trade in trades if trade.state not in TERMINAL_STATES)
    entered = tuple(
        trade
        for trade in open_trades
        if trade.state in {PaperTradeState.ENTERED, PaperTradeState.PARTIALLY_CLOSED}
    )
    waiting = tuple(trade for trade in open_trades if trade.state is PaperTradeState.WAITING_FOR_ENTRY)
    reserved_margin = sum(_planned_margin(trade) for trade in entered)
    open_risk = sum(_remaining_open_risk(trade) for trade in entered)
    available_balance = wallet_equity - reserved_margin
    exposure_pct = reserved_margin / wallet_equity * 100.0 if wallet_equity > 0.0 else 100.0
    open_risk_pct = open_risk / wallet_equity * 100.0 if wallet_equity > 0.0 else 100.0

    reasons: list[str] = []
    if wallet_equity <= 0.0:
        reasons.append("wallet equity is depleted")
    if available_balance < 0.0:
        reasons.append("reserved margin exceeds wallet equity")
    if exposure_pct > maximum_wallet_exposure_pct:
        reasons.append("wallet exposure limit exceeded")
    if open_risk_pct > maximum_open_risk_pct:
        reasons.append("open risk limit exceeded")

    return PaperPortfolioSnapshot(
        initial_wallet_balance=initial_wallet_balance,
        realized_net_pnl=realized_net_pnl,
        wallet_equity=wallet_equity,
        reserved_margin=reserved_margin,
        available_balance=available_balance,
        open_risk=open_risk,
        wallet_exposure_pct=exposure_pct,
        open_trade_count=len(open_trades),
        entered_trade_count=len(entered),
        waiting_trade_count=len(waiting),
        locked=bool(reasons),
        lock_reasons=tuple(reasons),
    )


def paper_portfolio_payload(snapshot: PaperPortfolioSnapshot) -> dict[str, Any]:
    """Return a stable JSON-ready portfolio payload."""

    return {
        "initial_wallet_balance": snapshot.initial_wallet_balance,
        "realized_net_pnl": snapshot.realized_net_pnl,
        "wallet_equity": snapshot.wallet_equity,
        "reserved_margin": snapshot.reserved_margin,
        "available_balance": snapshot.available_balance,
        "open_risk": snapshot.open_risk,
        "wallet_exposure_pct": snapshot.wallet_exposure_pct,
        "open_trade_count": snapshot.open_trade_count,
        "entered_trade_count": snapshot.entered_trade_count,
        "waiting_trade_count": snapshot.waiting_trade_count,
        "locked": snapshot.locked,
        "lock_reasons": list(snapshot.lock_reasons),
    }


def _planned_margin(trade: PaperTrade) -> float:
    plan = _mapping(trade.futures_plan)
    return _first_number(
        plan,
        "required_margin",
        "margin",
        "margin_required",
        nested_keys=("position_sizing", "position", "management_plan"),
    )


def _remaining_open_risk(trade: PaperTrade) -> float:
    remaining_fraction = max(0.0, 1.0 - trade.closed_percentage / 100.0)
    plan = _mapping(trade.futures_plan)
    configured = _first_number(
        plan,
        "total_maximum_planned_loss",
        "maximum_planned_loss",
        "max_loss",
        "risk_amount",
        nested_keys=("position_sizing", "position", "management_plan"),
    )
    base_risk = configured if configured > 0.0 else trade.signal.risk_amount
    return base_risk * remaining_fraction


def _first_number(
    payload: dict[str, Any],
    *keys: str,
    nested_keys: tuple[str, ...],
) -> float:
    for key in keys:
        value = _finite_nonnegative(payload.get(key))
        if value is not None:
            return value
    for nested_key in nested_keys:
        nested = _mapping(payload.get(nested_key))
        for key in keys:
            value = _finite_nonnegative(nested.get(key))
            if value is not None:
                return value
    return 0.0


def _finite_nonnegative(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0.0 else None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
