"""Deterministic Phase 6 risk calculations and orchestration."""

from __future__ import annotations

from apex.risk.config import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig
from apex.risk.contracts import (
    ActionableEntry,
    LeverageRange,
    ManagementPolicy,
    ManagementPolicyType,
    PositionSize,
    RiskApprovedSetup,
    RiskAssessment,
    RiskDecision,
    RiskRejectionCode,
    StopLoss,
    StopQualityBand,
    TakeProfit,
)
from apex.scoring.contracts import Phase5AnalysisResult, RankedCandidate
from apex.strategies.contracts import TradeCandidate, TradeDirection


def _reject(
    phase5: Phase5AnalysisResult,
    config: RiskConfig,
    *items: tuple[RiskRejectionCode, str],
) -> RiskAssessment:
    return RiskAssessment(
        symbol=phase5.symbol,
        decision_time=phase5.decision_time,
        decision=RiskDecision.REJECTED,
        setup=None,
        rejection_codes=tuple(item[0] for item in items),
        reasons=tuple(item[1] for item in items),
        configuration_id=config.identifier,
    )


def _entry(candidate: TradeCandidate, config: RiskConfig) -> ActionableEntry:
    preferred = candidate.entry.preferred
    chase = preferred * config.maximum_entry_chase_pct / 100.0
    maximum_chase = (
        candidate.entry.upper + chase
        if candidate.direction is TradeDirection.LONG
        else candidate.entry.lower - chase
    )
    return ActionableEntry(
        lower=candidate.entry.lower,
        upper=candidate.entry.upper,
        preferred=preferred,
        current_price=candidate.entry.current_price,
        maximum_chase_price=maximum_chase,
        current_price_inside_zone=(
            candidate.entry.lower <= candidate.entry.current_price <= candidate.entry.upper
        ),
    )


def _stop(candidate: TradeCandidate, config: RiskConfig) -> StopLoss:
    preferred = candidate.entry.preferred
    buffer = preferred * config.structural_stop_buffer_pct / 100.0
    price = (
        candidate.invalidation.price - buffer
        if candidate.direction is TradeDirection.LONG
        else candidate.invalidation.price + buffer
    )
    distance = abs(preferred - price)
    quality_score = _stop_quality_score(candidate, distance / preferred * 100.0, config)
    return StopLoss(
        price=price,
        distance=distance,
        distance_pct=distance / preferred * 100.0,
        rationale=(
            *candidate.invalidation.rationale,
            "buffer beyond thesis invalidation",
        ),
        quality_score=quality_score,
        quality_band=_stop_quality_band(quality_score),
    )


def _candidate_atr(candidate: TradeCandidate) -> float | None:
    """Return the candidate's decision-frame ATR when available."""

    value = candidate.metadata.get("decision_atr")
    if isinstance(value, int | float) and value > 0.0:
        return float(value)
    return None


def _minimum_stop_distance(
    candidate: TradeCandidate,
    config: RiskConfig,
) -> tuple[float, str]:
    """Return the volatility-aware minimum stop distance and model label."""

    atr = _candidate_atr(candidate)
    if atr is not None:
        return (
            atr * config.minimum_stop_atr_multiple,
            "decision_atr_multiple",
        )

    fallback = candidate.entry.preferred * config.minimum_stop_distance_pct / 100.0
    return fallback, "static_entry_percentage_fallback"


def _targets(candidate: TradeCandidate, stop: StopLoss) -> tuple[TakeProfit, ...]:
    preferred = candidate.entry.preferred
    raw = tuple(
        TakeProfit(
            label=level.label,
            price=level.price,
            reward=abs(level.price - preferred),
            risk_reward=abs(level.price - preferred) / stop.distance,
            rationale=level.rationale,
            partial_close_pct=partial,
        )
        for level, partial in zip(
            candidate.targets.levels,
            _partial_close_percentages(len(candidate.targets.levels)),
            strict=True,
        )
    )
    return raw


def _partial_close_percentages(count: int) -> tuple[float, ...]:
    if count <= 0:
        raise ValueError("target count must be positive")
    if count == 1:
        return (100.0,)
    if count == 2:
        return (50.0, 50.0)
    first = (40.0, 35.0)
    remaining = 25.0 / (count - 2)
    return (*first, *(remaining for _ in range(count - 2)))


