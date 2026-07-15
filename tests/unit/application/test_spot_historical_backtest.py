from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.spot_historical_backtest import (
    SpotBacktestConfig,
    run_spot_historical_backtest,
    _Order,
    _Wallet,
    _fill_entries,
    _metrics,
    _process_exits,
    _trade_record,
)
from apex.application.spot_historical_dataset import (
    SpotHistoricalDatasetManifest,
    hash_spot_historical_rows,
)
from apex.application.spot_historical_replay import SpotHistoricalReplayManifest
from apex.domain.models import Candle


def _candle(*, low: float, high: float, close: float, hour: int = 1) -> Candle:
    opened = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
        source="test",
    )


def _order() -> _Order:
    decision = datetime(2026, 1, 1, tzinfo=UTC)
    return _Order(
        order_id="BTCUSDT:test",
        symbol="BTCUSDT",
        decision_time=decision,
        expires_at=decision + timedelta(hours=48),
        strategy="TREND_PULLBACK",
        regime="RISK_ON",
        eligibility_state="ELIGIBLE",
        entry_state="READY_NOW",
        entries=[
            {"label": "ENTRY_1", "price": 100.0, "allocation_percentage": 60.0},
            {"label": "ENTRY_2", "price": 95.0, "allocation_percentage": 40.0},
        ],
        stop_price=90.0,
        targets=[
            {"label": "TP1", "price": 110.0, "sell_percentage": 50.0},
            {"label": "TP2", "price": 120.0, "sell_percentage": 50.0},
        ],
        maximum_chase_price=103.0,
        invalidation_price=89.0,
        capital_budget=1_000.0,
    )


def test_partial_entries_and_targets_use_position_level_accounting() -> None:
    order = _order()
    wallet = _Wallet(cash=2_000.0)
    counters: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, object]] = []
    config = SpotBacktestConfig(fee_rate=0.001, slippage_rate=0.0)

    assert _fill_entries(order, _candle(low=99.0, high=101.0, close=100.0), wallet, config, counters, events)
    assert order.filled_labels == {"ENTRY_1"}
    assert order.entry_notional == pytest.approx(600.0)

    assert _fill_entries(order, _candle(low=94.0, high=96.0, close=95.0, hour=2), wallet, config, counters, events)
    assert order.filled_labels == {"ENTRY_1", "ENTRY_2"}
    assert order.entry_notional == pytest.approx(1_000.0)

    reason = _process_exits(
        order,
        _candle(low=105.0, high=111.0, close=109.0, hour=3),
        wallet,
        config,
        counters,
        events,
    )
    assert reason is None
    assert order.completed_targets == {"TP1"}
    assert order.remaining_quantity == pytest.approx(order.quantity * 0.5)

    reason = _process_exits(
        order,
        _candle(low=115.0, high=121.0, close=120.0, hour=4),
        wallet,
        config,
        counters,
        events,
    )
    assert reason == "FINAL_TARGET"
    trade = _trade_record(order, datetime(2026, 1, 1, 5, tzinfo=UTC), reason, wallet)
    assert trade["realized_pnl"] > 0
    assert trade["exit_fees"] > 0


def test_ambiguous_candle_policy_is_conservative_by_default() -> None:
    order = _order()
    wallet = _Wallet(cash=2_000.0)
    counters: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, object]] = []
    config = SpotBacktestConfig(fee_rate=0.0, slippage_rate=0.0)
    assert _fill_entries(order, _candle(low=99.0, high=101.0, close=100.0), wallet, config, counters, events)

    reason = _process_exits(
        order,
        _candle(low=89.0, high=111.0, close=100.0, hour=2),
        wallet,
        config,
        counters,
        events,
    )

    assert reason == "STOP_LOSS"
    assert counters["ambiguous_candle_count"] == 1
    assert order.realized_pnl < 0


def test_metrics_use_trade_pnl_and_exposure_curve() -> None:
    wallet = _Wallet(cash=1_050.0, fees=5.0, slippage_cost=2.0)
    trades = (
        {
            "realized_pnl": 100.0,
            "opened_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-01T02:00:00+00:00",
            "symbol": "BTCUSDT",
            "strategy": "A",
            "market_regime": "RISK_ON",
            "eligibility_state": "ELIGIBLE",
            "entry_state": "READY_NOW",
            "exit_reason": "FINAL_TARGET",
        },
        {
            "realized_pnl": -50.0,
            "opened_at": "2026-01-02T00:00:00+00:00",
            "closed_at": "2026-01-02T04:00:00+00:00",
            "symbol": "ETHUSDT",
            "strategy": "B",
            "market_regime": "NEUTRAL",
            "eligibility_state": "INELIGIBLE",
            "entry_state": "WAIT_FOR_RETEST",
            "exit_reason": "STOP_LOSS",
        },
    )
    curve = (
        {"equity": 1_000.0, "exposure_utilization": 0.0},
        {"equity": 900.0, "exposure_utilization": 0.5},
        {"equity": 1_050.0, "exposure_utilization": 0.0},
    )

    metrics = _metrics(1_000.0, wallet, trades, curve, {"trade_count": 2})

    assert metrics["gross_profit"] == 100.0
    assert metrics["gross_loss"] == -50.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["win_rate"] == 0.5
    assert metrics["expectancy"] == 25.0
    assert metrics["maximum_drawdown"] == pytest.approx(0.1)
    assert metrics["maximum_exposure_utilization"] == 0.5


