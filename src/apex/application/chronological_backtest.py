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
from apex.application.futures_risk_mode import current_futures_risk_mode
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
    strategy_routing: Mapping[str, Sequence[str]] | None = None

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
    candidate_count_distribution: Mapping[str, int]
    rejection_code_counts: Mapping[str, int]
    rejection_reason_counts: Mapping[str, int]
    skipped_by_stage: Mapping[str, int]
    phase5_outcome_counts: Mapping[str, int]
    phase5_reason_counts: Mapping[str, int]
    phase5_strategy_counts: Mapping[str, int]
    phase5_score_bands: Mapping[str, int]
    risk_rejection_diagnostics: tuple[Mapping[str, object], ...]

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
        diagnostic_maps = (
            self.candidate_count_distribution,
            self.rejection_code_counts,
            self.rejection_reason_counts,
            self.skipped_by_stage,
            self.phase5_outcome_counts,
            self.phase5_reason_counts,
            self.phase5_strategy_counts,
            self.phase5_score_bands,
        )
        if any(value < 0 for mapping in diagnostic_maps for value in mapping.values()):
            raise ValueError("chronological diagnostic counts cannot be negative")
        object.__setattr__(self, "failures", MappingProxyType(dict(self.failures)))
        object.__setattr__(
            self,
            "candidate_count_distribution",
            MappingProxyType(dict(self.candidate_count_distribution)),
        )
        object.__setattr__(
            self,
            "rejection_code_counts",
            MappingProxyType(dict(self.rejection_code_counts)),
        )
        object.__setattr__(
            self,
            "rejection_reason_counts",
            MappingProxyType(dict(self.rejection_reason_counts)),
        )
        object.__setattr__(
            self,
            "skipped_by_stage",
            MappingProxyType(dict(self.skipped_by_stage)),
        )
        object.__setattr__(
            self,
            "phase5_outcome_counts",
            MappingProxyType(dict(self.phase5_outcome_counts)),
        )
        object.__setattr__(
            self,
            "phase5_reason_counts",
            MappingProxyType(dict(self.phase5_reason_counts)),
        )
        object.__setattr__(
            self,
            "phase5_strategy_counts",
            MappingProxyType(dict(self.phase5_strategy_counts)),
        )
        object.__setattr__(
            self,
            "phase5_score_bands",
            MappingProxyType(dict(self.phase5_score_bands)),
        )
        object.__setattr__(
            self,
            "risk_rejection_diagnostics",
            tuple(MappingProxyType(dict(item)) for item in self.risk_rejection_diagnostics),
        )


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
    candidate_count_distribution = {"0": 0, "1": 0, "2_plus": 0}
    rejection_code_counts: dict[str, int] = {}
    rejection_reason_counts: dict[str, int] = {}
    phase5_outcome_counts: dict[str, int] = {}
    phase5_reason_counts: dict[str, int] = {}
    phase5_strategy_counts: dict[str, int] = {}
    phase5_score_bands = {
        "below_40": 0,
        "40_to_49_99": 0,
        "50_to_59_99": 0,
        "60_to_69_99": 0,
        "70_plus": 0,
    }
    risk_rejection_diagnostics: list[Mapping[str, object]] = []
    skipped_by_stage = {
        "insufficient_warmup": 0,
        "no_candidates": 0,
        "risk_rejected": 0,
        "cooldown": 0,
        "overlap": 0,
        "no_future_candles": 0,
    }
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
            skipped_by_stage["insufficient_warmup"] += 1
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
            )
        except Exception as exc:
            failures[decision_time.isoformat()] = str(exc)
            continue

        candidate_bucket = (
            "0"
            if analysis.candidate_count == 0
            else "1"
            if analysis.candidate_count == 1
            else "2_plus"
        )
        candidate_count_distribution[candidate_bucket] += 1

        phase5 = dict(analysis.phase5_diagnostics or {})
        candidates = phase5.get("candidates", [])
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue

                outcome = candidate.get("outcome")
                if isinstance(outcome, str) and outcome:
                    phase5_outcome_counts[outcome] = phase5_outcome_counts.get(outcome, 0) + 1

                strategy = candidate.get("strategy")
                if isinstance(strategy, str) and strategy:
                    phase5_strategy_counts[strategy] = phase5_strategy_counts.get(strategy, 0) + 1

                reasons = candidate.get("reasons", [])
                if isinstance(reasons, list):
                    for reason in reasons:
                        if isinstance(reason, str) and reason:
                            phase5_reason_counts[reason] = phase5_reason_counts.get(reason, 0) + 1

                score = candidate.get("final_score")
                if isinstance(score, int | float):
                    if score < 40.0:
                        score_band = "below_40"
                    elif score < 50.0:
                        score_band = "40_to_49_99"
                    elif score < 60.0:
                        score_band = "50_to_59_99"
                    elif score < 70.0:
                        score_band = "60_to_69_99"
                    else:
                        score_band = "70_plus"
                    phase5_score_bands[score_band] += 1

        if analysis.assessment.decision is not RiskDecision.APPROVED:
            skipped_count += 1
            skipped_by_stage["risk_rejected"] += 1
            if analysis.candidate_count == 0:
                skipped_by_stage["no_candidates"] += 1
            for code in analysis.assessment.rejection_codes:
                rejection_code_counts[code.value] = rejection_code_counts.get(code.value, 0) + 1
            for reason in analysis.assessment.reasons:
                rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
            risk_rejection_diagnostics.extend(analysis.risk_rejection_diagnostics)
            continue
        if analysis.assessment.setup is None:
            failures[decision_time.isoformat()] = "approved assessment is missing setup"
            continue

        signal = signal_from_setup(
            analysis.assessment.setup,
            config=request.backtest_config,
        )
        fingerprint = _signal_fingerprint(signal)
        if _is_overlapping(trades, decision_time):
            overlap_skipped_count += 1
            skipped_by_stage["overlap"] += 1
            continue
        if _is_in_cooldown(
            fingerprint,
            last_fingerprint,
            decision_index,
            last_accepted_index,
            request.candidate_cooldown_candles,
        ):
            cooldown_skipped_count += 1
            skipped_by_stage["cooldown"] += 1
            continue

        future = tuple(
            candle for candle in replay[decision_index:] if candle.open_time >= decision_time
        )
        if not future:
            skipped_count += 1
            skipped_by_stage["no_future_candles"] += 1
            continue
        trades.append(
            simulate_trade(
                signal,
                future,
                config=request.backtest_config,
                metadata=_backtest_trade_metadata(
                    analysis,
                    request,
                    signal,
                ),
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
        candidate_count_distribution=candidate_count_distribution,
        rejection_code_counts=rejection_code_counts,
        rejection_reason_counts=rejection_reason_counts,
        skipped_by_stage=skipped_by_stage,
        phase5_outcome_counts=phase5_outcome_counts,
        phase5_reason_counts=phase5_reason_counts,
        phase5_strategy_counts=phase5_strategy_counts,
        phase5_score_bands=phase5_score_bands,
        risk_rejection_diagnostics=tuple(risk_rejection_diagnostics),
    )


def _signal_fingerprint(signal: BacktestSignal) -> tuple[str, str, str]:
    return signal.symbol, signal.strategy.value, signal.direction.value


def _backtest_trade_metadata(
    analysis: SymbolAnalysis,
    request: ChronologicalBacktestRequest,
    signal: BacktestSignal,
) -> dict[str, str | int | float | bool]:
    payload = serialize_symbol_analysis(analysis)
    metadata: dict[str, str | int | float | bool] = {
        "configuration_id": str(payload.get("configuration_id", "")),
        "active_risk_configuration_id": analysis.assessment.configuration_id,
        "active_risk_mode": current_futures_risk_mode().value,
        "scanner_type": str(payload.get("scanner_type", "")),
        "entry_state": str(payload.get("entry_state", "")),
        "configured_account_equity": request.risk_config.account_equity,
        "configured_account_loss_pct": request.risk_config.risk_per_trade_pct,
    }

    setup = analysis.assessment.setup
    if setup is not None:
        position_notional = signal.quantity * signal.entry_price
        minimum_funding_leverage = max(
            1.0,
            position_notional / request.risk_config.account_equity,
        )
        required_margin = position_notional / minimum_funding_leverage

        metadata.update(
            {
                "configured_wallet_loss_cap": signal.risk_amount,
                "position_quantity": signal.quantity,
                "position_notional": position_notional,
                "required_margin": required_margin,
                "leverage_used": minimum_funding_leverage,
                "leverage_used_model": "minimum_funding_leverage",
                "legacy_phase6_quantity": setup.position_size.quantity,
                "legacy_phase6_position_notional": setup.position_size.notional_value,
                "phase6_minimum_leverage": setup.leverage.minimum,
                "phase6_maximum_leverage": setup.leverage.maximum,
                "phase6_modeled_maximum_leverage": setup.leverage.modeled_maximum,
            }
        )

    precision = payload.get("precision_entry")
    if isinstance(precision, dict):
        score = precision.get("score")
        if isinstance(score, dict) and isinstance(
            score.get("final_score"),
            int | float,
        ):
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
