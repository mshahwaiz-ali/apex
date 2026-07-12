"""Deterministic Phase 6 risk calculations and orchestration."""

from __future__ import annotations

from apex.risk.config import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig
from apex.risk.contracts import (
    ActionableEntry,
    LeverageRange,
    PositionSize,
    RiskApprovedSetup,
    RiskAssessment,
    RiskDecision,
    RiskRejectionCode,
    StopLoss,
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
    return StopLoss(
        price=price,
        distance=distance,
        distance_pct=distance / preferred * 100.0,
        rationale=(*candidate.invalidation.rationale, "volatility buffer beyond thesis invalidation"),
    )


def _targets(candidate: TradeCandidate, stop: StopLoss) -> tuple[TakeProfit, ...]:
    preferred = candidate.entry.preferred
    targets: list[TakeProfit] = []
    for level in candidate.targets.levels:
        reward = abs(level.price - preferred)
        targets.append(
            TakeProfit(
                label=level.label,
                price=level.price,
                reward=reward,
                risk_reward=reward / stop.distance,
                rationale=level.rationale,
            )
        )
    return tuple(targets)


def _position_size(config: RiskConfig, entry: ActionableEntry, stop: StopLoss) -> PositionSize:
    risk_amount = config.account_equity * config.risk_per_trade_pct / 100.0
    quantity = risk_amount / stop.distance
    return PositionSize(
        risk_amount=risk_amount,
        quantity=quantity,
        notional_value=quantity * entry.preferred,
        account_risk_pct=config.risk_per_trade_pct,
    )


def _leverage(
    candidate: TradeCandidate,
    config: RiskConfig,
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
    if maximum < 1.0:
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
        minimum=1.0,
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
            (RiskRejectionCode.MAX_CONCURRENT_TRADES, "maximum concurrent trades reached")
        )
    if exposure.open_risk_amount + risk_amount > equity * config.maximum_open_risk_pct / 100.0:
        rejected.append((RiskRejectionCode.MAX_OPEN_RISK, "maximum aggregate open risk exceeded"))
    if (
        exposure.same_direction_risk_amount + risk_amount
        > equity * config.maximum_directional_risk_pct / 100.0
    ):
        rejected.append(
            (RiskRejectionCode.MAX_DIRECTIONAL_RISK, "maximum same-direction risk exceeded")
        )
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
    exposure: ExposureState = ExposureState(),
) -> RiskAssessment:
    """Apply deterministic risk controls to the selected Phase 5 candidate."""

    selected = phase5.selected_candidate
    if selected is None:
        return _reject(
            phase5,
            config,
            (RiskRejectionCode.NO_SELECTED_CANDIDATE, "Phase 5 selected no trade candidate"),
        )

    candidate = _candidate_from(selected)
    entry = _entry(candidate, config)
    if candidate.direction is TradeDirection.LONG:
        extended = entry.current_price > entry.maximum_chase_price
    else:
        extended = entry.current_price < entry.maximum_chase_price
    if candidate.entry.is_extended or extended:
        return _reject(
            phase5,
            config,
            (RiskRejectionCode.ENTRY_TOO_EXTENDED, "current price is beyond the maximum chase price"),
        )

    stop = _stop(candidate, config)
    if stop.distance_pct < config.minimum_stop_distance_pct:
        return _reject(
            phase5,
            config,
            (RiskRejectionCode.STOP_TOO_TIGHT, "stop is inside the configured noise floor"),
        )
    if stop.distance_pct > config.maximum_stop_distance_pct:
        return _reject(
            phase5,
            config,
            (RiskRejectionCode.STOP_TOO_WIDE, "stop exceeds the configured risk boundary"),
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

    leverage = _leverage(candidate, config, stop)
    if leverage is None:
        return _reject(
            phase5,
            config,
            (
                RiskRejectionCode.LEVERAGE_UNSAFE,
                "liquidation cannot remain safely beyond the structural stop",
            ),
        )

    warnings = tuple(candidate.evidence.warnings)
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
            warnings=warnings,
        ),
        rejection_codes=(),
        reasons=(),
        configuration_id=config.identifier,
    )
