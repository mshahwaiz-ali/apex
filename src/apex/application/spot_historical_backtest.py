"""Deterministic chronological cash-spot execution simulation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_historical_dataset import (
    SpotHistoricalDatasetManifest,
    hash_spot_historical_rows,
    load_spot_historical_rows,
)
from apex.application.spot_historical_replay import SpotHistoricalReplayManifest
from apex.domain.models import Candle

SPOT_HISTORICAL_BACKTEST_SCHEMA_VERSION = 1


class SpotBacktestConfig(BaseModel):
    """Cash-account execution assumptions for one historical campaign."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    starting_cash: float = Field(default=10_000.0, gt=0)
    fee_rate: float = Field(default=0.001, ge=0, lt=0.1)
    slippage_rate: float = Field(default=0.0005, ge=0, lt=0.1)
    maximum_position_allocation: float = Field(default=0.25, gt=0, le=1)
    maximum_total_exposure: float = Field(default=0.80, gt=0, le=1)
    maximum_open_positions: int = Field(default=4, ge=1)
    quote_reserve: float = Field(default=0.10, ge=0, lt=1)
    entry_expiry_hours: int = Field(default=48, ge=1)
    maximum_holding_hours: int = Field(default=720, ge=1)
    ambiguous_candle_policy: Literal["conservative", "optimistic"] = "conservative"

    @model_validator(mode="after")
    def validate_exposure(self) -> SpotBacktestConfig:
        if self.quote_reserve + self.maximum_total_exposure > 1.0 + 1e-12:
            raise ValueError("quote reserve plus maximum exposure cannot exceed total equity")
        return self