def _stop_quality_score(
    candidate: TradeCandidate,
    stop_distance_pct: float,
    config: RiskConfig,
) -> float:
    distance_window = config.maximum_stop_distance_pct - config.minimum_stop_distance_pct
    if distance_window <= 0.0:
        distance_quality = 0.0
    else:
        midpoint = (config.maximum_stop_distance_pct + config.minimum_stop_distance_pct) / 2.0
        distance_quality = 1.0 - min(
            1.0,
            abs(stop_distance_pct - midpoint) / (distance_window / 2.0),
        )
    structure_quality = candidate.quality.structure_quality
    entry_quality = candidate.quality.entry_quality
    blended = distance_quality * 0.45 + structure_quality * 0.35 + entry_quality * 0.20
    return max(0.0, min(1.0, blended))


def _stop_quality_band(score: float) -> StopQualityBand:
    if score >= 0.75:
        return StopQualityBand.STRONG
    if score >= 0.45:
        return StopQualityBand.ACCEPTABLE
    return StopQualityBand.WEAK


def _management_policies(targets: tuple[TakeProfit, ...]) -> tuple[ManagementPolicy, ...]:
    first_target = targets[0]
    final_target = targets[-1]
    return (
        ManagementPolicy(
            kind=ManagementPolicyType.BREAKEVEN,
            trigger=f"{first_target.label} touched or trade reaches 1R",
            action="move stop to breakeven after partial realization",
            rationale=("protect realized edge after first objective confirms thesis",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TRAILING,
            trigger=f"price accepts beyond {first_target.label}",
            action="trail behind the latest valid structural swing or volatility band",
            rationale=("keep upside open while preserving structural invalidation",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.TIME_EXIT,
            trigger="entry thesis remains unresolved through candidate expiry",
            action="cancel unfilled entry or flatten stale paper position",
            rationale=("avoid carrying a setup after its analysis window expires",),
        ),
        ManagementPolicy(
            kind=ManagementPolicyType.MOMENTUM_FAILURE,
            trigger=f"momentum contradicts before {final_target.label}",
            action="reduce or exit remaining exposure before structural stop",
            rationale=("cut exposure when continuation evidence fails before invalidation",),
        ),
    )


def _position_size(
    config: RiskConfig,
    entry: ActionableEntry,
    stop: StopLoss,
) -> PositionSize:
    """Size the position so structural loss plus execution costs equals the cap."""

    risk_amount = config.account_equity * config.risk_per_trade_pct / 100.0

    structural_loss_fraction = stop.distance / entry.preferred
    execution_cost_fraction = (
        config.entry_fee_pct
        + config.exit_fee_pct
        + config.entry_slippage_pct
        + config.exit_slippage_pct
    ) / 100.0
    total_loss_fraction = structural_loss_fraction + execution_cost_fraction

    if total_loss_fraction <= 0.0:
        raise ValueError("modeled Phase 6 loss fraction must be positive")

    notional_value = risk_amount / total_loss_fraction
    quantity = notional_value / entry.preferred

    return PositionSize(
        risk_amount=risk_amount,
        quantity=quantity,
        notional_value=notional_value,
        account_risk_pct=config.risk_per_trade_pct,
        required_leverage=max(
            1.0,
            notional_value / config.account_equity,
        ),
    )


def _leverage(
    candidate: TradeCandidate,
    config: RiskConfig,
    position: PositionSize,
    stop: StopLoss,
) -> LeverageRange | None:
    stop_fraction = stop.distance_pct / 100.0
    maintenance_fraction = config.maintenance_margin_pct / 100.0
    required_liquidation_distance = stop_fraction * (1.0 + config.liquidation_buffer_ratio)
    denominator = required_liquidation_distance + maintenance_fraction
    if denominator <= 0.0:
        return None

    modeled_maximum = 1.0 / denominator
    maximum = min(config.maximum_leverage, modeled_maximum)
    minimum = position.required_leverage
    if maximum < minimum:
        return None

    liquidation_distance = max(0.0, 1.0 / maximum - maintenance_fraction)
    entry = candidate.entry.preferred
    liquidation_price = (
        entry * (1.0 - liquidation_distance)
        if candidate.direction is TradeDirection.LONG
        else entry * (1.0 + liquidation_distance)
    )
    buffer = (
        stop.price - liquidation_price
        if candidate.direction is TradeDirection.LONG
        else liquidation_price - stop.price
    )
    if buffer <= 0.0:
        return None

    return LeverageRange(
        minimum=minimum,
        maximum=maximum,
        modeled_maximum=modeled_maximum,
        liquidation_price_at_maximum=liquidation_price,
        stop_to_liquidation_buffer_pct=buffer / entry * 100.0,
    )


def _exposure_rejections(
    config: RiskConfig,
    exposure: ExposureState,
    risk_amount: float,
) -> tuple[tuple[RiskRejectionCode, str], ...]:
    rejected: list[tuple[RiskRejectionCode, str]] = []
    equity = config.account_equity
    if exposure.open_trades >= config.maximum_concurrent_trades:
        rejected.append(
            (
                RiskRejectionCode.MAX_CONCURRENT_TRADES,
                "maximum concurrent trades reached",
            )
        )
    if exposure.open_risk_amount + risk_amount > equity * config.maximum_open_risk_pct / 100.0:
        rejected.append((RiskRejectionCode.MAX_OPEN_RISK, "maximum aggregate open risk exceeded"))
    if (
        exposure.same_direction_risk_amount + risk_amount
        > equity * config.maximum_directional_risk_pct / 100.0
    ):
        rejected.append(
            (
                RiskRejectionCode.MAX_DIRECTIONAL_RISK,
                "maximum same-direction risk exceeded",
            )
        )
    if (
        exposure.correlated_risk_amount + risk_amount
        > equity * config.maximum_correlated_risk_pct / 100.0
    ):
        rejected.append((RiskRejectionCode.MAX_CORRELATED_RISK, "maximum correlated risk exceeded"))
    if exposure.daily_realized_loss >= equity * config.maximum_daily_loss_pct / 100.0:
        rejected.append((RiskRejectionCode.DAILY_LOSS_LIMIT, "daily loss limit reached"))
    if exposure.consecutive_losses >= config.maximum_consecutive_losses:
        rejected.append(
            (RiskRejectionCode.CONSECUTIVE_LOSS_LIMIT, "consecutive loss limit reached")
        )
    return tuple(rejected)


def _candidate_from(selected: RankedCandidate) -> TradeCandidate:
    return selected.candidate


def analyze_phase6(
    phase5: Phase5AnalysisResult,
    *,
    config: RiskConfig = DEFAULT_RISK_CONFIG,
    exposure: ExposureState | None = None,
) -> RiskAssessment:
    """Apply deterministic risk controls to the selected Phase 5 candidate."""

    if exposure is None:
        exposure = ExposureState()

    selected = phase5.selected_candidate
    if selected is None:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.NO_SELECTED_CANDIDATE,
                "Phase 5 selected no trade candidate",
            ),
        )

    candidate = _candidate_from(selected)
    entry = _entry(candidate, config)
    extended = (
        entry.current_price > entry.maximum_chase_price
        if candidate.direction is TradeDirection.LONG
        else entry.current_price < entry.maximum_chase_price
    )
    if candidate.entry.is_extended or extended:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.ENTRY_TOO_EXTENDED,
                "current price is beyond the maximum chase price",
            ),
        )

    stop = _stop(candidate, config)
    minimum_stop_distance, minimum_stop_model = _minimum_stop_distance(
        candidate,
        config,
    )
    if stop.distance < minimum_stop_distance:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.STOP_TOO_TIGHT,
                (f"stop is inside the volatility-aware noise floor ({minimum_stop_model})"),
            ),
        )
    if stop.distance_pct > config.maximum_stop_distance_pct:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.STOP_TOO_WIDE,
                "stop exceeds the configured risk boundary",
            ),
        )

    targets = _targets(candidate, stop)
    if max(target.risk_reward for target in targets) < config.minimum_risk_reward:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.INSUFFICIENT_TARGET_SPACE,
                "no structural target reaches the minimum risk-to-reward requirement",
            ),
        )

    position = _position_size(config, entry, stop)
    exposure_rejections = _exposure_rejections(config, exposure, position.risk_amount)
    if exposure_rejections:
        return _reject(phase5, config, *exposure_rejections)

    leverage = _leverage(candidate, config, position, stop)
    if leverage is None:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.LEVERAGE_UNSAFE,
                "required leverage cannot keep liquidation safely beyond the stop",
            ),
        )

    return RiskAssessment(
        symbol=phase5.symbol,
        decision_time=phase5.decision_time,
        decision=RiskDecision.APPROVED,
        setup=RiskApprovedSetup(
            symbol=candidate.symbol,
            direction=candidate.direction,
            strategy=candidate.strategy,
            decision_time=candidate.decision_time,
            candidate_id=selected.scored.candidate_id,
            confidence_score=selected.final_score,
            entry=entry,
            stop_loss=stop,
            take_profits=targets,
            position_size=position,
            leverage=leverage,
            management_policies=_management_policies(targets),
            warnings=tuple(candidate.evidence.warnings),
        ),
        rejection_codes=(),
        reasons=(),
        configuration_id=config.identifier,
    )
