"""Frozen deterministic planning for V2 spot baseline campaigns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from apex.spot_baseline.contracts import (
    SpotAllocationVariant,
    SpotBaselineCampaignPlan,
    SpotCampaignCell,
    SpotCostVariant,
    SpotDatasetReference,
    SpotDatasetRole,
)


def build_spot_baseline_plan(
    *,
    strategies: Sequence[str],
    symbols: Sequence[str],
    datasets: Sequence[SpotDatasetReference],
    cost_variants: Sequence[SpotCostVariant],
    allocation_variants: Sequence[SpotAllocationVariant],
    assumptions: Mapping[str, object],
) -> SpotBaselineCampaignPlan:
    """Build the full frozen campaign matrix and stable identities."""
    normalized_strategies = _unique_sorted(strategies, "strategies")
    normalized_symbols = _unique_sorted(symbols, "symbols")
    normalized_datasets = tuple(sorted(datasets, key=lambda item: item.dataset_id))
    normalized_costs = tuple(sorted(cost_variants, key=lambda item: item.identifier))
    normalized_allocations = tuple(sorted(allocation_variants, key=lambda item: item.identifier))
    if not normalized_datasets or not normalized_costs or not normalized_allocations:
        raise ValueError("spot baseline plan requires datasets and scenario variants")
    _require_unique([dataset.dataset_id for dataset in normalized_datasets], "dataset ids")
    _require_unique([variant.identifier for variant in normalized_costs], "cost variant ids")
    _require_unique(
        [variant.identifier for variant in normalized_allocations],
        "allocation variant ids",
    )
    roles = {dataset.role for dataset in normalized_datasets}
    missing_roles = set(SpotDatasetRole) - roles
    if missing_roles:
        raise ValueError(
            "spot baseline datasets are missing roles: "
            f"{sorted(role.value for role in missing_roles)}"
        )
    known_symbols = set(normalized_symbols)
    covered_symbols: set[str] = set()
    for dataset in normalized_datasets:
        unknown = set(dataset.symbols) - known_symbols
        if unknown:
            raise ValueError(
                f"dataset {dataset.dataset_id} contains unplanned symbols: {sorted(unknown)}"
            )
        covered_symbols.update(dataset.symbols)
    missing_symbols = known_symbols - covered_symbols
    if missing_symbols:
        raise ValueError(f"spot baseline datasets are missing symbols: {sorted(missing_symbols)}")

    assumptions_hash = _stable_hash(dict(assumptions))
    cells = tuple(
        SpotCampaignCell(
            strategy=strategy,
            symbol=symbol,
            dataset_id=dataset.dataset_id,
            dataset_role=dataset.role,
            cost_variant_id=cost.identifier,
            allocation_variant_id=allocation.identifier,
        )
        for strategy in normalized_strategies
        for symbol in normalized_symbols
        for dataset in normalized_datasets
        if symbol in dataset.symbols
        for cost in normalized_costs
        for allocation in normalized_allocations
    )
    payload = {
        "strategies": normalized_strategies,
        "symbols": normalized_symbols,
        "datasets": [
            {
                "dataset_id": dataset.dataset_id,
                "content_hash": dataset.content_hash,
                "role": dataset.role.value,
                "symbols": dataset.symbols,
            }
            for dataset in normalized_datasets
        ],
        "cost_variants": [
            {
                "identifier": variant.identifier,
                "fee_pct": variant.fee_pct,
                "slippage_pct": variant.slippage_pct,
            }
            for variant in normalized_costs
        ],
        "allocation_variants": [
            {
                "identifier": variant.identifier,
                "maximum_allocation_per_position_pct": (
                    variant.maximum_allocation_per_position_pct
                ),
                "maximum_total_exposure_pct": variant.maximum_total_exposure_pct,
                "maximum_concurrent_positions": variant.maximum_concurrent_positions,
            }
            for variant in normalized_allocations
        ],
        "cells": [cell.key for cell in cells],
        "assumptions_hash": assumptions_hash,
    }
    return SpotBaselineCampaignPlan(
        plan_id=_stable_hash(payload),
        strategies=normalized_strategies,
        symbols=normalized_symbols,
        datasets=normalized_datasets,
        cost_variants=normalized_costs,
        allocation_variants=normalized_allocations,
        cells=cells,
        assumptions_hash=assumptions_hash,
    )


def _unique_sorted(values: Sequence[str], label: str) -> tuple[str, ...]:
    normalized = tuple(sorted(value.strip() for value in values if value.strip()))
    if not normalized:
        raise ValueError(f"spot baseline plan requires {label}")
    _require_unique(list(normalized), label)
    return normalized


def _require_unique(values: Sequence[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"spot baseline {label} must be unique")


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
