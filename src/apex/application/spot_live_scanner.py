"""Deterministic multi-symbol live spot scanning with eligibility pre-filtering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.spot_analysis import SpotAnalysisResult, spot_analysis_result_to_payload
from apex.application.spot_eligibility import build_spot_market_metadata
from apex.application.spot_live import SpotLiveAccountInput, analyze_live_spot
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.data.providers.base import MarketDataProvider
from apex.data.providers.errors import MarketDataProviderError
from apex.domain.spot_market import (
    SpotEligibilityReason,
    SpotEligibilityResult,
    SpotMarketMetadata,
    SpotScannerMode,
    evaluate_spot_symbol_eligibility,
)

SPOT_LIVE_SCAN_SCHEMA_VERSION = 2
_ELIGIBILITY_TIMEFRAME = "4h"
_REVIEWABLE_REASONS = {
    SpotEligibilityReason.INSUFFICIENT_MARKET_HISTORY,
    SpotEligibilityReason.INSUFFICIENT_ATR,
    SpotEligibilityReason.TERMINAL_EXTENSION,
}


@dataclass(frozen=True, slots=True)
class SpotLiveScanItem:
    symbol: str
    result: SpotAnalysisResult
    eligibility: SpotEligibilityResult
    metadata: SpotMarketMetadata


@dataclass(frozen=True, slots=True)
class SpotLiveIneligibleItem:
    symbol: str
    status: str
    eligibility: SpotEligibilityResult
    metadata: SpotMarketMetadata


@dataclass(frozen=True, slots=True)
class SpotLiveScanFailure:
    symbol: str
    error: str


@dataclass(frozen=True, slots=True)
class SpotLiveScanResult:
    mode: SpotScannerMode
    ranked: tuple[SpotLiveScanItem, ...]
    ineligible: tuple[SpotLiveIneligibleItem, ...]
    failures: tuple[SpotLiveScanFailure, ...]


def scan_live_spot(
    *,
    symbols: tuple[str, ...],
    account_input: SpotLiveAccountInput,
    candle_provider: MarketDataProvider,
    ticker_provider: MarketDataProvider,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
    mode: SpotScannerMode = SpotScannerMode.ELIGIBLE,
    candle_limit: int = 200,
) -> SpotLiveScanResult:
    normalized = tuple(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    if not normalized:
        raise ValueError("spot live scan requires at least one symbol")
    if candle_limit < product_config.eligibility.minimum_candle_count:
        raise ValueError("spot scan candle limit cannot be below eligibility minimum candle count")

    items: list[SpotLiveScanItem] = []
    ineligible: list[SpotLiveIneligibleItem] = []
    failures: list[SpotLiveScanFailure] = []
    for symbol in normalized:
        try:
            ticker = ticker_provider.fetch_ticker(symbol)
            candles = tuple(
                candle_provider.fetch_candles(
                    symbol,
                    _ELIGIBILITY_TIMEFRAME,
                    limit=candle_limit,
                )
            )
            metadata = build_spot_market_metadata(
                symbol=symbol,
                quote_asset=account_input.account.quote_asset,
                ticker=ticker,
                candles=candles,
                terminal_extension_atr_multiple=(
                    product_config.structure.terminal_extension_atr_multiple
                ),
            )
            eligibility = evaluate_spot_symbol_eligibility(
                metadata,
                product_config.eligibility,
            )
            reviewable = _is_reviewable(eligibility)
            if not eligibility.eligible:
                ineligible.append(
                    SpotLiveIneligibleItem(
                        symbol=symbol,
                        status="reviewable" if reviewable else "ineligible",
                        eligibility=eligibility,
                        metadata=metadata,
                    )
                )
            if not _should_orchestrate(mode, eligibility.eligible, reviewable):
                continue
            result = analyze_live_spot(
                symbol=symbol,
                account_input=account_input,
                candle_provider=candle_provider,
                ticker_provider=ticker_provider,
                product_config=product_config,
                strategy_config=strategy_config,
                candle_limit=candle_limit,
            )
        except (MarketDataProviderError, OSError, TypeError, ValueError) as exc:
            failures.append(SpotLiveScanFailure(symbol=symbol, error=str(exc)))
            continue
        items.append(
            SpotLiveScanItem(
                symbol=symbol,
                result=result,
                eligibility=eligibility,
                metadata=metadata,
            )
        )

    items.sort(key=_rank_key)
    ineligible.sort(key=lambda item: item.symbol)
    failures.sort(key=lambda item: item.symbol)
    return SpotLiveScanResult(
        mode=mode,
        ranked=tuple(items),
        ineligible=tuple(ineligible),
        failures=tuple(failures),
    )


def spot_live_scan_result_to_payload(result: SpotLiveScanResult) -> dict[str, Any]:
    return {
        "schema_version": SPOT_LIVE_SCAN_SCHEMA_VERSION,
        "mode": result.mode.value,
        "ranked": [
            {
                "rank": index,
                "symbol": item.symbol,
                "eligibility": _eligibility_payload(item.eligibility),
                "metadata": item.metadata.model_dump(mode="json"),
                "analysis": spot_analysis_result_to_payload(item.result),
            }
            for index, item in enumerate(result.ranked, start=1)
        ],
        "ineligible": [
            {
                "symbol": item.symbol,
                "eligibility_status": item.status,
                "reason_codes": [reason.value for reason in item.eligibility.reasons],
                "metadata": item.metadata.model_dump(mode="json"),
            }
            for item in result.ineligible
        ],
        "failures": [
            {"symbol": failure.symbol, "error": failure.error} for failure in result.failures
        ],
        "warnings": [
            "spot live scanning is research and paper-validation only",
            "ranking uses explicit execution state and evidence count, not a fabricated score",
            "eligibility uses measurable public market data and does not fabricate market age",
        ],
    }


def _eligibility_payload(result: SpotEligibilityResult) -> dict[str, Any]:
    return {
        "eligible": result.eligible,
        "reason_codes": [reason.value for reason in result.reasons],
    }


def _is_reviewable(result: SpotEligibilityResult) -> bool:
    return not result.eligible and set(result.reasons).issubset(_REVIEWABLE_REASONS)


def _should_orchestrate(mode: SpotScannerMode, eligible: bool, reviewable: bool) -> bool:
    if mode is SpotScannerMode.ELIGIBLE:
        return eligible
    if mode is SpotScannerMode.WATCHLIST:
        return eligible or reviewable
    return True


def _eligibility_rank(result: SpotEligibilityResult) -> int:
    if result.eligible:
        return 0
    if _is_reviewable(result):
        return 1
    return 2


def _rank_key(item: SpotLiveScanItem) -> tuple[int, int, int, int, str]:
    selected = item.result.routing.selected
    has_plan = item.result.planning is not None
    approved = selected is not None and selected.decision.value == "APPROVE"
    evidence_count = len(selected.evidence) if selected is not None else 0
    return (
        _eligibility_rank(item.eligibility),
        -int(has_plan),
        -int(approved),
        -evidence_count,
        item.symbol,
    )