class SpotHistoricalBacktestManifest(BaseModel):
    """Immutable provenance and summary for one spot backtest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SPOT_HISTORICAL_BACKTEST_SCHEMA_VERSION
    campaign_id: str
    source_dataset_sha256: str
    replay_records_sha256: str
    replay_configuration_sha256: str
    backtest_configuration_sha256: str
    result_sha256: str
    signal_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    plan_count: int = Field(ge=0)
    fill_count: int = Field(ge=0)
    trade_count: int = Field(ge=0)
    ending_equity: float = Field(ge=0)


@dataclass(frozen=True, slots=True)
class SpotHistoricalBacktestResult:
    manifest: SpotHistoricalBacktestManifest
    payload: dict[str, Any]


@dataclass(slots=True)
class _Order:
    order_id: str
    symbol: str
    decision_time: datetime
    expires_at: datetime
    strategy: str
    regime: str
    eligibility_state: str
    entry_state: str
    entries: list[dict[str, Any]]
    stop_price: float
    targets: list[dict[str, Any]]
    maximum_chase_price: float
    invalidation_price: float
    capital_budget: float
    filled_labels: set[str] = field(default_factory=set)
    quantity: float = 0.0
    entry_notional: float = 0.0
    entry_fees: float = 0.0
    slippage_cost: float = 0.0
    opened_at: datetime | None = None
    remaining_quantity: float = 0.0
    completed_targets: set[str] = field(default_factory=set)


@dataclass(slots=True)
class _Wallet:
    cash: float
    realized_pnl: float = 0.0
    fees: float = 0.0
    slippage_cost: float = 0.0


def run_spot_historical_backtest(
    *,
    campaign_id: str,
    dataset_records_path: Path,
    dataset_manifest_path: Path,
    replay_records_path: Path,
    replay_manifest_path: Path,
    config: SpotBacktestConfig,
) -> SpotHistoricalBacktestResult:
    """Execute replay plans against later candles with a shared cash wallet."""

    normalized_campaign = campaign_id.strip()
    if not normalized_campaign:
        raise ValueError("historical spot backtest campaign id cannot be blank")

    dataset_rows = load_spot_historical_rows(dataset_records_path)
    dataset_manifest = SpotHistoricalDatasetManifest.model_validate_json(
        dataset_manifest_path.read_text(encoding="utf-8")
    )
    if hash_spot_historical_rows(dataset_rows) != dataset_manifest.dataset_sha256:
        raise ValueError("historical spot dataset hash does not match its manifest")

    replay_records = _load_jsonl(replay_records_path)
    replay_manifest = SpotHistoricalReplayManifest.model_validate_json(
        replay_manifest_path.read_text(encoding="utf-8")
    )
    replay_hash = _hash_rows(replay_records)
    if replay_hash != replay_manifest.records_sha256:
        raise ValueError("historical spot replay hash does not match its manifest")
    if replay_manifest.source_dataset_sha256 != dataset_manifest.dataset_sha256:
        raise ValueError("historical spot replay references a different dataset")

    candles = _group_candles(dataset_rows)
    wallet = _Wallet(cash=config.starting_cash)
    pending: list[_Order] = []
    closed_trades: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    counters: defaultdict[str, int] = defaultdict(int)

    records_by_time: defaultdict[datetime, list[Mapping[str, Any]]] = defaultdict(list)
    for record in replay_records:
        records_by_time[_parse_time(record["decision_time"])].append(record)

    all_times = sorted(
        {candle.close_time for series in candles.values() for candle in series}
        | set(records_by_time)
    )
    for now in all_times:
        for record in sorted(records_by_time.get(now, []), key=lambda item: str(item["symbol"])):
            counters["signal_count"] += 1
            eligibility = record.get("eligibility")
            if isinstance(eligibility, Mapping) and bool(eligibility.get("eligible")):
                counters["eligible_count"] += 1
            order = _order_from_record(record, wallet, pending, config)
            if order is not None:
                counters["plan_count"] += 1
                pending.append(order)
                events.append(_event(now, order.symbol, "PLAN_ACCEPTED", order.order_id))

        for order in list(pending):
            candle = _candle_closing_at(candles.get(order.symbol, ()), now)
            if candle is None or candle.open_time < order.decision_time:
                continue
            if order.quantity == 0 and now >= order.expires_at:
                counters["expired_entry_count"] += 1
                events.append(_event(now, order.symbol, "ENTRY_EXPIRED", order.order_id))
                pending.remove(order)
                continue
            if order.quantity == 0 and candle.low <= order.invalidation_price:
                counters["invalidated_entry_count"] += 1
                events.append(_event(now, order.symbol, "ENTRY_INVALIDATED", order.order_id))
                pending.remove(order)
                continue
            if order.quantity == 0 and candle.low > order.maximum_chase_price:
                counters["missed_entry_count"] += 1
                events.append(_event(now, order.symbol, "MAXIMUM_CHASE_REJECTED", order.order_id))
                pending.remove(order)
                continue

            _fill_entries(order, candle, wallet, config, counters, events)
            if order.quantity <= 0:
                continue
            exit_reason = _process_exits(order, candle, wallet, config, counters, events)
            if exit_reason is None and order.opened_at is not None:
                if now - order.opened_at >= timedelta(hours=config.maximum_holding_hours):
                    _close_all(order, candle.close, now, "TIME_EXIT", wallet, config, events)
                    exit_reason = "TIME_EXIT"
            if exit_reason is not None or order.remaining_quantity <= 1e-12:
                closed_trades.append(_trade_record(order, now, exit_reason or "FINAL_TARGET", wallet))
                counters["trade_count"] += 1
                pending.remove(order)

        equity_curve.append(_equity_point(now, wallet, pending, candles))

    final_time = all_times[-1] if all_times else datetime.min
    for order in list(pending):
        if order.remaining_quantity > 0:
            final_candle = candles[order.symbol][-1]
            _close_all(order, final_candle.close, final_time, "END_OF_DATASET", wallet, config, events)
            closed_trades.append(_trade_record(order, final_time, "END_OF_DATASET", wallet))
            counters["trade_count"] += 1
        elif order.quantity == 0:
            counters["missed_entry_count"] += 1
        pending.remove(order)

    ending_equity = wallet.cash
    metrics = _metrics(config.starting_cash, ending_equity, wallet, closed_trades, equity_curve, counters)
    payload: dict[str, Any] = {
        "schema_version": SPOT_HISTORICAL_BACKTEST_SCHEMA_VERSION,
        "campaign_id": normalized_campaign,
        "source_dataset_sha256": dataset_manifest.dataset_sha256,
        "replay_records_sha256": replay_manifest.records_sha256,
        "replay_configuration_sha256": replay_manifest.configuration_sha256,
        "backtest_configuration_sha256": _hash_payload(config.model_dump(mode="json")),
        "configuration": config.model_dump(mode="json"),
        "metrics": metrics,
        "events": events,
        "trades": closed_trades,
        "equity_curve": equity_curve,
    }
    result_hash = _hash_payload(payload)
    payload["result_sha256"] = result_hash
    manifest = SpotHistoricalBacktestManifest(
        campaign_id=normalized_campaign,
        source_dataset_sha256=dataset_manifest.dataset_sha256,
        replay_records_sha256=replay_manifest.records_sha256,
        replay_configuration_sha256=replay_manifest.configuration_sha256,
        backtest_configuration_sha256=payload["backtest_configuration_sha256"],
        result_sha256=result_hash,
        signal_count=counters["signal_count"],
        eligible_count=counters["eligible_count"],
        plan_count=counters["plan_count"],
        fill_count=counters["fill_count"],
        trade_count=counters["trade_count"],
        ending_equity=ending_equity,
    )
    return SpotHistoricalBacktestResult(manifest=manifest, payload=payload)


def write_spot_historical_backtest(
    *, result: SpotHistoricalBacktestResult, result_path: Path, manifest_path: Path, force: bool = False
) -> None:
    """Persist deterministic result and manifest atomically."""

    for path in (result_path, manifest_path):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite historical spot backtest file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(result_path, json.dumps(result.payload, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        manifest_path,
        json.dumps(result.manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
    )


def _order_from_record(
    record: Mapping[str, Any], wallet: _Wallet, pending: Sequence[_Order], config: SpotBacktestConfig
) -> _Order | None:
    analysis = record.get("analysis")
    if not isinstance(analysis, Mapping):
        return None
    planning = analysis.get("planning")
    if not isinstance(planning, Mapping):
        return None
    if len([order for order in pending if order.remaining_quantity > 0]) >= config.maximum_open_positions:
        return None
    entry_plan = planning["entry_plan"]
    position_plan = planning["position_plan"]
    selected = analysis.get("selected_strategy") or {}
    decision_time = _parse_time(record["decision_time"])
    equity = wallet.cash + sum(order.entry_notional for order in pending if order.remaining_quantity > 0)
    current_exposure = sum(order.entry_notional for order in pending if order.remaining_quantity > 0)
    exposure_room = max(config.maximum_total_exposure * equity - current_exposure, 0.0)
    cash_room = max(wallet.cash - config.quote_reserve * equity, 0.0)
    requested = float(position_plan["capital_allocated"])
    budget = min(requested, config.maximum_position_allocation * equity, exposure_room, cash_room)
    if budget <= 0:
        return None
    regime = str(selected.get("market_regime", record.get("market_regime", "UNKNOWN")))
    eligibility = record.get("eligibility") or {}
    return _Order(
        order_id=f"{record['symbol']}:{record['decision_time']}",
        symbol=str(record["symbol"]),
        decision_time=decision_time,
        expires_at=decision_time + timedelta(hours=config.entry_expiry_hours),
        strategy=str(selected.get("strategy", "UNKNOWN")),
        regime=regime,
        eligibility_state="ELIGIBLE" if eligibility.get("eligible") else "INELIGIBLE",
        entry_state=str(entry_plan["state"]),
        entries=[dict(item) for item in entry_plan["entries"]],
        stop_price=float(planning["stop_plan"]["protective_stop_price"]),
        targets=[dict(item) for item in planning["target_plan"]["targets"]],
        maximum_chase_price=float(entry_plan["maximum_chase_price"]),
        invalidation_price=float(entry_plan["invalidation_price"]),
        capital_budget=budget,
    )


def _fill_entries(
    order: _Order, candle: Candle, wallet: _Wallet, config: SpotBacktestConfig,
    counters: defaultdict[str, int], events: list[dict[str, Any]],
) -> None:
    for leg in order.entries:
        label = str(leg["label"])
        if label in order.filled_labels:
            continue
        limit_price = float(leg["price"])
        if not (candle.low <= limit_price <= candle.high):
            continue
        budget = order.capital_budget * float(leg["allocation_percentage"]) / 100.0
        fill_price = limit_price * (1 + config.slippage_rate)
        gross_quantity = budget / fill_price
        fee = budget * config.fee_rate
        total_cost = budget + fee
        if total_cost > wallet.cash:
            budget = wallet.cash / (1 + config.fee_rate)
            gross_quantity = budget / fill_price
            fee = budget * config.fee_rate
            total_cost = budget + fee
        if gross_quantity <= 0:
            continue
        wallet.cash -= total_cost
        wallet.fees += fee
        slippage = gross_quantity * (fill_price - limit_price)
        wallet.slippage_cost += slippage
        order.quantity += gross_quantity
        order.remaining_quantity += gross_quantity
        order.entry_notional += budget
        order.entry_fees += fee
        order.slippage_cost += slippage
        order.filled_labels.add(label)
        order.opened_at = order.opened_at or candle.close_time
        counters["fill_count"] += 1
        events.append(_event(candle.close_time, order.symbol, "ENTRY_FILLED", order.order_id, label))


def _process_exits(
    order: _Order, candle: Candle, wallet: _Wallet, config: SpotBacktestConfig,
    counters: defaultdict[str, int], events: list[dict[str, Any]],
) -> str | None:
    pending_targets = [target for target in order.targets if str(target["label"]) not in order.completed_targets]
    hit_stop = candle.low <= order.stop_price
    hit_targets = [target for target in pending_targets if candle.high >= float(target["price"])]
    if hit_stop and hit_targets and config.ambiguous_candle_policy == "conservative":
        _close_all(order, order.stop_price, candle.close_time, "STOP_LOSS", wallet, config, events)
        counters["stop_count"] += 1
        return "STOP_LOSS"
    if hit_targets:
        for target in hit_targets:
            label = str(target["label"])
            original_share = float(target["sell_percentage"]) / 100.0
            quantity = min(order.quantity * original_share, order.remaining_quantity)
            _sell(order, quantity, float(target["price"]), candle.close_time, label, wallet, config, events)
            order.completed_targets.add(label)
        if order.remaining_quantity <= 1e-12:
            return "FINAL_TARGET"
    if hit_stop:
        _close_all(order, order.stop_price, candle.close_time, "STOP_LOSS", wallet, config, events)
        counters["stop_count"] += 1
        return "STOP_LOSS"
    return None


def _sell(
    order: _Order, quantity: float, reference_price: float, now: datetime, reason: str,
    wallet: _Wallet, config: SpotBacktestConfig, events: list[dict[str, Any]],
) -> None:
    fill_price = reference_price * (1 - config.slippage_rate)
    gross = quantity * fill_price
    fee = gross * config.fee_rate
    wallet.cash += gross - fee
    wallet.fees += fee
    wallet.slippage_cost += quantity * (reference_price - fill_price)
    order.remaining_quantity = max(order.remaining_quantity - quantity, 0.0)
    events.append(_event(now, order.symbol, "EXIT_FILLED", order.order_id, reason))


def _close_all(
    order: _Order, price: float, now: datetime, reason: str, wallet: _Wallet,
    config: SpotBacktestConfig, events: list[dict[str, Any]],
) -> None:
    _sell(order, order.remaining_quantity, price, now, reason, wallet, config, events)


def _trade_record(order: _Order, closed_at: datetime, exit_reason: str, wallet: _Wallet) -> dict[str, Any]:
    average_entry = order.entry_notional / order.quantity if order.quantity else 0.0
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "strategy": order.strategy,
        "market_regime": order.regime,
        "eligibility_state": order.eligibility_state,
        "entry_state": order.entry_state,
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
        "closed_at": closed_at.isoformat(),
        "average_entry_price": average_entry,
        "quantity": order.quantity,
        "entry_notional": order.entry_notional,
        "entry_fees": order.entry_fees,
        "slippage_cost": order.slippage_cost,
        "filled_entry_labels": sorted(order.filled_labels),
        "completed_target_labels": sorted(order.completed_targets),
        "exit_reason": exit_reason,
        "wallet_cash_after": wallet.cash,
    }


def _metrics(
    starting: float, ending: float, wallet: _Wallet, trades: Sequence[Mapping[str, Any]],
    equity_curve: Sequence[Mapping[str, Any]], counters: Mapping[str, int],
) -> dict[str, Any]:
    net = ending - starting
    peak = starting
    maximum_drawdown = 0.0
    for point in equity_curve:
        equity = float(point["equity"])
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak if peak else 0.0)
    return {
        **dict(counters),
        "gross_profit": max(net, 0.0),
        "gross_loss": min(net, 0.0),
        "net_profit": net,
        "profit_factor": None if net >= 0 else 0.0,
        "fees": wallet.fees,
        "slippage_cost": wallet.slippage_cost,
        "maximum_drawdown": maximum_drawdown,
        "ending_equity": ending,
        "win_rate": None,
        "expectancy": net / len(trades) if trades else 0.0,
        "average_holding_duration_hours": _average_holding_hours(trades),
        "performance_by_symbol": _group_count(trades, "symbol"),
        "performance_by_strategy": _group_count(trades, "strategy"),
        "performance_by_market_regime": _group_count(trades, "market_regime"),
        "performance_by_eligibility_state": _group_count(trades, "eligibility_state"),
        "performance_by_entry_state": _group_count(trades, "entry_state"),
        "performance_by_exit_reason": _group_count(trades, "exit_reason"),
    }


def _average_holding_hours(trades: Sequence[Mapping[str, Any]]) -> float:
    durations = [
        (_parse_time(trade["closed_at"]) - _parse_time(trade["opened_at"])).total_seconds() / 3600
        for trade in trades if trade.get("opened_at")
    ]
    return sum(durations) / len(durations) if durations else 0.0


def _group_count(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    result: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        result[str(row.get(key, "UNKNOWN"))] += 1
    return dict(sorted(result.items()))


def _equity_point(
    now: datetime, wallet: _Wallet, orders: Sequence[_Order],
    candles: Mapping[str, Sequence[Candle]],
) -> dict[str, Any]:
    market_value = 0.0
    for order in orders:
        if order.remaining_quantity <= 0:
            continue
        visible = [candle for candle in candles.get(order.symbol, ()) if candle.close_time <= now]
        if visible:
            market_value += order.remaining_quantity * visible[-1].close
    equity = wallet.cash + market_value
    return {"time": now.isoformat(), "cash": wallet.cash, "market_value": market_value, "equity": equity}


def _group_candles(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[Candle, ...]]:
    grouped: defaultdict[str, list[Candle]] = defaultdict(list)
    for row in rows:
        candle = Candle.model_validate(row)
        if candle.timeframe == "4h":
            grouped[candle.symbol.upper()].append(candle)
    return {symbol: tuple(sorted(values, key=lambda item: item.open_time)) for symbol, values in grouped.items()}


def _candle_closing_at(candles: Sequence[Candle], now: datetime) -> Candle | None:
    return next((candle for candle in candles if candle.close_time == now), None)


def _event(now: datetime, symbol: str, event: str, order_id: str, detail: str | None = None) -> dict[str, Any]:
    return {"time": now.isoformat(), "symbol": symbol, "event": event, "order_id": order_id, "detail": detail}


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows = tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if not rows:
        raise ValueError(f"JSONL file is empty: {path}")
    return rows


def _hash_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    text = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be an ISO-8601 string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
