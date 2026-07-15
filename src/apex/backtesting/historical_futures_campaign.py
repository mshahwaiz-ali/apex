"""Deterministic historical futures backtest campaign orchestration.

This module consumes verified N4.7 historical signal artifacts and replays accepted
signals through the existing Phase 8 futures backtester. It deliberately preserves
rejected and failed analysis observations and keeps train, validation, and final-test
results isolated.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from apex.application.historical_signal_io import (
    HistoricalSignalExecutionManifest,
    load_historical_signal_execution_manifest,
    load_historical_signal_record_payloads,
)
from apex.backtesting.contracts import BacktestConfig, BacktestSignal, SimulatedTrade
from apex.backtesting.engine import simulate_trade, summarize_trades
from apex.backtesting.historical_signal_campaign import HistoricalSignalCampaignInputs
from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.domain.models import Candle
from apex.strategies import StrategyType, TradeDirection

HISTORICAL_FUTURES_CAMPAIGN_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class HistoricalFuturesCampaignRequest:
    """Frozen inputs for one deterministic historical futures replay."""

    campaign_id: str
    records_path: Path
    signal_manifest_path: Path
    result_path: Path
    execution_manifest_path: Path
    starting_equity: float
    backtest_config: BacktestConfig = BacktestConfig()

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("historical futures campaign ID cannot be empty")
        if not math.isfinite(self.starting_equity) or self.starting_equity <= 0.0:
            raise ValueError("historical futures starting equity must be positive and finite")
        paths = (
            self.records_path.resolve(strict=False),
            self.signal_manifest_path.resolve(strict=False),
            self.result_path.resolve(strict=False),
            self.execution_manifest_path.resolve(strict=False),
        )
        if len(set(paths)) != len(paths):
            raise ValueError("historical futures campaign paths must be unique")


@dataclass(frozen=True, slots=True)
class HistoricalFuturesObservation:
    """One accepted, rejected, failed, or unconvertible historical observation."""

    symbol: str
    split: HistoricalSignalSplit
    decision_time: str
    status: str
    rejection_codes: tuple[str, ...] = ()
    reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "split": self.split.value,
            "decision_time": self.decision_time,
            "status": self.status,
            "rejection_codes": list(self.rejection_codes),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class HistoricalFuturesTradeResult:
    """Split-aware wrapper around one canonical simulated futures trade."""

    result_id: str
    split: HistoricalSignalSplit
    trade: SimulatedTrade

    def to_payload(self) -> dict[str, object]:
        signal = self.trade.signal
        return {
            "result_id": self.result_id,
            "split": self.split.value,
            "symbol": signal.symbol,
            "strategy": signal.strategy.value,
            "direction": signal.direction.value,
            "decision_time": signal.generated_at.isoformat(),
            "exit_time": self.trade.exit_time.isoformat(),
            "entry_price": signal.entry_price,
            "exit_price": self.trade.exit_price,
            "stop_price": signal.stop_price,
            "target_prices": list(signal.target_prices),
            "quantity": signal.quantity,
            "risk_amount": signal.risk_amount,
            "gross_pnl": self.trade.gross_pnl,
            "fees": self.trade.fees,
            "net_pnl": self.trade.net_pnl,
            "realized_r_multiple": self.trade.realized_r_multiple,
            "holding_candles": self.trade.holding_candles,
            "outcome": self.trade.outcome.value,
            "metadata": dict(self.trade.metadata),
        }


@dataclass(frozen=True, slots=True)
class HistoricalFuturesCampaignResult:
    """Deterministic campaign output with strict split isolation."""

    campaign_id: str
    starting_equity: float
    ending_equity: float
    observations: tuple[HistoricalFuturesObservation, ...]
    trades: tuple[HistoricalFuturesTradeResult, ...]
    split_metrics: tuple[tuple[str, Mapping[str, object]], ...]
    rejection_counts: tuple[tuple[str, int], ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": HISTORICAL_FUTURES_CAMPAIGN_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "net_pnl": self.ending_equity - self.starting_equity,
            "total_decisions": len(self.observations),
            "trade_count": len(self.trades),
            "observations": [item.to_payload() for item in self.observations],
            "trades": [item.to_payload() for item in self.trades],
            "split_metrics": {name: dict(metrics) for name, metrics in self.split_metrics},
            "rejection_counts": dict(self.rejection_counts),
            "warnings": [
                "Historical replay does not establish live edge or funded eligibility.",
                "Final-test results are reported but must not drive calibration.",
            ],
        }


@dataclass(frozen=True, slots=True)
class HistoricalFuturesExecutionManifest:
    """Audit manifest for one persisted historical futures campaign."""

    campaign_id: str
    signal_records_hash: str
    signal_configuration_hash: str
    result_path: str
    result_hash: str
    total_decisions: int
    trade_count: int
    split_counts: tuple[tuple[str, int], ...]
    schema_version: int = HISTORICAL_FUTURES_CAMPAIGN_SCHEMA_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "status": "completed",
            "signal_records_hash": self.signal_records_hash,
            "signal_configuration_hash": self.signal_configuration_hash,
            "result_path": self.result_path,
            "result_hash": self.result_hash,
            "total_decisions": self.total_decisions,
            "trade_count": self.trade_count,
            "split_counts": dict(self.split_counts),
        }


def execute_historical_futures_campaign(
    *,
    request: HistoricalFuturesCampaignRequest,
    inputs: HistoricalSignalCampaignInputs,
) -> HistoricalFuturesCampaignResult:
    """Verify N4.7 artifacts and replay accepted signals without live data calls."""

    manifest = load_historical_signal_execution_manifest(request.signal_manifest_path)
    payloads = load_historical_signal_record_payloads(request.records_path)
    _verify_inputs(request=request, inputs=inputs, manifest=manifest, payloads=payloads)

    observations: list[HistoricalFuturesObservation] = []
    trades: list[HistoricalFuturesTradeResult] = []
    rejection_counter: Counter[str] = Counter()

    for payload in payloads:
        symbol = _required_string(payload, "symbol")
        split = HistoricalSignalSplit(_required_string(payload, "split"))
        decision_time = _required_string(payload, "decision_time")
        analysis = _required_mapping(payload, "analysis")
        accepted = bool(payload.get("accepted", False))
        failure_reason = payload.get("failure_reason")

        if not accepted:
            codes = _string_tuple(analysis.get("rejection_codes"))
            if not codes and failure_reason is not None:
                codes = ("historical_analysis_failure",)
            rejection_counter.update(codes)
            observations.append(
                HistoricalFuturesObservation(
                    symbol=symbol,
                    split=split,
                    decision_time=decision_time,
                    status="failed" if failure_reason is not None else "rejected",
                    rejection_codes=codes,
                    reason=str(failure_reason) if failure_reason is not None else None,
                )
            )
            continue

        try:
            signal = _signal_from_analysis(analysis, decision_time=decision_time)
            future = _future_candles(inputs=inputs, signal=signal)
            if not future:
                raise ValueError("no future closed candles are available for replay")
            simulated = simulate_trade(
                signal,
                future,
                config=request.backtest_config,
                metadata={"split": split.value, "source": "historical_signal_campaign"},
            )
        except (KeyError, TypeError, ValueError) as exc:
            rejection_counter["historical_plan_conversion_failed"] += 1
            observations.append(
                HistoricalFuturesObservation(
                    symbol=symbol,
                    split=split,
                    decision_time=decision_time,
                    status="plan_rejected",
                    rejection_codes=("historical_plan_conversion_failed",),
                    reason=str(exc),
                )
            )
            continue

        observations.append(
            HistoricalFuturesObservation(
                symbol=symbol,
                split=split,
                decision_time=decision_time,
                status="simulated",
            )
        )
        trades.append(
            HistoricalFuturesTradeResult(
                result_id=_trade_result_id(split=split, trade=simulated),
                split=split,
                trade=simulated,
            )
        )

    net_pnl = sum(item.trade.net_pnl for item in trades)
    return HistoricalFuturesCampaignResult(
        campaign_id=request.campaign_id,
        starting_equity=request.starting_equity,
        ending_equity=request.starting_equity + net_pnl,
        observations=tuple(observations),
        trades=tuple(trades),
        split_metrics=_build_split_metrics(trades),
        rejection_counts=tuple(sorted(rejection_counter.items())),
    )


def write_historical_futures_campaign(
    *,
    request: HistoricalFuturesCampaignRequest,
    result: HistoricalFuturesCampaignResult,
) -> HistoricalFuturesExecutionManifest:
    """Atomically persist and reload-verify result and execution manifest."""

    if result.campaign_id != request.campaign_id:
        raise ValueError("historical futures result campaign does not match request")
    for path in (request.result_path, request.execution_manifest_path):
        if path.exists():
            raise FileExistsError(f"historical futures campaign refuses to overwrite: {path}")

    signal_manifest = load_historical_signal_execution_manifest(request.signal_manifest_path)
    result_payload = result.to_payload()
    result_hash = _hash_json(result_payload)
    split_counter = Counter(item.split.value for item in result.observations)
    manifest = HistoricalFuturesExecutionManifest(
        campaign_id=request.campaign_id,
        signal_records_hash=signal_manifest.records_hash,
        signal_configuration_hash=signal_manifest.configuration_hash,
        result_path=request.result_path.as_posix(),
        result_hash=result_hash,
        total_decisions=len(result.observations),
        trade_count=len(result.trades),
        split_counts=tuple(sorted(split_counter.items())),
    )

    created: list[Path] = []
    temporary: list[Path] = []
    try:
        _atomic_json_write(request.result_path, result_payload, created, temporary)
        reloaded_result = json.loads(request.result_path.read_text(encoding="utf-8"))
        if _hash_json(reloaded_result) != result_hash:
            raise ValueError("historical futures result hash changed after reload")
        _atomic_json_write(
            request.execution_manifest_path,
            manifest.to_payload(),
            created,
            temporary,
        )
        reloaded_manifest = load_historical_futures_execution_manifest(
            request.execution_manifest_path
        )
        if reloaded_manifest != manifest:
            raise ValueError("historical futures manifest changed after reload")
        return manifest
    except Exception:
        for path in reversed(created):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            with suppress(OSError):
                path.unlink(missing_ok=True)


def load_historical_futures_execution_manifest(
    path: Path,
) -> HistoricalFuturesExecutionManifest:
    """Load and validate a historical futures execution manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical futures execution manifest must be an object")
    raw_splits = payload.get("split_counts")
    if not isinstance(raw_splits, dict):
        raise ValueError("historical futures split counts must be an object")
    manifest = HistoricalFuturesExecutionManifest(
        schema_version=int(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        signal_records_hash=str(payload["signal_records_hash"]),
        signal_configuration_hash=str(payload["signal_configuration_hash"]),
        result_path=str(payload["result_path"]),
        result_hash=str(payload["result_hash"]),
        total_decisions=int(payload["total_decisions"]),
        trade_count=int(payload["trade_count"]),
        split_counts=tuple(sorted((str(key), int(value)) for key, value in raw_splits.items())),
    )
    if manifest.schema_version != HISTORICAL_FUTURES_CAMPAIGN_SCHEMA_VERSION:
        raise ValueError("unsupported historical futures campaign schema version")
    for digest in (
        manifest.signal_records_hash,
        manifest.signal_configuration_hash,
        manifest.result_hash,
    ):
        if not _is_sha256(digest):
            raise ValueError("historical futures manifest hashes must be SHA-256")
    if manifest.total_decisions < 1 or manifest.trade_count < 0:
        raise ValueError("historical futures manifest counts are invalid")
    if sum(count for _, count in manifest.split_counts) != manifest.total_decisions:
        raise ValueError("historical futures split counts must equal total decisions")
    return manifest


def _verify_inputs(
    *,
    request: HistoricalFuturesCampaignRequest,
    inputs: HistoricalSignalCampaignInputs,
    manifest: HistoricalSignalExecutionManifest,
    payloads: tuple[dict[str, object], ...],
) -> None:
    if request.campaign_id != inputs.campaign_id or request.campaign_id != manifest.campaign_id:
        raise ValueError("historical futures campaign IDs do not match")
    if Path(manifest.records_path).resolve(strict=False) != request.records_path.resolve(strict=False):
        raise ValueError("historical signal manifest does not reference supplied records")
    if _hash_json(payloads) != manifest.records_hash:
        raise ValueError("historical signal record hash mismatch")
    if len(payloads) != manifest.total_records:
        raise ValueError("historical signal record count mismatch")
    source_hashes = {item.content_hash for item in inputs.source_datasets}
    manifest_hashes = {
        str(item["content_hash"])
        for item in manifest.source_datasets
        if "content_hash" in item
    }
    if source_hashes != manifest_hashes:
        raise ValueError("historical signal source dataset hashes do not match inputs")
    keys = tuple(
        (_required_string(item, "decision_time"), _required_string(item, "symbol"))
        for item in payloads
    )
    if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
        raise ValueError("historical signal records must be unique and chronological")


def _signal_from_analysis(
    analysis: Mapping[str, object],
    *,
    decision_time: str,
) -> BacktestSignal:
    direction = TradeDirection(_required_string(analysis, "decision").lower())
    strategy = StrategyType(_required_string(analysis, "strategy"))
    entry = _required_mapping(analysis, "entry_zone")
    position = _required_mapping(analysis, "position_size")
    raw_targets = analysis.get("take_profits")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValueError("accepted historical signal requires take profits")
    targets = tuple(_required_float(_required_mapping(item), "price") for item in raw_targets)
    partials = tuple(100.0 / len(targets) for _ in targets)
    return BacktestSignal(
        symbol=_required_string(analysis, "symbol"),
        strategy=strategy,
        direction=direction,
        generated_at=_parse_datetime(decision_time),
        entry_price=_required_float(entry, "preferred"),
        stop_price=_required_float(analysis, "stop_loss"),
        target_price=targets[0],
        quantity=_required_float(position, "quantity"),
        risk_amount=_required_float(position, "risk_amount"),
        confidence_score=_required_float(analysis, "confidence_score"),
        target_prices=targets,
        partial_close_percentages=partials,
    )


def _future_candles(
    *,
    inputs: HistoricalSignalCampaignInputs,
    signal: BacktestSignal,
) -> tuple[Candle, ...]:
    finest = min(inputs.timeframes, key=_timeframe_seconds)
    return tuple(
        candle
        for candle in inputs.store.candles_for(signal.symbol, finest)
        if candle.open_time >= signal.generated_at and candle.is_closed
    )


def _build_split_metrics(
    trades: list[HistoricalFuturesTradeResult],
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    output: list[tuple[str, Mapping[str, object]]] = []
    for split in HistoricalSignalSplit:
        selected = tuple(item.trade for item in trades if item.split is split)
        report = summarize_trades(selected)
        output.append(
            (
                split.value,
                {
                    "trade_count": report.total_trades,
                    "win_rate": report.win_rate,
                    "loss_rate": report.loss_rate,
                    "breakeven_rate": report.breakeven_rate,
                    "net_profit": report.net_profit,
                    "profit_factor": report.profit_factor,
                    "expectancy": report.expectancy,
                    "average_r": report.average_risk_reward,
                    "maximum_drawdown": report.maximum_drawdown,
                    "consecutive_wins": report.consecutive_wins,
                    "consecutive_losses": report.consecutive_losses,
                },
            )
        )
    return tuple(output)


def _trade_result_id(*, split: HistoricalSignalSplit, trade: SimulatedTrade) -> str:
    return _hash_json(
        {
            "split": split.value,
            "symbol": trade.signal.symbol,
            "decision_time": trade.signal.generated_at.isoformat(),
            "exit_time": trade.exit_time.isoformat(),
            "outcome": trade.outcome.value,
        }
    )


def _atomic_json_write(
    path: Path,
    payload: object,
    created: list[Path],
    temporary: list[Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temporary.append(temp)
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)
    created.append(path)


def _required_mapping(
    value: Mapping[str, object] | object,
    key: str | None = None,
) -> Mapping[str, object]:
    selected = value[key] if key is not None and isinstance(value, Mapping) else value
    if not isinstance(selected, Mapping):
        raise ValueError(f"{key or 'value'} must be an object")
    return selected


def _required_string(value: Mapping[str, object], key: str) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return selected


def _required_float(value: Mapping[str, object], key: str) -> float:
    selected = value.get(key)
    if not isinstance(selected, int | float):
        raise ValueError(f"{key} must be numeric")
    result = float(selected)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{key} must be positive and finite")
    return result


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("historical futures decision time must be timezone-aware")
    return parsed


def _timeframe_seconds(value: str) -> int:
    unit = value[-1]
    amount = int(value[:-1])
    return amount * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
