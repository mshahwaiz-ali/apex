"""Serialization and text reporting for lifecycle executions."""

from __future__ import annotations

from typing import Any

from apex.application.trade_lifecycle_engine import TradeLifecycleExecution


def trade_lifecycle_payload(execution: TradeLifecycleExecution) -> dict[str, Any]:
    """Return a stable JSON-ready lifecycle execution payload."""

    return {
        "state": execution.lifecycle.state.value,
        "entry_price": execution.entry_price,
        "exit_price": execution.exit_price,
        "active_stop": execution.lifecycle.active_stop_price,
        "trailing_stop": execution.lifecycle.trailing_stop_price,
        "runner_active": execution.lifecycle.runner_active,
        "remaining_percentage": execution.remaining_percentage,
        "closed_percentage": execution.lifecycle.closed_percentage,
        "partial_targets_hit": list(execution.lifecycle.partial_targets_hit),
        "realized_pnl": execution.realized_pnl,
        "unrealized_pnl": execution.unrealized_pnl,
        "total_fees": execution.total_fees,
        "total_slippage": execution.total_slippage,
        "realized_r_multiple": execution.realized_r_multiple,
        "bars_pending": execution.bars_pending,
        "bars_open": execution.bars_open,
        "exit_reason": execution.exit_reason,
        "events": [event.model_dump(mode="json") for event in execution.events],
    }


def format_trade_lifecycle(execution: TradeLifecycleExecution) -> str:
    """Return a compact operational lifecycle summary."""

    return "\n".join(
        (
            f"Lifecycle state: {execution.lifecycle.state.value}",
            f"Entry / exit: {_price(execution.entry_price)} / {_price(execution.exit_price)}",
            f"Remaining / closed: {execution.remaining_percentage:.1f}% / {execution.lifecycle.closed_percentage:.1f}%",
            f"Realized / unrealized PnL: {execution.realized_pnl:.4f} / {execution.unrealized_pnl:.4f}",
            f"Fees / slippage: {execution.total_fees:.4f} / {execution.total_slippage:.4f}",
            f"Realized R: {execution.realized_r_multiple:.3f}",
            f"Runner active: {'yes' if execution.lifecycle.runner_active else 'no'}",
            f"Exit reason: {execution.exit_reason or 'open'}",
        )
    )


def _price(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"
