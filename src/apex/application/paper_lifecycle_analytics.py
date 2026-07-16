"""Typed production analytics for paper intake, execution, and lifecycle outcomes."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from statistics import fmean
from typing import Any

from apex.paper_trading.contracts import TERMINAL_STATES, PaperTrade, PaperTradeState
from apex.paper_trading.intake import IntakeSummary
from apex.paper_trading.runtime import PaperRuntimeResult

__all__ = [
    "HoldingTimeBand",
    "PaperLifecycleAnalytics",
    "PaperLifecycleTradeRecord",
    "RiskMultipleBand",
    "build_paper_lifecycle_analytics",
    "paper_lifecycle_analytics_payload",
]


class RiskMultipleBand(StrEnum):
    BELOW_MINUS_1 = "below_minus_1r"
    MINUS_1_TO_0 = "minus_1r_to_0r"
    ZERO_TO_1 = "0r_to_1r"
    ONE_TO_2 = "1r_to_2r"
    ABOVE_2 = "above_2r"


class HoldingTimeBand(StrEnum):
    NOT_ENTERED = "not_entered"
    ZERO_TO_5 = "0_5_candles"
    SIX_TO_12 = "6_12_candles"
    THIRTEEN_TO_24 = "13_24_candles"
    ABOVE_24 = "above_24_candles"


@dataclass(frozen=True, slots=True)
class PaperLifecycleTradeRecord:
    trade_id: str
    symbol: str
    market_type: str
    strategy: str
    direction: str
    state: str
    entry_state: str | None
    entered: bool
    terminal: bool
    transition_counts: dict[str, int]
    transition_reason_counts: dict[str, int]
    partial_target_count: int
    full_target_completed: bool
    candles_waited: int
    candles_held: int
    holding_time_band: str
    net_pnl: float | None
    realized_r_multiple: float | None
    risk_multiple_band: str | None
    leverage: float | None
    margin: float | None
    wallet_exposure_pct: float | None
    liquidation_price: float | None
    fees: float | None
    slippage: float | None


@dataclass(frozen=True, slots=True)
class PaperLifecycleAnalytics:
    intake_candidates_observed: int
    intake_accepted: int
    intake_rejected: int
    duplicates_skipped: int
    persistence_failures: int
    intake_reason_counts: dict[str, int]
    loaded_trades: int
    eligible_trades: int
    advanced_trades: int
    unchanged_trades: int
    missing_candle_trades: int
    requested_symbols: int
    successful_symbols: int
    provider_failure_count: int
    provider_failures_by_symbol: dict[str, int]
    state_counts: dict[str, int]
    entry_state_counts: dict[str, int]
    waiting_for_entry: int
    entered_trades: int
    unfilled_terminal_trades: int
    partial_target_fills: int
    full_target_completions: int
    stop_loss_exits: int
    expired_trades: int
    invalidations: int
    cancelled_trades: int
    transition_counts: dict[str, int]
    transition_reason_counts: dict[str, int]
    realized_net_pnl: float | None
    average_realized_r_multiple: float | None
    risk_multiple_distribution: dict[str, int]
    leverage_distribution: dict[str, int]
    holding_time_distribution: dict[str, int]
    average_margin: float | None
    average_wallet_exposure_pct: float | None
    total_fees: float | None
    total_slippage: float | None
    trades: tuple[PaperLifecycleTradeRecord, ...]


def build_paper_lifecycle_analytics(
    *,
    intake: IntakeSummary | None,
    runtime: PaperRuntimeResult | None,
    trades: tuple[PaperTrade, ...] = (),
) -> PaperLifecycleAnalytics:
    """Build deterministic analytics without fabricating absent financial fields."""

    records = tuple(sorted((_trade_record(trade) for trade in trades), key=lambda item: item.trade_id))
    states = Counter(record.state for record in records)
    entry_states = Counter(
        record.entry_state for record in records if record.entry_state is not None
    )
    transitions: Counter[str] = Counter()
    transition_reasons: Counter[str] = Counter()
    risk_bands: Counter[str] = Counter()
    leverage_bands: Counter[str] = Counter()
    holding_bands: Counter[str] = Counter()
    net_values: list[float] = []
    r_values: list[float] = []
    margins: list[float] = []
    exposures: list[float] = []
    fees: list[float] = []
    slippage: list[float] = []

    for record in records:
        transitions.update(record.transition_counts)
        transition_reasons.update(record.transition_reason_counts)
        holding_bands[record.holding_time_band] += 1
        if record.risk_multiple_band is not None:
            risk_bands[record.risk_multiple_band] += 1
        if record.leverage is not None:
            leverage_bands[_leverage_band(record.leverage)] += 1
        if record.terminal and record.net_pnl is not None:
            net_values.append(record.net_pnl)
        if record.terminal and record.realized_r_multiple is not None:
            r_values.append(record.realized_r_multiple)
        if record.margin is not None:
            margins.append(record.margin)
        if record.wallet_exposure_pct is not None:
            exposures.append(record.wallet_exposure_pct)
        if record.fees is not None:
            fees.append(record.fees)
        if record.slippage is not None:
            slippage.append(record.slippage)

    cycle = None if runtime is None else runtime.cycle
    failures = () if runtime is None else runtime.provider_failures
    failure_counts = Counter(symbol for symbol, _reason in failures)
    intake_reasons = {} if intake is None else dict(sorted(intake.reason_counts.items()))

    return PaperLifecycleAnalytics(
        intake_candidates_observed=0 if intake is None else intake.candidates_observed,
        intake_accepted=0 if intake is None else intake.accepted,
        intake_rejected=0 if intake is None else intake.rejected,
        duplicates_skipped=0 if intake is None else intake.duplicates_skipped,
        persistence_failures=0 if intake is None else intake.persistence_failures,
        intake_reason_counts=intake_reasons,
        loaded_trades=0 if cycle is None else cycle.loaded_trade_count,
        eligible_trades=0 if cycle is None else cycle.eligible_trade_count,
        advanced_trades=0 if cycle is None else cycle.advanced_trade_count,
        unchanged_trades=0 if cycle is None else cycle.unchanged_trade_count,
        missing_candle_trades=0 if cycle is None else len(cycle.missing_candle_trade_ids),
        requested_symbols=0 if runtime is None else len(runtime.requested_symbols),
        successful_symbols=0 if runtime is None else len(runtime.successful_symbols),
        provider_failure_count=len(failures),
        provider_failures_by_symbol=dict(sorted(failure_counts.items())),
        state_counts=dict(sorted(states.items())),
        entry_state_counts=dict(sorted(entry_states.items())),
        waiting_for_entry=states[PaperTradeState.WAITING_FOR_ENTRY.value],
        entered_trades=sum(record.entered for record in records),
        unfilled_terminal_trades=sum(record.terminal and not record.entered for record in records),
        partial_target_fills=sum(record.partial_target_count for record in records),
        full_target_completions=states[PaperTradeState.TARGET_HIT.value],
        stop_loss_exits=states[PaperTradeState.STOPPED.value],
        expired_trades=states[PaperTradeState.EXPIRED.value],
        invalidations=states[PaperTradeState.INVALIDATED.value],
        cancelled_trades=states[PaperTradeState.CANCELLED.value],
        transition_counts=dict(sorted(transitions.items())),
        transition_reason_counts=dict(sorted(transition_reasons.items())),
        realized_net_pnl=sum(net_values) if net_values else None,
        average_realized_r_multiple=fmean(r_values) if r_values else None,
        risk_multiple_distribution=dict(sorted(risk_bands.items())),
        leverage_distribution=dict(sorted(leverage_bands.items())),
        holding_time_distribution=dict(sorted(holding_bands.items())),
        average_margin=fmean(margins) if margins else None,
        average_wallet_exposure_pct=fmean(exposures) if exposures else None,
        total_fees=sum(fees) if fees else None,
        total_slippage=sum(slippage) if slippage else None,
        trades=records,
    )


def paper_lifecycle_analytics_payload(analytics: PaperLifecycleAnalytics) -> dict[str, Any]:
    """Return a stable JSON-ready analytics payload."""

    return asdict(analytics)


def _trade_record(trade: PaperTrade) -> PaperLifecycleTradeRecord:
    payload = trade.analysis_payload if isinstance(trade.analysis_payload, dict) else {}
    futures_plan = trade.futures_plan if isinstance(trade.futures_plan, dict) else {}
    entry = futures_plan.get("entry")
    entry = entry if isinstance(entry, dict) else {}

    transition_counts: Counter[str] = Counter()
    transition_reasons: Counter[str] = Counter()
    for event in trade.lifecycle_events:
        event_type = str(event.get("event_type", "")).strip()
        if event_type:
            transition_counts[event_type] += 1
        reason = str(event.get("reason", "")).strip()
        if reason:
            transition_reasons[reason] += 1

    net_pnl = _optional_finite(trade.net_pnl) if trade.state in TERMINAL_STATES else None
    realized_r = (
        _optional_finite(trade.realized_r_multiple) if trade.state in TERMINAL_STATES else None
    )
    leverage = _first_number(
        futures_plan,
        "recommended_leverage",
        "modeled_leverage",
        "required_leverage",
        "leverage",
    )
    margin = _first_number(futures_plan, "required_margin", "margin", "margin_required")
    exposure = _first_number(
        futures_plan,
        "wallet_exposure_pct",
        "wallet_exposure_percentage",
        "account_exposure_pct",
    )
    liquidation = _first_number(
        futures_plan,
        "liquidation_price",
        "estimated_liquidation_price",
    )
    fees = _first_number(futures_plan, "fees", "estimated_fees", "fee_allowance")
    slippage = _first_number(
        futures_plan,
        "slippage",
        "estimated_slippage",
        "slippage_allowance",
    )
    entry_state = str(entry.get("state") or entry.get("entry_state") or "").strip().lower()

    return PaperLifecycleTradeRecord(
        trade_id=trade.trade_id,
        symbol=trade.signal.symbol,
        market_type=str(payload.get("market_type", "futures")).lower(),
        strategy=str(payload.get("strategy") or trade.signal.strategy.value),
        direction=str(payload.get("direction") or trade.signal.direction.value),
        state=trade.state.value,
        entry_state=entry_state or None,
        entered=trade.entry_time is not None,
        terminal=trade.state in TERMINAL_STATES,
        transition_counts=dict(sorted(transition_counts.items())),
        transition_reason_counts=dict(sorted(transition_reasons.items())),
        partial_target_count=trade.partial_target_count,
        full_target_completed=trade.state is PaperTradeState.TARGET_HIT,
        candles_waited=trade.candles_waited,
        candles_held=trade.candles_held,
        holding_time_band=_holding_band(trade).value,
        net_pnl=net_pnl,
        realized_r_multiple=realized_r,
        risk_multiple_band=None if realized_r is None else _risk_band(realized_r).value,
        leverage=leverage,
        margin=margin,
        wallet_exposure_pct=exposure,
        liquidation_price=liquidation,
        fees=fees,
        slippage=slippage,
    )


def _optional_finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_number(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _optional_finite(payload.get(key))
        if value is not None:
            return value
    sizing = payload.get("position_sizing")
    if isinstance(sizing, dict):
        for key in keys:
            value = _optional_finite(sizing.get(key))
            if value is not None:
                return value
    return None


def _risk_band(value: float) -> RiskMultipleBand:
    if value < -1.0:
        return RiskMultipleBand.BELOW_MINUS_1
    if value < 0.0:
        return RiskMultipleBand.MINUS_1_TO_0
    if value < 1.0:
        return RiskMultipleBand.ZERO_TO_1
    if value < 2.0:
        return RiskMultipleBand.ONE_TO_2
    return RiskMultipleBand.ABOVE_2


def _holding_band(trade: PaperTrade) -> HoldingTimeBand:
    if trade.entry_time is None:
        return HoldingTimeBand.NOT_ENTERED
    if trade.candles_held <= 5:
        return HoldingTimeBand.ZERO_TO_5
    if trade.candles_held <= 12:
        return HoldingTimeBand.SIX_TO_12
    if trade.candles_held <= 24:
        return HoldingTimeBand.THIRTEEN_TO_24
    return HoldingTimeBand.ABOVE_24


def _leverage_band(value: float) -> str:
    if value <= 5.0:
        return "1_5x"
    if value <= 10.0:
        return "5_10x"
    if value <= 20.0:
        return "10_20x"
    return "above_20x"
