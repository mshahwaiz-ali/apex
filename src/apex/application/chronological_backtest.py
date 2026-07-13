"""Chronological full-pipeline backtest orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from apex.application.analysis import SymbolAnalysis, analyze_symbol, serialize_symbol_analysis
from apex.application.chronological_metadata import (
    ChronologicalBacktestMetadata,
    build_chronological_metadata,
)
from apex.backtesting import (
    BacktestConfig,
    BacktestReport,
    BacktestSignal,
    SimulatedTrade,
    signal_from_setup,
    simulate_trade,
    summarize_trades,
)
from apex.domain import GainerStateThresholds
from apex.domain.models import Candle, TickerSnapshot
from apex.risk import DEFAULT_RISK_CONFIG, RiskConfig
from apex.risk.contracts import RiskDecision


@dataclass(frozen=True, slots=True)
class ChronologicalBacktestRequest:
    symbol: str
    candles_by_timeframe: Mapping[str, tuple[Candle, ...]]
    analysis_timeframes: tuple[str, ...]
    replay_timeframe: str
    candle_limit: int = 200
    decision_interval_candles: int = 1
    candidate_cooldown_candles: int = 3
    risk_config: RiskConfig = field(default_factory=lambda: DEFAULT_RISK_CONFIG)
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)
    strategy_routing: Mapping[str, Sequence[str]] | None = None
    gainer_state_thresholds: GainerStateThresholds | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("chronological backtest symbol cannot be empty")
        if self.candle_limit < 40:
            raise ValueError("chronological backtest requires at least 40 candles")
        if self.decision_interval_candles < 1:
            raise ValueError("decision interval candles must be positive")
        if self.candidate_cooldown_candles < 0:
            raise ValueError("candidate cooldown candles cannot be negative")
        if self.replay_timeframe not in self.candles_by_timeframe:
            raise ValueError("replay timeframe candles are required")
        missing = set(self.analysis_timeframes).difference(self.candles_by_timeframe)
        if missing:
            raise ValueError(f"analysis timeframe candles are missing: {sorted(missing)}")
        normalized = {
            timeframe: tuple(sorted(candles, key=lambda candle: candle.open_time))
            for timeframe, candles in self.candles_by_timeframe.items()
        }
        object.__setattr__(self, "candles_by_timeframe", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class ChronologicalBacktestResult:
    report: BacktestReport
    trades: tuple[SimulatedTrade, ...]
    metadata: ChronologicalBacktestMetadata
    decision_count: int
    approved_count: int
    skipped_count: int
    cooldown_skipped_count: int
    overlap_skipped_count: int
    failure_count: int
    failures: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.report.total_trades != len(self.trades):
            raise ValueError("report trade count must match chronological trades")
        if self.approved_count != len(self.trades):
            raise ValueError("approved count must match simulated trades")
        names = (
            "decision_count",
            "approved_count",
            "skipped_count",
            "cooldown_skipped_count",
            "overlap_skipped_count",
            "failure_count",
        )
        if any(getattr(self, name) < 0 for name in names):
            raise ValueError("chronological counts cannot be negative")
        if self.failure_count != len(self.failures):
            raise ValueError("failure count must match failure details")
        object.__setattr__(self, "failures", MappingProxyType(dict(self.failures)))


def run_chronological_pipeline_backtest(
    request: ChronologicalBacktestRequest,
) -> ChronologicalBacktestResult:
    """Run the full analysis/scoring/risk pipeline at historical decision times."""

    replay = tuple(
        candle
        for candle in request.candles_by_timeframe[request.replay_timeframe]
        if candle.is_closed
    )
    trades: list[SimulatedTrade] = []
    failures: dict[str, str] = {}
    last_fingerprint: tuple[str, str, str] | None = None
    last_accepted_index: int | None = None
    decision_count = skipped_count = cooldown_skipped_count = overlap_skipped_count = 0

    indexes = range(request.candle_limit, len(replay), request.decision_interval_candles)
    for decision_index in indexes:
        decision_time = replay[decision_index - 1].close_time
        provider = _HistoricalPrefixProvider(request.candles_by_timeframe, decision_time)
        decision_count += 1
        if not _has_required_warmup(
            provider, request.symbol, request.analysis_timeframes, request.candle_limit
        ):
            skipped_count += 1
            continue
        try:
            analysis = analyze_symbol(
                request.symbol,
                provider,
                timeframes=request.analysis_timeframes,
                candle_limit=request.candle_limit,
                risk_config=request.risk_config,
                generated_at=decision_time,
                strategy_routing=request.strategy_routing,
                gainer_state_thresholds=request.gainer_state_thresholds,
            )
        except Exception as exc:
            failures[decision_time.isoformat()] = str(exc)
            continue
        if analysis.assessment.decision is not RiskDecision.APPROVED:
            skipped_count += 1
            continue
        if analysis.assessment.setup is None:
            failures[decision_time.isoformat()] = "approved assessment is missing setup"
            continue

        signal = signal_from_setup(analysis.assessment.setup)
        fingerprint = _signal_fingerprint(signal)
        if _is_overlapping(trades, decision_time):
            overlap_skipped_count += 1
            continue
        if _is_in_cooldown(
            fingerprint,
            last_fingerprint,
            decision_index,
            last_accepted_index,
            request.candidate_cooldown_candles,
        ):
            cooldown_skipped_count += 1
            continue

        future = tuple(
            candle for candle in replay[decision_index:] if candle.open_time >= decision_time
        )
        if not future:
            skipped_count += 1
            continue
        trades.append(
            simulate_trade(
                signal,
                future,
                config=request.backtest_config,
                metadata=_backtest_trade_metadata(analysis),
            )
        )
        last_fingerprint = fingerprint
        last_accepted_index = decision_index

    trade_tuple = tuple(trades)
    metadata = build_chronological_metadata(
        symbol=request.symbol,
        candles_by_timeframe=request.candles_by_timeframe,
        analysis_timeframes=request.analysis_timeframes,
        replay_timeframe=request.replay_timeframe,
        candle_limit=request.candle_limit,
        decision_interval_candles=request.decision_interval_candles,
        candidate_cooldown_candles=request.candidate_cooldown_candles,
        risk_config=request.risk_config,
        backtest_config=request.backtest_config,
    )
    return ChronologicalBacktestResult(
        report=summarize_trades(trade_tuple),
        trades=trade_tuple,
        metadata=metadata,
        decision_count=decision_count,
        approved_count=len(trade_tuple),
        skipped_count=skipped_count,
        cooldown_skipped_count=cooldown_skipped_count,
        overlap_skipped_count=overlap_skipped_count,
        failure_count=len(failures),
        failures=failures,
    )


def _signal_fingerprint(signal: BacktestSignal) -> tuple[str, str, str]:
    return signal.symbol, signal.strategy.value, signal.direction.value


def _backtest_trade_metadata(analysis: SymbolAnalysis) -> dict[str, str | int | float | bool]:
    payload = serialize_symbol_analysis(analysis)
    metadata: dict[str, str | int | float | bool] = {
        "configuration_id": str(payload.get("configuration_id", "")),
        "scanner_type": str(payload.get("scanner_type", "")),
        "entry_state": str(payload.get("entry_state", "")),
    }
    precision = payload.get("precision_entry")
    if isinstance(precision, dict):
        score = precision.get("score")
        if isinstance(score, dict) and isinstance(score.get("final_score"), int | float):
            metadata["precision_entry_score"] = float(score["final_score"])
    return metadata


def _is_overlapping(trades: Sequence[SimulatedTrade], decision_time: datetime) -> bool:
    return bool(trades and trades[-1].exit_time > decision_time)


def _is_in_cooldown(
    fingerprint: tuple[str, str, str],
    previous: tuple[str, str, str] | None,
    decision_index: int,
    previous_index: int | None,
    cooldown: int,
) -> bool:
    return (
        cooldown > 0
        and fingerprint == previous
        and previous_index is not None
        and decision_index - previous_index <= cooldown
    )


def _has_required_warmup(
    provider: _HistoricalPrefixProvider,
    symbol: str,
    timeframes: Sequence[str],
    candle_limit: int,
) -> bool:
    return all(
        len(provider.fetch_candles(symbol, timeframe, limit=candle_limit)) >= candle_limit
        for timeframe in timeframes
    )


class _HistoricalPrefixProvider:
    def __init__(
        self,
        candles_by_timeframe: Mapping[str, Sequence[Candle]],
        decision_time: datetime,
    ) -> None:
        self._candles_by_timeframe = candles_by_timeframe
        self._decision_time = decision_time

    @property
    def name(self) -> str:
        return "historical-prefix"

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        available = tuple(
            candle
            for candle in self._candles_by_timeframe[timeframe]
            if candle.symbol == symbol
            and candle.is_closed
            and candle.close_time <= self._decision_time
        )
        return list(available[-limit:])

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        available = tuple(
            candle
            for candles in self._candles_by_timeframe.values()
            for candle in candles
            if candle.symbol == symbol
            and candle.is_closed
            and candle.close_time <= self._decision_time
        )
        if not available:
            raise ValueError(f"no historical price is available for {symbol}")
        latest = max(available, key=lambda candle: candle.close_time)
        return TickerSnapshot(
            symbol=symbol,
            last_price=latest.close,
            bid_price=latest.close,
            ask_price=latest.close,
            quote_volume_24h=0.0,
            captured_at=self._decision_time,
            source="historical-closed-candle",
        )
