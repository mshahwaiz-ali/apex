"""Deterministic paper-only opportunity intake for futures and spot plans."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from apex.application.analysis import SymbolAnalysis
from apex.application.spot_analysis import SpotAnalysisResult, spot_analysis_result_to_payload
from apex.backtesting import BacktestSignal
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.engine import create_paper_trade
from apex.paper_trading.store import PaperTradeStore
from apex.risk import RiskDecision
from apex.strategies import StrategyType, TradeDirection


class IntakeMarketType(StrEnum):
    FUTURES = "futures"
    SPOT = "spot"


class IntakeStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    PERSISTENCE_FAILED = "persistence_failed"


class IntakeReason(StrEnum):
    ACCEPTED = "ACCEPTED"
    NO_APPROVED_SETUP = "NO_APPROVED_SETUP"
    MISSING_ACTIONABLE_PLAN = "MISSING_ACTIONABLE_PLAN"
    NON_ACTIONABLE_ENTRY_STATE = "NON_ACTIONABLE_ENTRY_STATE"
    INVALIDATED = "INVALIDATED"
    MISSED_ENTRY = "MISSED_ENTRY"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    NO_TRADE = "NO_TRADE"
    SPOT_SHORT_NOT_ALLOWED = "SPOT_SHORT_NOT_ALLOWED"
    SPOT_NOT_APPROVED = "SPOT_NOT_APPROVED"
    SPOT_ALLOCATION_REJECTED = "SPOT_ALLOCATION_REJECTED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"


_ACTIONABLE_ENTRY_STATES = {
    "ready_now",
    "approaching_entry",
    "wait_for_reclaim",
    "wait_for_retest",
}
_REJECTED_ENTRY_STATES = {
    "invalidated": IntakeReason.INVALIDATED,
    "missed_entry": IntakeReason.MISSED_ENTRY,
    "expired": IntakeReason.EXPIRED,
    "rejected": IntakeReason.REJECTED,
    "no_trade": IntakeReason.NO_TRADE,
}


@dataclass(frozen=True, slots=True)
class IntakeCandidate:
    market_type: IntakeMarketType
    symbol: str
    strategy: str
    direction: str
    setup_segment: dict[str, str]
    analysis_timestamp: datetime
    plan_identity: str
    source_command: str
    source_mode: str
    analysis_payload: dict[str, Any]
    paper_trade: PaperTrade

    def __post_init__(self) -> None:
        if self.analysis_timestamp.tzinfo is None or self.analysis_timestamp.utcoffset() is None:
            raise ValueError("intake analysis timestamp must be timezone-aware")
        for value, label in (
            (self.symbol, "symbol"),
            (self.strategy, "strategy"),
            (self.direction, "direction"),
            (self.plan_identity, "plan identity"),
            (self.source_command, "source command"),
            (self.source_mode, "source mode"),
        ):
            if not value.strip():
                raise ValueError(f"intake {label} cannot be empty")

    @property
    def deduplication_key(self) -> str:
        payload = {
            "market_type": self.market_type.value,
            "symbol": self.symbol.upper(),
            "strategy": self.strategy,
            "direction": self.direction,
            "setup_segment": dict(sorted(self.setup_segment.items())),
            "analysis_timestamp": self.analysis_timestamp.astimezone(UTC).isoformat(),
            "plan_identity": self.plan_identity,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class IntakeResult:
    status: IntakeStatus
    reason: IntakeReason
    market_type: IntakeMarketType
    symbol: str
    deduplication_key: str | None = None
    trade_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class IntakeSummary:
    market_type: IntakeMarketType
    candidates_observed: int
    accepted: int
    rejected: int
    duplicates_skipped: int
    persistence_failures: int
    reason_counts: dict[str, int]
    created_trade_ids: tuple[str, ...]
    results: tuple[IntakeResult, ...]


def build_futures_intake_candidate(
    analysis: SymbolAnalysis,
    *,
    futures_plan: dict[str, Any] | None,
    management_plan: dict[str, Any] | None,
    account_policy_snapshot: dict[str, Any] | None,
    source_command: str,
    source_mode: str,
) -> IntakeCandidate | IntakeResult:
    """Build one paper-only futures intake candidate or a stable rejection."""

    setup = analysis.assessment.setup
    if analysis.assessment.decision is not RiskDecision.APPROVED or setup is None:
        return _rejection(
            IntakeMarketType.FUTURES,
            analysis.symbol,
            IntakeReason.NO_APPROVED_SETUP,
        )
    if not futures_plan or not _plan_is_actionable(futures_plan):
        return _rejection(
            IntakeMarketType.FUTURES,
            analysis.symbol,
            IntakeReason.MISSING_ACTIONABLE_PLAN,
        )
    entry_state = _entry_state(analysis.precision_entry)
    rejected_reason = _REJECTED_ENTRY_STATES.get(entry_state)
    if rejected_reason is not None:
        return _rejection(IntakeMarketType.FUTURES, analysis.symbol, rejected_reason)
    if entry_state not in _ACTIONABLE_ENTRY_STATES:
        return _rejection(
            IntakeMarketType.FUTURES,
            analysis.symbol,
            IntakeReason.NON_ACTIONABLE_ENTRY_STATE,
            detail=f"entry_state={entry_state or 'missing'}",
        )

    strategy = setup.strategy.value
    direction = setup.direction.value
    setup_segment = _setup_segment(
        market_type=IntakeMarketType.FUTURES,
        symbol=analysis.symbol,
        strategy=strategy,
        direction=direction,
        scanner_type=analysis.scanner_type.value,
        gainer_state=analysis.gainer_state,
    )
    plan_identity = _stable_plan_identity(futures_plan)
    payload = {
        "market_type": IntakeMarketType.FUTURES.value,
        "strategy": strategy,
        "direction": direction,
        "setup_segment": setup_segment,
        "analysis_timestamp": analysis.generated_at.isoformat(),
        "source_command": source_command,
        "source_mode": source_mode,
        "eligibility": "paper_only",
        "strategy_approval": analysis.assessment.decision.value,
        "risk_mode": futures_plan.get("risk_mode"),
        "account_policy_snapshot": account_policy_snapshot,
        "scanner_context": {
            "scanner_type": analysis.scanner_type.value,
            "gainer_state": analysis.gainer_state,
            "gainer_evidence": analysis.gainer_evidence,
            "strategy_routing": analysis.strategy_routing,
        },
        "precision_entry": analysis.precision_entry,
        "management_plan": management_plan,
        "futures_plan": futures_plan,
    }
    trade = create_paper_trade(
        setup,
        analysis_payload=payload,
        futures_plan=futures_plan,
        created_at=analysis.generated_at,
    )
    return IntakeCandidate(
        market_type=IntakeMarketType.FUTURES,
        symbol=analysis.symbol,
        strategy=strategy,
        direction=direction,
        setup_segment=setup_segment,
        analysis_timestamp=analysis.generated_at,
        plan_identity=plan_identity,
        source_command=source_command,
        source_mode=source_mode,
        analysis_payload=payload,
        paper_trade=trade,
    )


def build_spot_intake_candidate(
    *,
    symbol: str,
    result: SpotAnalysisResult,
    analysis_timestamp: datetime,
    source_command: str,
    source_mode: str,
    scanner_context: dict[str, Any] | None = None,
) -> IntakeCandidate | IntakeResult:
    """Build one long-only cash-spot paper intake candidate or rejection."""

    selected = result.routing.selected
    planning = result.planning
    if selected is None or selected.decision.value != "APPROVE":
        return _rejection(IntakeMarketType.SPOT, symbol, IntakeReason.SPOT_NOT_APPROVED)
    if planning is None:
        return _rejection(IntakeMarketType.SPOT, symbol, IntakeReason.SPOT_ALLOCATION_REJECTED)
    direction = "long"
    if direction != TradeDirection.LONG.value:
        return _rejection(IntakeMarketType.SPOT, symbol, IntakeReason.SPOT_SHORT_NOT_ALLOWED)

    entry_state = planning.entry_plan.state.value.lower()
    if entry_state not in _ACTIONABLE_ENTRY_STATES:
        return _rejection(
            IntakeMarketType.SPOT,
            symbol,
            IntakeReason.NON_ACTIONABLE_ENTRY_STATE,
            detail=f"entry_state={entry_state}",
        )
    position = planning.position_plan
    if position.capital_allocated <= 0 or position.quantity <= 0:
        return _rejection(IntakeMarketType.SPOT, symbol, IntakeReason.SPOT_ALLOCATION_REJECTED)

    strategy = selected.strategy.value
    setup_segment = _setup_segment(
        market_type=IntakeMarketType.SPOT,
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        scanner_type=source_mode,
        gainer_state=None,
    )
    planning_payload = spot_analysis_result_to_payload(result)["planning"]
    assert isinstance(planning_payload, dict)
    plan_identity = _stable_plan_identity(planning_payload)
    targets = planning.target_plan.targets
    signal = BacktestSignal(
        symbol=symbol,
        strategy=_spot_strategy_type(strategy),
        direction=TradeDirection.LONG,
        generated_at=analysis_timestamp,
        entry_price=position.average_entry_price,
        stop_price=planning.stop_plan.protective_stop_price,
        target_price=targets[-1].price,
        quantity=position.quantity,
        risk_amount=position.planned_loss_amount,
        confidence_score=float(len(selected.evidence)),
        target_prices=tuple(target.price for target in targets),
        partial_close_percentages=tuple(target.sell_percentage for target in targets),
    )
    payload = {
        "market_type": IntakeMarketType.SPOT.value,
        "strategy": strategy,
        "direction": direction,
        "setup_segment": setup_segment,
        "analysis_timestamp": analysis_timestamp.isoformat(),
        "source_command": source_command,
        "source_mode": source_mode,
        "eligibility": selected.eligibility.value,
        "scanner_context": scanner_context,
        "spot_plan": planning_payload,
        "spot_strategy": selected.model_dump(mode="json"),
    }
    trade_id = _trade_id(symbol, analysis_timestamp, plan_identity)
    trade = PaperTrade(
        trade_id=trade_id,
        signal=signal,
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=analysis_timestamp,
        updated_at=analysis_timestamp,
        analysis_payload=payload,
        futures_plan=None,
        lifecycle_events=(
            {
                "event_type": "setup_generated",
                "occurred_at": analysis_timestamp.isoformat(),
            },
            {
                "event_type": "waiting_for_entry",
                "occurred_at": analysis_timestamp.isoformat(),
            },
        ),
        notes=("paper trade generated from approved cash-spot plan",),
    )
    return IntakeCandidate(
        market_type=IntakeMarketType.SPOT,
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        setup_segment=setup_segment,
        analysis_timestamp=analysis_timestamp,
        plan_identity=plan_identity,
        source_command=source_command,
        source_mode=source_mode,
        analysis_payload=payload,
        paper_trade=trade,
    )


def persist_intake_candidates(
    store: PaperTradeStore,
    candidates: tuple[IntakeCandidate | IntakeResult, ...],
    *,
    market_type: IntakeMarketType,
) -> IntakeSummary:
    """Deduplicate and atomically persist a deterministic intake batch."""

    existing = store.load()
    known_keys = {
        str(trade.analysis_payload.get("paper_intake", {}).get("deduplication_key"))
        for trade in existing
        if isinstance(trade.analysis_payload.get("paper_intake"), dict)
    }
    results: list[IntakeResult] = []
    additions: list[PaperTrade] = []
    for item in candidates:
        if isinstance(item, IntakeResult):
            results.append(item)
            continue
        key = item.deduplication_key
        if key in known_keys:
            results.append(
                IntakeResult(
                    status=IntakeStatus.DUPLICATE_SKIPPED,
                    reason=IntakeReason.DUPLICATE_SKIPPED,
                    market_type=item.market_type,
                    symbol=item.symbol,
                    deduplication_key=key,
                )
            )
            continue
        metadata = {
            "deduplication_key": key,
            "plan_identity": item.plan_identity,
            "source_command": item.source_command,
            "source_mode": item.source_mode,
            "persistence_result": IntakeStatus.ACCEPTED.value,
        }
        payload = dict(item.analysis_payload)
        payload["paper_intake"] = metadata
        trade = replace(item.paper_trade, analysis_payload=payload)
        additions.append(trade)
        known_keys.add(key)
        results.append(
            IntakeResult(
                status=IntakeStatus.ACCEPTED,
                reason=IntakeReason.ACCEPTED,
                market_type=item.market_type,
                symbol=item.symbol,
                deduplication_key=key,
                trade_id=trade.trade_id,
            )
        )

    if additions:
        try:
            store.save((*existing, *additions))
        except OSError as exc:
            failed_ids = {trade.trade_id for trade in additions}
            results = [
                IntakeResult(
                    status=IntakeStatus.PERSISTENCE_FAILED,
                    reason=IntakeReason.PERSISTENCE_FAILED,
                    market_type=result.market_type,
                    symbol=result.symbol,
                    deduplication_key=result.deduplication_key,
                    detail=str(exc),
                )
                if result.trade_id in failed_ids
                else result
                for result in results
            ]

    ordered = tuple(sorted(results, key=_result_order_key))
    counts = Counter(result.reason.value for result in ordered)
    return IntakeSummary(
        market_type=market_type,
        candidates_observed=len(candidates),
        accepted=sum(result.status is IntakeStatus.ACCEPTED for result in ordered),
        rejected=sum(result.status is IntakeStatus.REJECTED for result in ordered),
        duplicates_skipped=sum(
            result.status is IntakeStatus.DUPLICATE_SKIPPED for result in ordered
        ),
        persistence_failures=sum(
            result.status is IntakeStatus.PERSISTENCE_FAILED for result in ordered
        ),
        reason_counts=dict(sorted(counts.items())),
        created_trade_ids=tuple(
            result.trade_id for result in ordered if result.trade_id is not None
        ),
        results=ordered,
    )


def intake_summary_payload(summary: IntakeSummary) -> dict[str, Any]:
    payload = asdict(summary)
    payload["market_type"] = summary.market_type.value
    payload["results"] = [
        {
            **asdict(result),
            "status": result.status.value,
            "reason": result.reason.value,
            "market_type": result.market_type.value,
        }
        for result in summary.results
    ]
    return payload


def _rejection(
    market_type: IntakeMarketType,
    symbol: str,
    reason: IntakeReason,
    *,
    detail: str | None = None,
) -> IntakeResult:
    return IntakeResult(
        status=IntakeStatus.REJECTED,
        reason=reason,
        market_type=market_type,
        symbol=symbol,
        detail=detail,
    )


def _entry_state(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get("state") or payload.get("entry_state")
    return str(value or "").strip().lower()


def _plan_is_actionable(plan: dict[str, Any]) -> bool:
    decision = str(plan.get("decision", plan.get("status", "approved"))).lower()
    return decision not in {"rejected", "invalid", "no_trade", "error"}


def _setup_segment(
    *,
    market_type: IntakeMarketType,
    symbol: str,
    strategy: str,
    direction: str,
    scanner_type: str,
    gainer_state: str | None,
) -> dict[str, str]:
    segment = {
        "market_type": market_type.value,
        "symbol": symbol,
        "strategy": strategy,
        "direction": direction,
        "scanner_type": scanner_type,
    }
    if gainer_state is not None:
        segment["gainer_state"] = gainer_state
    return dict(sorted(segment.items()))


def _stable_plan_identity(plan: dict[str, Any]) -> str:
    encoded = json.dumps(plan, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _trade_id(symbol: str, timestamp: datetime, plan_identity: str) -> str:
    raw = f"{symbol}|{timestamp.astimezone(UTC).isoformat()}|{plan_identity}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def _spot_strategy_type(strategy: str) -> StrategyType:
    mapping = {
        "higher_timeframe_trend_pullback": StrategyType.TREND_PULLBACK,
        "breakout_retest": StrategyType.BREAKOUT_CONTINUATION,
        "accumulation_range_breakout": StrategyType.BREAKOUT_CONTINUATION,
        "liquidity_sweep_daily_recovery": StrategyType.LIQUIDITY_REVERSAL,
        "relative_strength_leader_pullback": StrategyType.TREND_PULLBACK,
        "post_capitulation_recovery": StrategyType.LIQUIDITY_REVERSAL,
    }
    return mapping[strategy]


def _result_order_key(result: IntakeResult) -> tuple[str, str, str]:
    return (result.symbol, result.status.value, result.reason.value)
