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
    BacktestSignal,
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
    decision_interval_candles: int = 1
    candidate_cooldown_candles: int = 3
    risk_config: RiskConfig = field(default_factory=lambda: DEFAULT_RISK_CONFIG)
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("chronological backtest symbol cannot be empty")
        if self.candle_limit < 40:
            raise ValueError("chronological backtest requires