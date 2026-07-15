"""Deterministic multi-symbol live spot scanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.spot_analysis import SpotAnalysisResult, spot_analysis_result_to_payload
from apex.application.spot_live import SpotLiveAccountInput, analyze_live_spot
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.data.providers.base import MarketDataProvider

SPOT_LIVE_SCAN_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SpotLiveScanItem:
    symbol: str
    result: SpotAnalysisResult


@dataclass(frozen=True, slots=True)
class SpotLiveScanFailure:
    symbol: str
    error: str


@dataclass(frozen=True, slots=True)
class SpotLiveScanResult:
    ranked: tuple[SpotLiveScanItem, ...]
    failures: tuple[SpotLiveScanFailure, ...]


def scan_live_spot(
    *,
    symbols: tuple[str, ...],
    account_input: SpotLiveAccountInput,
    candle_provider: MarketDataProvider,
    ticker_provider: MarketDataProvider,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
    candle_limit: int = 200,
) -> SpotLiveScanResult:
    normalized = tuple(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    if not normalized:
        raise ValueError("spot live scan requires at least one symbol")

    items: list[SpotLiveScanItem] = []
    failures: list[SpotLiveScanFailure] = []
    for symbol in normalized:
        try:
            result = analyze_live_spot(
                symbol=symbol,
                account_input=account_input,
                candle_provider=candle_provider,
                ticker_provider=ticker_provider,
                product_config=product_config,
                strategy_config=strategy_config,
                candle_limit=candle_limit,
            )
        except (OSError, TypeError, ValueError) as exc:
            failures.append(SpotLiveScanFailure(symbol=symbol, error=str(exc)))
            continue
        items.append(SpotLiveScanItem(symbol=symbol, result=result))

    items.sort(key=_rank_key)
    failures.sort(key=lambda item: item.symbol)
    return SpotLiveScanResult(ranked=tuple(items), failures=tuple(failures))


def spot_live_scan_result_to_payload(result: SpotLiveScanResult) -> dict[str, Any]:
    return {
        "schema_version": SPOT_LIVE_SCAN_SCHEMA_VERSION,
        "ranked": [
            {"rank": index, "symbol": item.symbol, "analysis": spot_analysis_result_to_payload(item.result)}
            for index, item in enumerate(result.ranked, start=1)
        ],
        "failures": [
            {"symbol": failure.symbol, "error": failure.error} for failure in result.failures
        ],
        "warnings": [
            "spot live scanning is research and paper-validation only",
            "ranking uses explicit execution state and evidence count, not a fabricated score",
        ],
    }


def _rank_key(item: SpotLiveScanItem) -> tuple[int, int, int, str]:
    selected = item.result.routing.selected
    has_plan = item.result.planning is not None
    approved = selected is not None and selected.decision.value == "APPROVE"
    evidence_count = len(selected.evidence) if selected is not None else 0
    return (-int(has_plan), -int(approved), -evidence_count, item.symbol)
