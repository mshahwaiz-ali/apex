"""Deterministic chronological cash-spot execution simulation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apex.application.spot_historical_dataset import (
    SpotHistoricalDatasetManifest,
    hash_spot_historical_rows,
    load_spot_historical_rows,
)
from apex.application.spot_historical_replay import SpotHistoricalReplayManifest
from apex.domain.models import Candle

SPOT_HISTORICAL_BACKTEST_SCHEMA_VERSION = 1
_EXECUTION_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "4h")
_EPSILON = 1e-12


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
    def validate_exposure(self) -> Self:
        if self.quote_reserve + self.maximum_total_exposure > 1.0 + _EPSILON:
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
    completed_targets: set[str] = field(default_factory=set)
    quantity: float = 0.0
    remaining_quantity: float = 0.0
    entry_notional: float = 0.0
    entry_fees: float = 0.0
    exit_gross: float = 0.0
    exit_fees: float = 0.0
    realized_pnl: float = 0.0
    slippage_cost: float = 0.0
    opened_at: datetime | None = None
    last_fill_time: datetime | None = None

    @property
    def average_entry_price(self) -> float:
        return self.entry_notional / self.quantity if self.quantity else 0.0

    @property
    def active(self) -> bool:
        return self.remaining_quantity > _EPSILON


@dataclass(slots=True)
class _Wallet:
    cash: float
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
    """Execute verified replay plans against later candles with a shared cash wallet."""

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
    if _hash_rows(replay_records) != replay_manifest.records_sha256:
        raise ValueError("historical spot replay hash does not match its manifest")
    if replay_manifest.source_dataset_sha256 != dataset_manifest.dataset_sha256:
        raise ValueError("historical spot replay references a different dataset")

    candles, execution_timeframes = _group_execution_candles(dataset_rows)
    wallet = _Wallet(cash=config.starting_cash)
    orders: list[_Order] = []
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
    if not all_times:
        raise ValueError("historical spot backtest has no chronological timestamps")

    for now in all_times:
        for record in sorted(records_by_time.get(now, []), key=lambda item: str(item["symbol"])):
            counters["signal_count"] += 1
            eligibility = record.get("eligibility")
            if isinstance(eligibility, Mapping) and bool(eligibility.get("eligible")):
                counters["eligible_count"] += 1
            order, rejection = _order_from_record(record, wallet, orders, candles, now, config)
            if order is None:
                if rejection is not None:
                    counters[rejection] += 1
                continue
            counters["plan_count"] += 1
            orders.append(order)
            events.append(_event(now, order.symbol, "PLAN_ACCEPTED", order.order_id))

        for order in list(orders):
            candle = _candle_closing_at(candles.get(order.symbol, ()), now)
            if candle is None or candle.open_time < order.decision_time:
                continue
            if not order.active and now >= order.expires_at:
                counters["expired_entry_count"] += 1
                events.append(_event(now, order.symbol, "ENTRY_EXPIRED", order.order_id))
                orders.remove(order)
                continue
            if not order.active and candle.low <= order.invalidation_price:
                counters["invalidated_entry_count"] += 1
                events.append(_event(now, order.symbol, "ENTRY_INVALIDATED", order.order_id))
                orders.remove(order)
                continue
            if not order.active and candle.low > order.maximum_chase_price:
                counters["missed_entry_count"] += 1
                events.append(_event(now, order.symbol, "MAXIMUM_CHASE_REJECTED", order.order_id))
                orders.remove(order)
                continue

            filled_this_candle = _fill_entries(order, candle, wallet, config, counters, events)
            if not order.active or filled_this_candle:
                continue
            exit_reason = _process_exits(order, candle, wallet, config, counters, events)
            if exit_reason is None and order.opened_at is not None:
                if now - order.opened_at >= timedelta(hours=config.maximum_holding_hours):
                    _close_all(order, candle.close, now, "TIME_EXIT", wallet, config, events)
                    exit_reason = "TIME_EXIT"
                    counters["time_exit_count"] += 1
            if exit_reason is not None or not order.active:
                closed_trades.append(_trade_record(order, now, exit_reason or "FINAL_TARGET", wallet))
                counters["trade_count"] += 1
                orders.remove(order)

        equity_curve.append(_equity_point(now, wallet, orders, candles))

    final_time = all_times[-1]
    for order in list(orders):
        if order.active:
            final_candle = candles[order.symbol][-1]
            _close_all(order, final_candle.close, final_time, "END_OF_DATASET", wallet, config, events)
            closed_trades.append(_trade_record(order, final_time, "END_OF_DATASET", wallet))
            counters["trade_count"] += 1
            counters["end_of_dataset_exit_count"] += 1
        else:
            counters["missed_entry_count"] += 1
        orders.remove(order)
    equity_curve.append(_equity_point(final_time, wallet, orders, candles))

    metrics = _metrics(config.starting_cash, wallet, closed_trades, equity_curve, counters)
    backtest_hash = _hash_payload(config.model_dump(mode="json"))
    payload: dict[str, Any] = {
        "schema_version": SPOT_HISTORICAL_BACKTEST_SCHEMA_VERSION,
        "campaign_id": normalized_campaign,
        "source_dataset_sha256": dataset_manifest.dataset_sha256,
        "replay_records_sha256": replay_manifest.records_sha256,
        "replay_configuration_sha256": replay_manifest.configuration_sha256,
        "backtest_configuration_sha256": backtest_hash,
        "execution_timeframes": execution_timeframes,
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
        backtest_configuration_sha256=backtest_hash,
        result_sha256=result_hash,
        signal_count=counters["signal_count"],
        eligible_count=counters["eligible_count"],
        plan_count=counters["plan_count"],
        fill_count=counters["fill_count"],
        trade_count=counters["trade_count"],
        ending_equity=metrics["ending_equity"],
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
    record: Mapping[str, Any],
    wallet: _Wallet,
    orders: Sequence[_Order],
    candles: Mapping[str, Sequence[Candle]],
    now: datetime,
    config: SpotBacktestConfig,
) -> tuple[_Order | None, str | None]:
    analysis = record.get("analysis")
    if not isinstance(analysis, Mapping):
        return None, None
    planning = analysis.get("planning")
    if not isinstance(planning, Mapping):
        return None, None
    symbol = str(record["symbol"]).upper()
    if symbol not in candles:
        return None, "missing_execution_data_count"
    if any(order.symbol == symbol and order.active for order in orders):
        return None, "duplicate_position_rejection_count"
    if sum(order.active for order in orders) >= config.maximum_open_positions:
        return None, "open_position_limit_rejection_count"

    entry_plan = _require_mapping(planning, "entry_plan")
    position_plan = _require_mapping(planning, "position_plan")
    stop_plan = _require_mapping(planning, "stop_plan")
    target_plan = _require_mapping(planning, "target_plan")
    selected = analysis.get("selected_strategy")
    selected_map = selected if isinstance(selected, Mapping) else {}
    equity = _portfolio_equity(now, wallet, orders, candles)
    current_exposure = _market_value(now, orders, candles)
    exposure_room = max(config.maximum_total_exposure * equity - current_exposure, 0.0)
    cash_room = max(wallet.cash - config.quote_reserve * equity, 0.0)
    requested = float(position_plan["capital_allocated"])
    budget = min(requested, config.maximum_position_allocation * equity, exposure_room, cash_room)
    if budget <= _EPSILON:
        return None, "exposure_rejection_count"
    eligibility = record.get("eligibility")
    eligibility_map = eligibility if isinstance(eligibility, Mapping) else {}
    decision_time = _parse_time(record["decision_time"])
    return (
        _Order(
            order_id=f"{symbol}:{record['decision_time']}",
            symbol=symbol,
            decision_time=decision_time,
            expires_at=decision_time + timedelta(hours=config.entry_expiry_hours),
            strategy=str(selected_map.get("strategy", "UNKNOWN")),
            regime=str(selected_map.get("market_regime", record.get("market_regime", "UNKNOWN"))),
            eligibility_state="ELIGIBLE" if eligibility_map.get("eligible") else "INELIGIBLE",
            entry_state=str(entry_plan["state"]),
            entries=[dict(item) for item in _require_sequence(entry_plan, "entries")],
            stop_price=float(stop_plan["protective_stop_price"]),
            targets=[dict(item) for item in _require_sequence(target_plan, "targets")],
            maximum_chase_price=float(entry_plan["maximum_chase_price"]),
            invalidation_price=float(entry_plan["invalidation_price"]),
            capital_budget=budget,
        ),
        None,
    )


def _fill_entries(
    order: _Order,
    candle: Candle,
    wallet: _Wallet,
    config: SpotBacktestConfig,
    counters: defaultdict[str, int],
    events: list[dict[str, Any]],
) -> bool:
    filled = False
    for leg in order.entries:
        label = str(leg["label"])
        if label in order.filled_labels:
            continue
        limit_price = float(leg["price"])
        if not (candle.low <= limit_price <= candle.high):
            continue
        budget = order.capital_budget * float(leg["allocation_percentage"]) / 100.0
        budget = min(budget, wallet.cash / (1 + config.fee_rate))
        fill_price = limit_price * (1 + config.slippage_rate)
        quantity = budget / fill_price
        if quantity <= _EPSILON:
            continue
        fee = budget * config.fee_rate
        wallet.cash -= budget + fee
        wallet.fees += fee
        slippage = quantity * (fill_price - limit_price)
        wallet.slippage_cost += slippage
        order.quantity += quantity
        order.remaining_quantity += quantity
        order.entry_notional += budget
        order.entry_fees += fee
        order.slippage_cost += slippage
        order.filled_labels.add(label)
        order.opened_at = order.opened_at or candle.close_time
        order.last_fill_time = candle.close_time
        counters["fill_count"] += 1
        events.append(_event(candle.close_time, order.symbol, "ENTRY_FILLED", order.order_id, label))
        filled = True
    return filled


def _process_exits(
    order: _Order,
    candle: Candle,
    wallet: _Wallet,
    config: SpotBacktestConfig,
    counters: defaultdict[str, int],
    events: list[dict[str, Any]],
) -> str | None:
    pending_targets = [
        target for target in order.targets if str(target["label"]) not in order.completed_targets
    ]
    hit_stop = candle.low <= order.stop_price
    hit_targets = [target for target in pending_targets if candle.high >= float(target["price"])]
    if hit_stop and hit_targets and config.ambiguous_candle_policy == "conservative":
        _close_all(order, order.stop_price, candle.close_time, "STOP_LOSS", wallet, config, events)
        counters["stop_count"] += 1
        counters["ambiguous_candle_count"] += 1
        return "STOP_LOSS"
    if hit_targets:
        if hit_stop:
            counters["ambiguous_candle_count"] += 1
        for target in hit_targets:
            label = str(target["label"])
            quantity = min(
                order.quantity * float(target["sell_percentage"]) / 100.0,
                order.remaining_quantity,
            )
            _sell(order, quantity, float(target["price"]), candle.close_time, label, wallet, config, events)
            order.completed_targets.add(label)
            counters["target_fill_count"] += 1
        if not order.active:
            return "FINAL_TARGET"
    if hit_stop and order.active:
        _close_all(order, order.stop_price, candle.close_time, "STOP_LOSS", wallet, config, events)
        counters["stop_count"] += 1
        return "STOP_LOSS"
    return None


def _sell(
    order: _Order,
    quantity: float,
    reference_price: float,
    now: datetime,
    reason: str,
    wallet: _Wallet,
    config: SpotBacktestConfig,
    events: list[dict[str, Any]],
) -> None:
    quantity = min(quantity, order.remaining_quantity)
    if quantity <= _EPSILON:
        return
    fill_price = reference_price * (1 - config.slippage_rate)
    gross = quantity * fill_price
    fee = gross * config.fee_rate
    cost_basis = quantity * order.average_entry_price
    allocated_entry_fee = order.entry_fees * (quantity / order.quantity)
    realized = gross - fee - cost_basis - allocated_entry_fee
    wallet.cash += gross - fee
    wallet.fees += fee
    slippage = quantity * (reference_price - fill_price)
    wallet.slippage_cost += slippage
    order.exit_gross += gross
    order.exit_fees += fee
    order.realized_pnl += realized
    order.slippage_cost += slippage
    order.remaining_quantity = max(order.remaining_quantity - quantity, 0.0)
    events.append(_event(now, order.symbol, "EXIT_FILLED", order.order_id, reason))


def _close_all(
    order: _Order,
    price: float,
    now: datetime,
    reason: str,
    wallet: _Wallet,
    config: SpotBacktestConfig,
    events: list[dict[str, Any]],
) -> None:
    _sell(order, order.remaining_quantity, price, now, reason, wallet, config, events)


def _trade_record(order: _Order, closed_at: datetime, exit_reason: str, wallet: _Wallet) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "strategy": order.strategy,
        "market_regime": order.regime,
        "eligibility_state": order.eligibility_state,
        "entry_state": order.entry_state,
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
        "closed_at": closed_at.isoformat(),
        "average_entry_price": order.average_entry_price,
        "quantity": order.quantity,
        "entry_notional": order.entry_notional,
        "entry_fees": order.entry_fees,
        "exit_gross": order.exit_gross,
        "exit_fees": order.exit_fees,
        "realized_pnl": order.realized_pnl,
        "return_on_entry_notional": (
            order.realized_pnl / order.entry_notional if order.entry_notional else 0.0
        ),
        "slippage_cost": order.slippage_cost,
        "filled_entry_labels": sorted(order.filled_labels),
        "completed_target_labels": sorted(order.completed_targets),
        "exit_reason": exit_reason,
        "wallet_cash_after": wallet.cash,
    }


def _metrics(
    starting: float,
    wallet: _Wallet,
    trades: Sequence[Mapping[str, Any]],
    equity_curve: Sequence[Mapping[str, Any]],
    counters: Mapping[str, int],
) -> dict[str, Any]:
    pnls = [float(trade["realized_pnl"]) for trade in trades]
    gross_profit = sum(value for value in pnls if value > 0)
    gross_loss = sum(value for value in pnls if value < 0)
    wins = sum(value > 0 for value in pnls)
    ending = float(equity_curve[-1]["equity"]) if equity_curve else wallet.cash
    peak = starting
    maximum_drawdown = 0.0
    exposure_samples: list[float] = []
    for point in equity_curve:
        equity = float(point["equity"])
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak if peak else 0.0)
        exposure_samples.append(float(point["exposure_utilization"]))
    return {
        **dict(counters),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": ending - starting,
        "profit_factor": (
            gross_profit / abs(gross_loss) if gross_loss < 0 else None
        ),
        "fees": wallet.fees,
        "slippage_cost": wallet.slippage_cost,
        "maximum_drawdown": maximum_drawdown,
        "ending_equity": ending,
        "win_rate": wins / len(pnls) if pnls else None,
        "expectancy": sum(pnls) / len(pnls) if pnls else 0.0,
        "average_holding_duration_hours": _average_holding_hours(trades),
        "average_exposure_utilization": (
            sum(exposure_samples) / len(exposure_samples) if exposure_samples else 0.0
        ),
        "maximum_exposure_utilization": max(exposure_samples, default=0.0),
        "performance_by_symbol": _group_performance(trades, "symbol"),
        "performance_by_strategy": _group_performance(trades, "strategy"),
        "performance_by_market_regime": _group_performance(trades, "market_regime"),
        "performance_by_eligibility_state": _group_performance(trades, "eligibility_state"),
        "performance_by_entry_state": _group_performance(trades, "entry_state"),
        "performance_by_exit_reason": _group_performance(trades, "exit_reason"),
    }


def _average_holding_hours(trades: Sequence[Mapping[str, Any]]) -> float:
    durations = [
        (_parse_time(trade["closed_at"]) - _parse_time(trade["opened_at"])).total_seconds()
        / 3600
        for trade in trades
        if trade.get("opened_at")
    ]
    return sum(durations) / len(durations) if durations else 0.0


def _group_performance(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "UNKNOWN"))].append(float(row["realized_pnl"]))
    return {
        group: {
            "trade_count": len(values),
            "win_count": sum(value > 0 for value in values),
            "net_profit": sum(values),
            "expectancy": sum(values) / len(values),
        }
        for group, values in sorted(grouped.items())
    }


def _equity_point(
    now: datetime,
    wallet: _Wallet,
    orders: Sequence[_Order],
    candles: Mapping[str, Sequence[Candle]],
) -> dict[str, Any]:
    market_value = _market_value(now, orders, candles)
    equity = wallet.cash + market_value
    return {
        "time": now.isoformat(),
        "cash": wallet.cash,
        "market_value": market_value,
        "equity": equity,
        "exposure_utilization": market_value / equity if equity > 0 else 0.0,
        "open_position_count": sum(order.active for order in orders),
    }


def _portfolio_equity(
    now: datetime,
    wallet: _Wallet,
    orders: Sequence[_Order],
    candles: Mapping[str, Sequence[Candle]],
) -> float:
    return wallet.cash + _market_value(now, orders, candles)


def _market_value(
    now: datetime,
    orders: Sequence[_Order],
    candles: Mapping[str, Sequence[Candle]],
) -> float:
    total = 0.0
    for order in orders:
        if not order.active:
            continue
        visible = [candle for candle in candles.get(order.symbol, ()) if candle.close_time <= now]
        if visible:
            total += order.remaining_quantity * visible[-1].close
    return total


def _group_execution_candles(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, tuple[Candle, ...]], dict[str, str]]:
    available: defaultdict[tuple[str, str], list[Candle]] = defaultdict(list)
    for row in rows:
        candle = Candle.model_validate(row)
        available[(candle.symbol.upper(), candle.timeframe)].append(candle)
    symbols = sorted({symbol for symbol, _ in available})
    grouped: dict[str, tuple[Candle, ...]] = {}
    selected: dict[str, str] = {}
    for symbol in symbols:
        timeframe = next(
            (value for value in _EXECUTION_TIMEFRAMES if available.get((symbol, value))),
            None,
        )
        if timeframe is None:
            continue
        selected[symbol] = timeframe
        grouped[symbol] = tuple(
            sorted(available[(symbol, timeframe)], key=lambda item: item.open_time)
        )
    return grouped, selected


def _candle_closing_at(candles: Sequence[Candle], now: datetime) -> Candle | None:
    return next((candle for candle in candles if candle.close_time == now), None)


def _event(
    now: datetime,
    symbol: str,
    event: str,
    order_id: str,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "time": now.isoformat(),
        "symbol": symbol,
        "event": event,
        "order_id": order_id,
        "detail": detail,
    }


def _require_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = container.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"historical spot replay planning field must be an object: {key}")
    return value


def _require_sequence(container: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    value = container.get(key)
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise TypeError(f"historical spot replay planning field must be an object list: {key}")
    return value


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows = tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not rows:
        raise ValueError(f"JSONL file is empty: {path}")
    if not all(isinstance(row, dict) for row in rows):
        raise TypeError("historical spot replay JSONL rows must be objects")
    return rows


def _hash_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    text = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be an ISO-8601 string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
