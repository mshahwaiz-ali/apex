"""Multi-variant chronological backtest campaign orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from apex.application.backtest_report_io import make_run_id, to_json_value
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    ChronologicalBacktestResult,
    run_chronological_pipeline_backtest,
)
from apex.application.symbols import normalize_market_symbol
from apex.backtesting import BacktestConfig
from apex.domain.models import Candle
from apex.risk import DEFAULT_RISK_CONFIG, RiskConfig

BACKTEST_CAMPAIGN_SCHEMA_VERSION = 1

ChronologicalRunner = Callable[[ChronologicalBacktestRequest], ChronologicalBacktestResult]


@dataclass(frozen=True, slots=True)
class BacktestCampaignVariant:
    """One deterministic chronological backtest parameter variant."""

    identifier: str
    replay_timeframe: str = "5m"
    candle_limit: int = 200
    decision_interval_candles: int = 1
    candidate_cooldown_candles: int = 3
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("campaign variant identifier cannot be empty")
        if not self.replay_timeframe.strip():
            raise ValueError("campaign variant replay timeframe cannot be empty")
        if self.candle_limit < 40:
            raise ValueError("campaign variant candle limit must be at least 40")
        if self.decision_interval_candles < 1:
            raise ValueError("campaign variant decision interval must be positive")
        if self.candidate_cooldown_candles < 0:
            raise ValueError("campaign variant cooldown cannot be negative")


@dataclass(frozen=True, slots=True)
class BacktestCampaignRequest:
    """Provider-independent request for a multi-variant chronological campaign."""

    symbol: str
    candles_by_timeframe: Mapping[str, tuple[Candle, ...]]
    analysis_timeframes: tuple[str, ...]
    variants: tuple[BacktestCampaignVariant, ...]
    dataset_source: str = "local"
    risk_config: RiskConfig = field(default_factory=lambda: DEFAULT_RISK_CONFIG)
    strategy_routing: Mapping[str, Sequence[str]] | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("campaign symbol cannot be empty")
        if not self.dataset_source.strip():
            raise ValueError("campaign dataset source cannot be empty")
        if not self.variants:
            raise ValueError("campaign requires at least one variant")
        identifiers = tuple(variant.identifier for variant in self.variants)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("campaign variant identifiers must be unique")
        required_timeframes = set(self.analysis_timeframes)
        required_timeframes.update(variant.replay_timeframe for variant in self.variants)
        missing = required_timeframes.difference(self.candles_by_timeframe)
        if missing:
            raise ValueError(f"campaign candles are missing: {sorted(missing)}")
        normalized = {
            timeframe: tuple(sorted(candles, key=lambda candle: candle.open_time))
            for timeframe, candles in self.candles_by_timeframe.items()
        }
        object.__setattr__(self, "candles_by_timeframe", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class MultiSymbolBacktestCampaignRequest:
    """Provider-independent request for a curated multi-symbol campaign."""

    symbols: tuple[str, ...]
    candles_by_symbol: Mapping[str, Mapping[str, tuple[Candle, ...]]]
    analysis_timeframes: tuple[str, ...]
    variants: tuple[BacktestCampaignVariant, ...]
    dataset_source: str = "local"
    risk_config: RiskConfig = field(default_factory=lambda: DEFAULT_RISK_CONFIG)
    strategy_routing: Mapping[str, Sequence[str]] | None = None

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValueError("multi-symbol campaign requires at least one symbol")
        symbols = tuple(normalize_market_symbol(symbol) for symbol in self.symbols)
        if len(set(symbols)) != len(symbols):
            raise ValueError("multi-symbol campaign symbols must be unique")
        if not self.dataset_source.strip():
            raise ValueError("campaign dataset source cannot be empty")
        if not self.variants:
            raise ValueError("campaign requires at least one variant")
        identifiers = tuple(variant.identifier for variant in self.variants)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("campaign variant identifiers must be unique")

        required_timeframes = set(self.analysis_timeframes)
        required_timeframes.update(variant.replay_timeframe for variant in self.variants)
        normalized: dict[str, Mapping[str, tuple[Candle, ...]]] = {}
        for symbol in symbols:
            if symbol not in self.candles_by_symbol:
                raise ValueError(f"campaign candles are missing for symbol {symbol}")
            candles_by_timeframe = self.candles_by_symbol[symbol]
            missing = required_timeframes.difference(candles_by_timeframe)
            if missing:
                raise ValueError(f"campaign candles are missing for {symbol}: {sorted(missing)}")
            normalized[symbol] = MappingProxyType(
                {
                    timeframe: tuple(sorted(candles, key=lambda candle: candle.open_time))
                    for timeframe, candles in candles_by_timeframe.items()
                }
            )
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "candles_by_symbol", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class BacktestCampaignRun:
    """One completed variant inside a chronological campaign."""

    variant: BacktestCampaignVariant
    run_id: str
    result: ChronologicalBacktestResult
    symbol: str = ""

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("campaign variant run id cannot be empty")
        if self.symbol is not None and not self.symbol.strip():
            object.__setattr__(self, "symbol", self.result.metadata.symbol)


@dataclass(frozen=True, slots=True)
class BacktestCampaignResult:
    """Deterministic multi-variant campaign result."""

    campaign_id: str
    symbol: str
    dataset_source: str
    generated_at: datetime
    runs: tuple[BacktestCampaignRun, ...]
    best_variant_id: str | None
    best_symbol: str | None = None

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("campaign id cannot be empty")
        if not self.symbol.strip() or not self.dataset_source.strip():
            raise ValueError("campaign result symbol and dataset source are required")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("campaign generated_at must be timezone-aware")
        if not self.runs:
            raise ValueError("campaign result requires at least one run")
        if self.best_variant_id is not None and self.best_variant_id not in {
            run.variant.identifier for run in self.runs
        }:
            raise ValueError("best variant id must refer to a campaign run")
        if self.best_symbol is not None and self.best_symbol not in {
            run.symbol for run in self.runs
        }:
            raise ValueError("best symbol must refer to a campaign run")


def default_campaign_variants() -> tuple[BacktestCampaignVariant, ...]:
    """Return a compact default campaign suitable for local validation."""

    return (
        BacktestCampaignVariant(identifier="baseline"),
        BacktestCampaignVariant(
            identifier="fast-decisions",
            replay_timeframe="5m",
            candle_limit=120,
            decision_interval_candles=1,
            candidate_cooldown_candles=1,
        ),
        BacktestCampaignVariant(
            identifier="slower-decisions",
            replay_timeframe="5m",
            candle_limit=200,
            decision_interval_candles=3,
            candidate_cooldown_candles=3,
        ),
    )


def run_backtest_campaign(
    request: BacktestCampaignRequest,
    *,
    generated_at: datetime | None = None,
    runner: ChronologicalRunner = run_chronological_pipeline_backtest,
) -> BacktestCampaignResult:
    """Run each campaign variant through the production chronological pipeline."""

    runs: list[BacktestCampaignRun] = []
    for variant in request.variants:
        variant_request = ChronologicalBacktestRequest(
            symbol=request.symbol,
            candles_by_timeframe=request.candles_by_timeframe,
            analysis_timeframes=request.analysis_timeframes,
            replay_timeframe=variant.replay_timeframe,
            candle_limit=variant.candle_limit,
            decision_interval_candles=variant.decision_interval_candles,
            candidate_cooldown_candles=variant.candidate_cooldown_candles,
            risk_config=request.risk_config,
            backtest_config=variant.backtest_config,
            strategy_routing=request.strategy_routing,
        )
        result = runner(variant_request)
        runs.append(
            BacktestCampaignRun(
                variant=variant,
                run_id=make_run_id(
                    symbol=request.symbol,
                    replay_timeframe=variant.replay_timeframe,
                    dataset_hash=result.metadata.dataset_hash,
                    config_hash=result.metadata.config_hash,
                ),
                result=result,
                symbol=request.symbol,
            )
        )
    run_tuple = tuple(runs)
    campaign_id = _campaign_id(request.symbol, request.dataset_source, run_tuple)
    best = _rank_campaign_runs(run_tuple)[0]
    return BacktestCampaignResult(
        campaign_id=campaign_id,
        symbol=request.symbol,
        dataset_source=request.dataset_source,
        generated_at=generated_at or datetime.now(UTC),
        runs=run_tuple,
        best_variant_id=best.variant.identifier,
        best_symbol=best.symbol,
    )


def run_multi_symbol_backtest_campaign(
    request: MultiSymbolBacktestCampaignRequest,
    *,
    generated_at: datetime | None = None,
    runner: ChronologicalRunner = run_chronological_pipeline_backtest,
) -> BacktestCampaignResult:
    """Run every symbol and variant through the production chronological pipeline."""

    runs: list[BacktestCampaignRun] = []
    for symbol in request.symbols:
        for variant in request.variants:
            variant_request = ChronologicalBacktestRequest(
                symbol=symbol,
                candles_by_timeframe=request.candles_by_symbol[symbol],
                analysis_timeframes=request.analysis_timeframes,
                replay_timeframe=variant.replay_timeframe,
                candle_limit=variant.candle_limit,
                decision_interval_candles=variant.decision_interval_candles,
                candidate_cooldown_candles=variant.candidate_cooldown_candles,
                risk_config=request.risk_config,
                backtest_config=variant.backtest_config,
                strategy_routing=request.strategy_routing,
            )
            result = runner(variant_request)
            runs.append(
                BacktestCampaignRun(
                    variant=variant,
                    run_id=make_run_id(
                        symbol=symbol,
                        replay_timeframe=variant.replay_timeframe,
                        dataset_hash=result.metadata.dataset_hash,
                        config_hash=result.metadata.config_hash,
                    ),
                    result=result,
                    symbol=symbol,
                )
            )
    run_tuple = tuple(runs)
    best = _rank_campaign_runs(run_tuple)[0]
    return BacktestCampaignResult(
        campaign_id=_campaign_id("MULTI", request.dataset_source, run_tuple),
        symbol="MULTI",
        dataset_source=request.dataset_source,
        generated_at=generated_at or datetime.now(UTC),
        runs=run_tuple,
        best_variant_id=best.variant.identifier,
        best_symbol=best.symbol,
    )


def campaign_result_to_payload(result: BacktestCampaignResult) -> dict[str, Any]:
    """Serialize a campaign result with complete per-variant report payloads."""

    rankings = [
        {
            "rank": index,
            "symbol": run.symbol,
            "variant_id": run.variant.identifier,
            "run_id": run.run_id,
            "total_trades": run.result.report.total_trades,
            "net_profit": run.result.report.net_profit,
            "expectancy": run.result.report.expectancy,
            "maximum_drawdown": run.result.report.maximum_drawdown,
            "failure_count": run.result.failure_count,
        }
        for index, run in enumerate(_rank_campaign_runs(result.runs), start=1)
    ]
    return {
        "schema_version": BACKTEST_CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": result.campaign_id,
        "symbol": result.symbol,
        "dataset_source": result.dataset_source,
        "generated_at": result.generated_at.isoformat(),
        "variant_count": len(result.runs),
        "symbol_count": len({run.symbol for run in result.runs}),
        "best_variant_id": result.best_variant_id,
        "best_symbol": result.best_symbol,
        "rankings": rankings,
        "variants": [_campaign_run_payload(run) for run in result.runs],
    }


def parse_campaign_variants(specification: str | None) -> tuple[BacktestCampaignVariant, ...]:
    """Parse CLI campaign variants from id:timeframe:candles:interval:cooldown entries."""

    if specification is None or not specification.strip():
        return default_campaign_variants()
    variants: list[BacktestCampaignVariant] = []
    for raw_item in specification.split(","):
        item = raw_item.strip()
        if not item:
            continue
        parts = tuple(part.strip() for part in item.split(":"))
        if len(parts) != 5:
            raise ValueError("campaign variants must use id:timeframe:candles:interval:cooldown")
        identifier, replay_timeframe, candle_limit, interval, cooldown = parts
        variants.append(
            BacktestCampaignVariant(
                identifier=identifier,
                replay_timeframe=replay_timeframe,
                candle_limit=int(candle_limit),
                decision_interval_candles=int(interval),
                candidate_cooldown_candles=int(cooldown),
            )
        )
    return tuple(variants)


def split_campaign_candles_by_symbol(
    candles_by_timeframe: Mapping[str, Sequence[Candle]],
    symbols: Sequence[str],
) -> Mapping[str, Mapping[str, tuple[Candle, ...]]]:
    """Split timeframe-grouped historical candles into symbol-specific groups."""

    normalized_symbols = tuple(normalize_market_symbol(symbol) for symbol in symbols)
    if len(set(normalized_symbols)) != len(normalized_symbols):
        raise ValueError("campaign symbols must be unique")
    split: dict[str, dict[str, tuple[Candle, ...]]] = {}
    for symbol in normalized_symbols:
        split[symbol] = {}
        for timeframe, candles in candles_by_timeframe.items():
            matching = tuple(
                candle for candle in candles if normalize_market_symbol(candle.symbol) == symbol
            )
            if matching:
                split[symbol][timeframe] = matching
    return MappingProxyType(
        {symbol: MappingProxyType(timeframes) for symbol, timeframes in split.items()}
    )


def _campaign_run_payload(run: BacktestCampaignRun) -> dict[str, Any]:
    return {
        "symbol": run.symbol,
        "variant": to_json_value(run.variant),
        "run_id": run.run_id,
        "metadata": to_json_value(run.result.metadata),
        "decision_count": run.result.decision_count,
        "approved_count": run.result.approved_count,
        "skipped_count": run.result.skipped_count,
        "cooldown_skipped_count": run.result.cooldown_skipped_count,
        "overlap_skipped_count": run.result.overlap_skipped_count,
        "failure_count": run.result.failure_count,
        "failures": dict(run.result.failures),
        "metrics": to_json_value(run.result.report),
        "trades": to_json_value(run.result.trades),
    }


def _rank_campaign_runs(runs: Sequence[BacktestCampaignRun]) -> tuple[BacktestCampaignRun, ...]:
    return tuple(
        sorted(
            runs,
            key=lambda run: (
                -run.result.report.net_profit,
                -run.result.report.expectancy,
                run.result.report.maximum_drawdown,
                -run.result.report.total_trades,
                run.variant.identifier,
            ),
        )
    )


def _campaign_id(
    symbol: str,
    dataset_source: str,
    runs: Sequence[BacktestCampaignRun],
) -> str:
    digest = hashlib.sha256()
    digest.update(symbol.encode("utf-8"))
    digest.update(b"\0")
    digest.update(dataset_source.encode("utf-8"))
    for run in runs:
        digest.update(b"\0")
        digest.update(run.symbol.encode("utf-8"))
        digest.update(b"\0")
        digest.update(run.variant.identifier.encode("utf-8"))
        digest.update(b"\0")
        digest.update(run.run_id.encode("utf-8"))
    slug = symbol.lower().replace("/", "-").replace("_", "-")
    return f"{slug}-campaign-{digest.hexdigest()[:16]}"