def _hash_rows(rows: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _dataset_row(
    *,
    symbol: str,
    opened: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timeframe": "1h",
        "open_time": opened.isoformat(),
        "close_time": (opened + timedelta(hours=1)).isoformat(),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1_000.0,
        "is_closed": True,
        "source": "s9-execution-fixture",
    }


def _planning_record(
    *,
    campaign_id: str,
    dataset_hash: str,
    configuration_hash: str,
    symbol: str,
    decision_time: datetime,
    entry_price: float,
    stop_price: float,
    target_price: float,
    capital: float,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "symbol": symbol,
        "decision_time": decision_time.isoformat(),
        "source_dataset_sha256": dataset_hash,
        "configuration_sha256": configuration_hash,
        "eligibility": {
            "eligible": True,
            "reasons": ["ELIGIBLE"],
            "unavailable_fields": ["bid_ask_spread"],
        },
        "eligibility_data_complete": False,
        "unavailable_historical_fields": ["bid_ask_spread"],
        "analysis": {
            "schema_version": 1,
            "selected_strategy": {
                "strategy": "higher_timeframe_trend_pullback",
                "decision": "APPROVE",
                "eligibility": "RESEARCH",
                "thesis": f"{symbol}: deterministic execution fixture",
                "invalidation_price": stop_price,
                "evidence": ["fixture"],
                "rejection_reasons": [],
                "warnings": [],
            },
            "candidates": [],
            "planning": {
                "entry_plan": {
                    "state": "READY_NOW",
                    "current_price": entry_price,
                    "entries": [
                        {
                            "label": "ENTRY_1",
                            "price": entry_price,
                            "allocation_percentage": 100.0,
                            "requires_confirmation": False,
                        }
                    ],
                    "maximum_chase_price": entry_price * 1.03,
                    "invalidation_price": stop_price * 0.99,
                },
                "stop_plan": {
                    "structural_invalidation_price": stop_price,
                    "protective_stop_price": stop_price,
                    "thesis_failure_reason": "fixture stop",
                    "market_regime_exit_required": True,
                },
                "position_plan": {
                    "average_entry_price": entry_price,
                    "quantity": capital / entry_price,
                    "capital_allocated": capital,
                    "allocation_percentage_of_equity": capital / 100.0,
                    "planned_loss_amount": capital * 0.1,
                    "planned_loss_percentage_of_equity": 1.0,
                    "remaining_quote_reserve": 10_000.0 - capital,
                },
                "target_plan": {
                    "targets": [
                        {
                            "label": "RUNNER",
                            "price": target_price,
                            "sell_percentage": 100.0,
                            "rationale": "fixture final target",
                        }
                    ]
                },
                "lifecycle": {
                    "state": "WAITING_FOR_ENTRY",
                    "active_stop_price": stop_price,
                },
            },
            "warnings": ["fixture"],
        },
        "failure": None,
    }


def _write_execution_campaign(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    campaign_id = "s9-execution-fixture"
    decision_time = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        _dataset_row(
            symbol="BTCUSDT",
            opened=decision_time,
            open_price=101.0,
            high=102.0,
            low=99.0,
            close=100.0,
        ),
        _dataset_row(
            symbol="ETHUSDT",
            opened=decision_time,
            open_price=51.0,
            high=52.0,
            low=49.0,
            close=50.0,
        ),
        _dataset_row(
            symbol="BTCUSDT",
            opened=decision_time + timedelta(hours=1),
            open_price=100.0,
            high=112.0,
            low=99.0,
            close=111.0,
        ),
        _dataset_row(
            symbol="ETHUSDT",
            opened=decision_time + timedelta(hours=1),
            open_price=50.0,
            high=51.0,
            low=44.0,
            close=45.0,
        ),
    ]
    rows.sort(key=lambda row: (str(row["open_time"]), str(row["symbol"])))
    dataset_hash = hash_spot_historical_rows(rows)
    dataset_manifest = SpotHistoricalDatasetManifest(
        dataset_id=campaign_id,
        provider="fixture",
        symbols=("BTCUSDT", "ETHUSDT"),
        timeframes=("1h",),
        start_time=decision_time,
        end_time=decision_time + timedelta(hours=2),
        candle_count=len(rows),
        symbol_timeframe_counts={"BTCUSDT:1h": 2, "ETHUSDT:1h": 2},
        dataset_sha256=dataset_hash,
    )

    replay_configuration_hash = "a" * 64
    records = [
        _planning_record(
            campaign_id=campaign_id,
            dataset_hash=dataset_hash,
            configuration_hash=replay_configuration_hash,
            symbol="BTCUSDT",
            decision_time=decision_time,
            entry_price=100.0,
            stop_price=90.0,
            target_price=110.0,
            capital=2_000.0,
        ),
        _planning_record(
            campaign_id=campaign_id,
            dataset_hash=dataset_hash,
            configuration_hash=replay_configuration_hash,
            symbol="ETHUSDT",
            decision_time=decision_time,
            entry_price=50.0,
            stop_price=45.0,
            target_price=60.0,
            capital=2_000.0,
        ),
    ]
    replay_hash = _hash_rows(records)
    replay_manifest = SpotHistoricalReplayManifest(
        campaign_id=campaign_id,
        source_dataset_id=campaign_id,
        source_dataset_sha256=dataset_hash,
        configuration_sha256=replay_configuration_hash,
        records_sha256=replay_hash,
        decision_count=len(records),
        accepted_plan_count=len(records),
        eligibility_pass_count=len(records),
        failure_count=0,
    )

    dataset_records_path = tmp_path / "history.jsonl"
    dataset_manifest_path = tmp_path / "history.manifest.json"
    replay_records_path = tmp_path / "replay.jsonl"
    replay_manifest_path = tmp_path / "replay.manifest.json"

    dataset_records_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    dataset_manifest_path.write_text(
        dataset_manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    replay_records_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    replay_manifest_path.write_text(
        replay_manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return (
        dataset_records_path,
        dataset_manifest_path,
        replay_records_path,
        replay_manifest_path,
    )


def test_full_shared_wallet_execution_campaign_is_deterministic(tmp_path: Path) -> None:
    (
        dataset_records_path,
        dataset_manifest_path,
        replay_records_path,
        replay_manifest_path,
    ) = _write_execution_campaign(tmp_path)
    config = SpotBacktestConfig(
        starting_cash=10_000.0,
        fee_rate=0.001,
        slippage_rate=0.0005,
        maximum_position_allocation=0.25,
        maximum_total_exposure=0.8,
        maximum_open_positions=4,
        quote_reserve=0.1,
        entry_expiry_hours=48,
        maximum_holding_hours=720,
        ambiguous_candle_policy="conservative",
    )

    first = run_spot_historical_backtest(
        campaign_id="s9-execution-fixture",
        dataset_records_path=dataset_records_path,
        dataset_manifest_path=dataset_manifest_path,
        replay_records_path=replay_records_path,
        replay_manifest_path=replay_manifest_path,
        config=config,
    )
    second = run_spot_historical_backtest(
        campaign_id="s9-execution-fixture",
        dataset_records_path=dataset_records_path,
        dataset_manifest_path=dataset_manifest_path,
        replay_records_path=replay_records_path,
        replay_manifest_path=replay_manifest_path,
        config=config,
    )

    assert first.payload == second.payload
    assert first.manifest == second.manifest
    assert first.manifest.signal_count == 2
    assert first.manifest.eligible_count == 2
    assert first.manifest.plan_count == 2
    assert first.manifest.fill_count == 2
    assert first.manifest.trade_count == 2

    trades = {trade["symbol"]: trade for trade in first.payload["trades"]}
    assert trades["BTCUSDT"]["exit_reason"] == "FINAL_TARGET"
    assert trades["BTCUSDT"]["realized_pnl"] > 0
    assert trades["ETHUSDT"]["exit_reason"] == "STOP_LOSS"
    assert trades["ETHUSDT"]["realized_pnl"] < 0

    metrics = first.payload["metrics"]
    assert metrics["fees"] > 0
    assert metrics["slippage_cost"] > 0
    assert metrics["win_rate"] == 0.5
    assert metrics["performance_by_symbol"]["BTCUSDT"]["trade_count"] == 1
    assert metrics["performance_by_symbol"]["ETHUSDT"]["trade_count"] == 1

    event_types = [event["event"] for event in first.payload["events"]]
    assert event_types.count("PLAN_ACCEPTED") == 2
    assert event_types.count("ENTRY_FILLED") == 2
    assert event_types.count("EXIT_FILLED") == 2

