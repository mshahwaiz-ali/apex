"""Chronological full-pipeline backtest orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from apex.application.analysis import analyze_symbol
from apex.backtesting import (
    BacktestConfig,
    BacktestReport,
    SimulatedTrade,
    signal_from_setup,
    simulate_trade,
    summarize_trades,
)
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
    risk_config: RiskConfig = field(default_factory=lambda: DEFAULT_RISK_CONFIG)
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("chronological backtest symbol cannot be empty")
        if self.candle_limit < 40:
            raise ValueError("chronological backtest requires at least 40 candles")
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
    decision_count: int
    approved_count: int
    skipped_count: int
    failure_count: int
    failures: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.report.total_trades != len(self.trades):
            raise ValueError("report trade count must match chronological trades")
        if self.approved_count != len(self.trades):
            raise ValueError("approved count must match simulated trades")
        for name in ("decision_count", "approved_count", "skipped_count", "failure_count"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.failure_count != len(self.failures):
            raise ValueError("failure count must match failure details")
        object.__setattr__(self, "failures", MappingProxyType(dict(self.failures)))


def run_chronological_pipeline_backtest(
    request: ChronologicalBacktestRequest,
) -> ChronologicalBacktestResult:
    """Run the full analysis/scoring/risk pipeline at historical decision times."""

    replay_candles = tuple(
        candle
        for candle in request.candles_by_timeframe[request.replay_timeframe]
        if candle.is_closed
    )
    trades: list[SimulatedTrade] = []
    failures: dict[str, str] = {}
    decision_count = 0
    skipped_count = 0

    for decision_index in range(request.candle_limit, len(replay_candles)):
        decision_candle = replay_candles[decision_index - 1]
        decision_time = decision_candle.close_time
        provider = _HistoricalPrefixProvider(request.candles_by_timeframe, decision_time)
        decision_count += 1

        if not _has_required_warmup(
            provider,
            request.symbol,
            request.analysis_timeframes,
            request.candle_limit,
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

        future = tuple(
            candle
            for candle in replay_candles[decision_index:]
            if candle.open_time >= decision_time
        )
        if not future:
            skipped_count += 1
            continue
        signal = signal_from_setup(analysis.assessment.setup)
        trades.append(simulate_trade(signal, future, config=request.backtest_config))

    trade_tuple = tuple(trades)
    return ChronologicalBacktestResult(
        report=summarize_trades(trade_tuple),
        trades=trade_tuple,
        decision_count=decision_count,
        approved_count=len(trade_tuple),
        skipped_count=skipped_count,
        failure_count=len(failures),
        failures=failures,
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
        candles = self._candles_by_timeframe[timeframe]
        available = tuple(
            candle
            for candle in candles
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
