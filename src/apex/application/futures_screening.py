"""Deterministic lightweight futures-universe opportunity screening."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from math import log10

from apex.domain.futures_market import FuturesContractMetadata
from apex.domain.futures_screening import (
    FuturesDiscoveryLane,
    FuturesDiscoveryLaneSignal,
    FuturesOpportunityFeatures,
    FuturesOpportunityScore,
    FuturesScreenerConfig,
    FuturesScreeningCandidate,
    FuturesScreeningExclusion,
    FuturesScreeningExclusionReason,
    FuturesScreeningResult,
    FuturesTickerSnapshot,
)
from apex.domain.models import Candle


def ticker_prefilter_symbols(
    contracts: Iterable[FuturesContractMetadata],
    tickers: Iterable[FuturesTickerSnapshot],
    config: FuturesScreenerConfig,
) -> tuple[str, ...]:
    """Return symbols worth one limited candle request."""

    contracts_by_symbol = {
        _normalize_symbol(contract.exchange_symbol): contract for contract in contracts
    }
    eligible: list[tuple[str, FuturesTickerSnapshot]] = []
    for ticker in tickers:
        exchange_symbol = _normalize_symbol(ticker.exchange_symbol)
        if exchange_symbol not in contracts_by_symbol:
            continue
        if _hard_exclusion(ticker, config) is not None:
            continue
        eligible.append((exchange_symbol, ticker))

    ranked = sorted(
        eligible,
        key=lambda item: (
            -item[1].absolute_movement_percentage,
            -item[1].quote_volume_24h,
            item[1].spread_percentage,
            item[0],
        ),
    )
    return tuple(exchange_symbol for exchange_symbol, _ in ranked[: config.ticker_prefilter_size])


def screen_futures_universe(
    contracts: Iterable[FuturesContractMetadata],
    tickers: Iterable[FuturesTickerSnapshot],
    candle_sets_or_config: (Mapping[str, Sequence[Candle]] | FuturesScreenerConfig),
    config: FuturesScreenerConfig | None = None,
    *,
    candle_failures: Mapping[str, str] | None = None,
) -> FuturesScreeningResult:
    """Screen tickers alone or use recent candles when supplied."""

    if isinstance(candle_sets_or_config, FuturesScreenerConfig):
        if config is not None:
            raise ValueError("config must be omitted for ticker-only screening")
        return _screen_tickers_only(
            contracts,
            tickers,
            candle_sets_or_config,
        )

    if config is None:
        raise ValueError("config is required when candle sets are supplied")
    candle_sets = candle_sets_or_config

    contracts_by_symbol = {
        _normalize_symbol(contract.exchange_symbol): contract for contract in contracts
    }
    tickers_by_symbol = {_normalize_symbol(ticker.exchange_symbol): ticker for ticker in tickers}
    normalized_candles = {
        _normalize_symbol(symbol): candles for symbol, candles in candle_sets.items()
    }
    failures = {
        _normalize_symbol(symbol): detail for symbol, detail in (candle_failures or {}).items()
    }
    exclusions: list[FuturesScreeningExclusion] = []
    hard_eligible: list[tuple[FuturesContractMetadata, FuturesTickerSnapshot]] = []

    for exchange_symbol in sorted(tickers_by_symbol.keys() - contracts_by_symbol.keys()):
        exclusions.append(
            FuturesScreeningExclusion(
                exchange_symbol=exchange_symbol,
                reason=FuturesScreeningExclusionReason.OUTSIDE_UNIVERSE,
                detail=("Ticker is not part of the selected futures contract universe."),
            )
        )

    for exchange_symbol in sorted(contracts_by_symbol):
        contract = contracts_by_symbol[exchange_symbol]
        ticker = tickers_by_symbol.get(exchange_symbol)
        if ticker is None:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=FuturesScreeningExclusionReason.MISSING_TICKER,
                    detail=("No valid batch ticker was available for this contract."),
                )
            )
            continue

        hard_exclusion = _hard_exclusion(ticker, config)
        if hard_exclusion is not None:
            reason, detail = hard_exclusion
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=reason,
                    detail=detail,
                )
            )
            continue
        hard_eligible.append((contract, ticker))

    prefilter_symbols = set(
        ticker_prefilter_symbols(
            (contract for contract, _ in hard_eligible),
            (ticker for _, ticker in hard_eligible),
            config,
        )
    )
    scored: list[
        tuple[
            FuturesContractMetadata,
            FuturesTickerSnapshot,
            FuturesOpportunityFeatures,
            FuturesOpportunityScore,
            tuple[FuturesDiscoveryLaneSignal, ...],
        ]
    ] = []

    for contract, ticker in hard_eligible:
        exchange_symbol = _normalize_symbol(contract.exchange_symbol)
        if exchange_symbol not in prefilter_symbols:
            continue
        failure = failures.get(exchange_symbol)
        if failure is not None:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(FuturesScreeningExclusionReason.CANDLE_FETCH_FAILED),
                    detail=failure,
                )
            )
            continue

        candles = tuple(
            candle for candle in normalized_candles.get(exchange_symbol, ()) if candle.is_closed
        )
        if len(candles) < config.minimum_candle_count:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(FuturesScreeningExclusionReason.INSUFFICIENT_CANDLE_HISTORY),
                    detail=(
                        f"Received {len(candles)} closed candles; "
                        f"{config.minimum_candle_count} required."
                    ),
                )
            )
            continue

        try:
            features = extract_opportunity_features(candles)
        except ValueError as exc:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=(FuturesScreeningExclusionReason.INVALID_CANDLE_DATA),
                    detail=str(exc),
                )
            )
            continue

        opportunity = score_futures_opportunity(
            ticker,
            features,
            config,
        )
        lanes = classify_discovery_lanes(ticker, features, opportunity)
        scored.append((contract, ticker, features, opportunity, lanes))

    ranked = sorted(
        scored,
        key=lambda item: (
            -item[3].total,
            -item[3].directional_clarity,
            -item[3].relative_volume,
            item[1].spread_percentage,
            _normalize_symbol(item[0].exchange_symbol),
        ),
    )
    selected = ranked[: config.shortlist_size]

    for contract, _, _, opportunity, _ in ranked[config.shortlist_size :]:
        exclusions.append(
            FuturesScreeningExclusion(
                exchange_symbol=_normalize_symbol(contract.exchange_symbol),
                reason=FuturesScreeningExclusionReason.BELOW_SHORTLIST,
                detail=(
                    f"Opportunity score {opportunity.total:.2f} "
                    "ranked below the configured shortlist."
                ),
            )
        )

    candidates = tuple(
        FuturesScreeningCandidate(
            rank=rank,
            contract=contract,
            ticker=ticker,
            features=features,
            opportunity=opportunity,
            discovery_lanes=lanes,
        )
        for rank, (
            contract,
            ticker,
            features,
            opportunity,
            lanes,
        ) in enumerate(selected, start=1)
    )

    return FuturesScreeningResult(
        total_contracts=len(contracts_by_symbol),
        total_tickers=len(tickers_by_symbol),
        hard_eligible_count=len(hard_eligible),
        candle_screened_count=len(scored),
        candidates=candidates,
        exclusions=tuple(exclusions),
    )


def _screen_tickers_only(
    contracts: Iterable[FuturesContractMetadata],
    tickers: Iterable[FuturesTickerSnapshot],
    config: FuturesScreenerConfig,
) -> FuturesScreeningResult:
    """Preserve the original cheap ticker-only screening contract."""

    contracts_by_symbol = {
        _normalize_symbol(contract.exchange_symbol): contract for contract in contracts
    }
    tickers_by_symbol = {_normalize_symbol(ticker.exchange_symbol): ticker for ticker in tickers}
    exclusions: list[FuturesScreeningExclusion] = []
    eligible: list[tuple[FuturesContractMetadata, FuturesTickerSnapshot]] = []

    for exchange_symbol in sorted(tickers_by_symbol.keys() - contracts_by_symbol.keys()):
        exclusions.append(
            FuturesScreeningExclusion(
                exchange_symbol=exchange_symbol,
                reason=FuturesScreeningExclusionReason.OUTSIDE_UNIVERSE,
                detail=("Ticker is not part of the selected futures contract universe."),
            )
        )

    for exchange_symbol in sorted(contracts_by_symbol):
        contract = contracts_by_symbol[exchange_symbol]
        ticker = tickers_by_symbol.get(exchange_symbol)
        if ticker is None:
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=FuturesScreeningExclusionReason.MISSING_TICKER,
                    detail=("No valid batch ticker was available for this contract."),
                )
            )
            continue

        hard_exclusion = _hard_exclusion(ticker, config)
        if hard_exclusion is not None:
            reason, detail = hard_exclusion
            exclusions.append(
                FuturesScreeningExclusion(
                    exchange_symbol=exchange_symbol,
                    reason=reason,
                    detail=detail,
                )
            )
            continue
        eligible.append((contract, ticker))

    ranked = sorted(
        eligible,
        key=lambda item: (
            -item[1].absolute_movement_percentage,
            -item[1].quote_volume_24h,
            item[1].spread_percentage,
            _normalize_symbol(item[0].exchange_symbol),
        ),
    )[: config.shortlist_size]

    neutral_features = FuturesOpportunityFeatures(
        return_5m_pct=0.0,
        return_15m_pct=0.0,
        return_30m_pct=0.0,
        return_1h_pct=0.0,
        relative_volume=0.0,
        volume_acceleration=0.0,
        atr_percentage=0.0,
        range_expansion=0.0,
        trend_slope_percentage=0.0,
        breakout_proximity=0.0,
        ema_distance_atr=0.0,
        wick_intensity=0.0,
        directional_persistence=0.0,
        current_participation=0.0,
    )
    candidates = tuple(
        FuturesScreeningCandidate(
            rank=rank,
            contract=contract,
            ticker=ticker,
            features=neutral_features,
            opportunity=FuturesOpportunityScore(
                total=round(
                    min(
                        100.0,
                        ticker.absolute_movement_percentage,
                    ),
                    4,
                ),
                liquidity=0.0,
                movement=round(
                    min(
                        100.0,
                        ticker.absolute_movement_percentage,
                    ),
                    4,
                ),
                acceleration=0.0,
                relative_volume=0.0,
                volatility_usability=0.0,
                entry_freshness=0.0,
                structure_proximity=0.0,
                directional_clarity=0.0,
                spread_quality=0.0,
                noise_quality=0.0,
                reasons=("ticker-only compatibility screening",),
                cautions=(),
            ),
            discovery_lanes=(
                FuturesDiscoveryLaneSignal(
                    lane=FuturesDiscoveryLane.FAST_MOVER,
                    score=round(min(100.0, ticker.absolute_movement_percentage), 4),
                    reason="ticker-only compatibility screening used absolute movement",
                ),
            ),
        )
        for rank, (contract, ticker) in enumerate(ranked, start=1)
    )
    return FuturesScreeningResult(
        total_contracts=len(contracts_by_symbol),
        total_tickers=len(tickers_by_symbol),
        hard_eligible_count=len(eligible),
        candle_screened_count=0,
        candidates=candidates,
        exclusions=tuple(exclusions),
    )


def extract_opportunity_features(
    candles: Sequence[Candle],
) -> FuturesOpportunityFeatures:
    """Derive 5m through 1h features from one closed 5m series."""

    ordered = tuple(sorted(candles, key=lambda candle: candle.open_time))
    if len(ordered) < 13:
        raise ValueError("at least 13 closed candles are required")

    closes = [candle.close for candle in ordered]
    volumes = [candle.volume for candle in ordered]
    ranges = [candle.high - candle.low for candle in ordered]
    true_ranges = [
        max(
            candle.high - candle.low,
            abs(candle.high - ordered[index - 1].close),
            abs(candle.low - ordered[index - 1].close),
        )
        for index, candle in enumerate(ordered)
        if index > 0
    ]

    atr = _mean(true_ranges[-12:])
    latest = ordered[-1]
    baseline_volume = _mean(volumes[-13:-1])
    recent_volume = _mean(volumes[-3:])
    previous_volume = _mean(volumes[-6:-3])
    baseline_range = _mean(ranges[-13:-1])
    recent_range = _mean(ranges[-3:])
    recent = ordered[-12:]
    recent_high = max(candle.high for candle in recent[:-1])
    recent_low = min(candle.low for candle in recent[:-1])
    nearest_level_distance = min(
        abs(recent_high - latest.close),
        abs(latest.close - recent_low),
    )
    ema = _ema(closes[-12:], period=6)

    total_wick = 0.0
    total_range = 0.0
    directional = 0
    net_direction = 1 if closes[-1] >= closes[-7] else -1
    for candle in ordered[-6:]:
        candle_range = candle.high - candle.low
        total_range += candle_range
        total_wick += max(
            0.0,
            candle_range - abs(candle.close - candle.open),
        )
        candle_direction = 1 if candle.close >= candle.open else -1
        if candle_direction == net_direction:
            directional += 1

    return FuturesOpportunityFeatures(
        return_5m_pct=_return_pct(closes[-2], closes[-1]),
        return_15m_pct=_return_pct(closes[-4], closes[-1]),
        return_30m_pct=_return_pct(closes[-7], closes[-1]),
        return_1h_pct=_return_pct(closes[-13], closes[-1]),
        relative_volume=_safe_ratio(
            recent_volume,
            baseline_volume,
        ),
        volume_acceleration=_safe_ratio(
            recent_volume,
            previous_volume,
        ),
        atr_percentage=_safe_ratio(atr, latest.close) * 100,
        range_expansion=_safe_ratio(
            recent_range,
            baseline_range,
        ),
        trend_slope_percentage=(_return_pct(closes[-13], closes[-1]) / 12),
        breakout_proximity=_clamp01(
            1.0
            - _safe_ratio(
                nearest_level_distance,
                atr * 2,
            )
        ),
        ema_distance_atr=_safe_ratio(
            abs(latest.close - ema),
            atr,
        ),
        wick_intensity=_clamp01(_safe_ratio(total_wick, total_range)),
        directional_persistence=directional / 6,
        current_participation=_safe_ratio(
            latest.volume,
            baseline_volume,
        ),
    )


def score_futures_opportunity(
    ticker: FuturesTickerSnapshot,
    features: FuturesOpportunityFeatures,
    config: FuturesScreenerConfig,
) -> FuturesOpportunityScore:
    """Calculate deterministic normalized opportunity components."""

    liquidity = _score_log_scale(
        ticker.quote_volume_24h,
        config.minimum_quote_volume_24h,
        config.target_quote_volume_24h,
    )
    movement = _score_target(
        max(
            ticker.absolute_movement_percentage * 0.35,
            abs(features.return_1h_pct),
            abs(features.return_30m_pct) * 1.25,
        ),
        config.target_movement_percentage,
    )
    acceleration = _score_target(
        max(
            abs(features.return_5m_pct) * 4,
            abs(features.return_15m_pct) * 2,
            abs(features.return_30m_pct),
        ),
        config.target_movement_percentage,
    )
    relative_volume = _score_target(
        max(
            features.relative_volume,
            features.volume_acceleration,
            features.current_participation,
        ),
        config.target_relative_volume,
    )
    volatility_usability = _band_score(
        features.atr_percentage,
        ideal=config.target_atr_percentage,
        maximum=config.maximum_usable_atr_percentage,
    )
    entry_freshness = 100.0 * _clamp01(
        1.0 - features.ema_distance_atr / config.maximum_extension_atr
    )
    structure_proximity = features.breakout_proximity * 100
    directional_clarity = 100.0 * _clamp01(
        features.directional_persistence * 0.65
        + min(
            abs(features.trend_slope_percentage),
            1.0,
        )
        * 0.35
    )
    spread_quality = 100.0 * _clamp01(
        1.0 - ticker.spread_percentage / config.maximum_spread_percentage
    )
    noise_quality = 100.0 * _clamp01(
        1.0 - (features.wick_intensity * 0.6 + max(0.0, features.range_expansion - 2.0) / 4.0)
    )

    components = {
        "liquidity": liquidity,
        "movement": movement,
        "acceleration": acceleration,
        "relative_volume": relative_volume,
        "volatility_usability": volatility_usability,
        "entry_freshness": entry_freshness,
        "structure_proximity": structure_proximity,
        "directional_clarity": directional_clarity,
        "spread_quality": spread_quality,
        "noise_quality": noise_quality,
    }
    total = sum(components[name] * weight for name, weight in config.weights.as_dict().items())

    reasons: list[str] = []
    cautions: list[str] = []
    if acceleration >= 70:
        reasons.append("recent momentum is accelerating")
    if relative_volume >= 70:
        reasons.append("recent participation is above baseline")
    if structure_proximity >= 70:
        reasons.append("price is near a recent structural boundary")
    if directional_clarity >= 70:
        reasons.append("recent candles show directional persistence")
    if not reasons:
        reasons.append("balanced movement, liquidity, and entry-quality profile")

    if entry_freshness < 45:
        cautions.append("price is extended from the short EMA")
    if noise_quality < 45:
        cautions.append("recent candles contain elevated wick or range noise")
    if volatility_usability < 45:
        cautions.append("recent volatility is outside the preferred usable band")
    if spread_quality < 50:
        cautions.append("spread reduces execution quality")

    rounded = {name: round(value, 4) for name, value in components.items()}
    return FuturesOpportunityScore(
        total=round(_clamp(total, 0.0, 100.0), 4),
        liquidity=rounded["liquidity"],
        movement=rounded["movement"],
        acceleration=rounded["acceleration"],
        relative_volume=rounded["relative_volume"],
        volatility_usability=rounded["volatility_usability"],
        entry_freshness=rounded["entry_freshness"],
        structure_proximity=rounded["structure_proximity"],
        directional_clarity=rounded["directional_clarity"],
        spread_quality=rounded["spread_quality"],
        noise_quality=rounded["noise_quality"],
        reasons=tuple(reasons),
        cautions=tuple(cautions),
    )


def classify_discovery_lanes(
    ticker: FuturesTickerSnapshot,
    features: FuturesOpportunityFeatures,
    opportunity: FuturesOpportunityScore,
) -> tuple[FuturesDiscoveryLaneSignal, ...]:
    """Classify screening candidates into transparent discovery lanes."""

    lanes: list[FuturesDiscoveryLaneSignal] = []
    if features.directional_persistence >= 0.67 and opportunity.entry_freshness >= 45:
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.TREND_CONTINUATION,
                score=round(
                    min(
                        100.0,
                        opportunity.directional_clarity * 0.65 + opportunity.entry_freshness * 0.35,
                    ),
                    4,
                ),
                reason="directional persistence remains usable without excessive EMA extension",
            )
        )
    if features.range_expansion <= 0.85 or (
        features.atr_percentage > 0
        and features.atr_percentage <= max(0.01, opportunity.volatility_usability / 100 * 2.5)
    ):
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.COMPRESSION_EXPANSION,
                score=round(
                    min(
                        100.0,
                        (1.0 - min(features.range_expansion, 1.0)) * 70.0
                        + opportunity.structure_proximity * 0.3,
                    ),
                    4,
                ),
                reason="recent range is compressed near a potential expansion area",
            )
        )
    if opportunity.structure_proximity >= 65 and opportunity.relative_volume >= 45:
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.FRESH_BREAK,
                score=round(
                    min(
                        100.0,
                        opportunity.structure_proximity * 0.55 + opportunity.relative_volume * 0.45,
                    ),
                    4,
                ),
                reason="price is near a recent boundary with participation evidence",
            )
        )
    if opportunity.acceleration >= 65 or ticker.absolute_movement_percentage >= 8:
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.FAST_MOVER,
                score=round(
                    min(
                        100.0,
                        opportunity.acceleration * 0.7
                        + min(100.0, ticker.absolute_movement_percentage * 8.0) * 0.3,
                    ),
                    4,
                ),
                reason="recent return acceleration or 24h movement is elevated",
            )
        )
    if features.wick_intensity >= 0.45 and opportunity.structure_proximity >= 45:
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.RANGE_LIQUIDITY_REJECTION,
                score=round(
                    min(
                        100.0,
                        features.wick_intensity * 55.0 + opportunity.structure_proximity * 0.45,
                    ),
                    4,
                ),
                reason="wick activity near structure suggests rejection or sweep potential",
            )
        )
    if (
        abs(features.return_1h_pct) >= 1.5
        and opportunity.relative_volume >= 45
        and opportunity.spread_quality >= 50
    ):
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.RELATIVE_STRENGTH_WEAKNESS,
                score=round(
                    min(
                        100.0,
                        abs(features.return_1h_pct) * 18.0 + opportunity.relative_volume * 0.35,
                    ),
                    4,
                ),
                reason="recent relative movement is supported by participation and usable spread",
            )
        )
    if not lanes:
        lanes.append(
            FuturesDiscoveryLaneSignal(
                lane=FuturesDiscoveryLane.FAST_MOVER,
                score=round(max(1.0, opportunity.movement), 4),
                reason="fallback lane for balanced movement and execution-quality screening",
            )
        )
    return tuple(sorted(lanes, key=lambda item: (-item.score, item.lane.value)))


def _hard_exclusion(
    ticker: FuturesTickerSnapshot,
    config: FuturesScreenerConfig,
) -> tuple[FuturesScreeningExclusionReason, str] | None:
    if ticker.quote_volume_24h < config.minimum_quote_volume_24h:
        return (
            FuturesScreeningExclusionReason.INSUFFICIENT_LIQUIDITY,
            (
                f"24h quote volume {ticker.quote_volume_24h} "
                f"is below {config.minimum_quote_volume_24h}."
            ),
        )
    if ticker.spread_percentage > config.maximum_spread_percentage:
        return (
            FuturesScreeningExclusionReason.SPREAD_TOO_WIDE,
            (
                f"Spread {ticker.spread_percentage} is above "
                f"{config.maximum_spread_percentage} percent."
            ),
        )
    if ticker.absolute_movement_percentage < config.minimum_absolute_movement_percentage:
        return (
            FuturesScreeningExclusionReason.INSUFFICIENT_MOVEMENT,
            (
                "Absolute 24h movement "
                f"{ticker.absolute_movement_percentage} is below "
                f"{config.minimum_absolute_movement_percentage} percent."
            ),
        )
    return None


def _return_pct(start: float, end: float) -> float:
    if start <= 0:
        raise ValueError("return baseline must be positive")
    return (end - start) / start * 100


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _ema(values: Sequence[float], *, period: int) -> float:
    if not values:
        raise ValueError("EMA requires values")
    alpha = 2.0 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def _score_target(value: float, target: float) -> float:
    return 100.0 * _clamp01(value / target)


def _score_log_scale(
    value: float,
    floor: float,
    target: float,
) -> float:
    if value <= floor:
        return 0.0
    if target <= floor:
        return 100.0
    shifted_value = value - floor + 1.0
    shifted_target = target - floor + 1.0
    return 100.0 * _clamp01(log10(shifted_value) / log10(shifted_target))


def _band_score(
    value: float,
    *,
    ideal: float,
    maximum: float,
) -> float:
    if value <= ideal:
        return _score_target(value, ideal)
    if value >= maximum:
        return 0.0
    return 100.0 * (maximum - value) / (maximum - ideal)


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return min(maximum, max(minimum, value))


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper().replace("/", "").replace("-", "")
    if not normalized:
        raise ValueError("symbol cannot be empty")
    return normalized
