"""Execution binding for frozen V2 spot baseline campaign cells."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

from apex.spot_backtesting import (
    SpotBacktestConfig,
    SpotBar,
    SpotOrderPlan,
    run_spot_backtest,
)
from apex.spot_baseline.contracts import (
    SpotBaselineCampaignPlan,
    SpotCampaignResult,
)


@dataclass(frozen=True, slots=True)
class SpotCampaignInput:
    """Strategy-generated plans and chronological bars for one frozen cell."""

    plans: tuple[SpotOrderPlan, ...]
    bars: tuple[SpotBar, ...]

    def __post_init__(self) -> None:
        if not self.plans or not self.bars:
            raise ValueError("spot campaign input requires plans and bars")


def execute_spot_baseline_plan(
    plan: SpotBaselineCampaignPlan,
    inputs: Mapping[str, SpotCampaignInput],
    *,
    starting_cash: float,
    minimum_cash_reserve_pct: float = 10.0,
    maximum_scale_entries: int = 3,
    maximum_holding: timedelta = timedelta(days=7),
) -> tuple[SpotCampaignResult, ...]:
    """Execute every frozen campaign cell exactly once in stable order."""
    planned = {cell.key for cell in plan.cells}
    observed = set(inputs)
    missing = planned - observed
    extra = observed - planned
    if missing:
        raise ValueError(f"missing spot campaign inputs: {sorted(missing)}")
    if extra:
        raise ValueError(f"unplanned spot campaign inputs: {sorted(extra)}")

    costs = {variant.identifier: variant for variant in plan.cost_variants}
    allocations = {variant.identifier: variant for variant in plan.allocation_variants}
    datasets = {dataset.dataset_id: dataset for dataset in plan.datasets}
    completed: list[SpotCampaignResult] = []
    for cell in sorted(plan.cells, key=lambda item: item.key):
        campaign_input = inputs[cell.key]
        _validate_cell_input(cell.strategy, cell.symbol, campaign_input)
        cost = costs[cell.cost_variant_id]
        allocation = allocations[cell.allocation_variant_id]
        config = SpotBacktestConfig(
            starting_cash=starting_cash,
            maximum_allocation_per_position_pct=(allocation.maximum_allocation_per_position_pct),
            maximum_total_exposure_pct=allocation.maximum_total_exposure_pct,
            maximum_concurrent_positions=allocation.maximum_concurrent_positions,
            minimum_cash_reserve_pct=minimum_cash_reserve_pct,
            fee_pct=cost.fee_pct,
            slippage_pct=cost.slippage_pct,
            maximum_scale_entries=maximum_scale_entries,
            maximum_holding=maximum_holding,
        )
        completed.append(
            SpotCampaignResult(
                cell=cell,
                plan_id=plan.plan_id,
                assumptions_hash=plan.assumptions_hash,
                dataset_content_hash=datasets[cell.dataset_id].content_hash,
                backtest=run_spot_backtest(
                    config,
                    campaign_input.plans,
                    campaign_input.bars,
                ),
            )
        )
    return tuple(completed)


def _validate_cell_input(
    strategy: str,
    symbol: str,
    campaign_input: SpotCampaignInput,
) -> None:
    if any(order.strategy != strategy for order in campaign_input.plans):
        raise ValueError("spot campaign input strategy does not match frozen cell")
    if any(order.symbol != symbol for order in campaign_input.plans):
        raise ValueError("spot campaign input plan symbol does not match frozen cell")
    if any(bar.symbol != symbol for bar in campaign_input.bars):
        raise ValueError("spot campaign input bar symbol does not match frozen cell")
