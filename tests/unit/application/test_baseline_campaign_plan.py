"""Tests for V2.1 frozen baseline campaign planning."""

from __future__ import annotations

import pytest

from apex.application.baseline_campaign_plan import (
    BaselineCampaignManifest,
    BaselineCampaignPlan,
    BaselineDatasetRef,
)
from apex.domain import RiskMode
from apex.strategies import StrategyType


def _dataset() -> BaselineDatasetRef:
    return BaselineDatasetRef(
        dataset_id="btc-bull-bear-v1",
        content_hash="abc123",
        symbols=("BTCUSDT", "ETHUSDT"),
        market_regimes=("bullish", "bearish", "ranging"),
    )


def _plan() -> BaselineCampaignPlan:
    return BaselineCampaignPlan(
        identifier="futures-baseline-v1",
        datasets=(_dataset(),),
        strategies=(StrategyType.TREND_PULLBACK, StrategyType.BREAKOUT_CONTINUATION),
        risk_modes=(RiskMode.STANDARD,),
        variant_ids=("baseline", "fee-stress"),
        fee_pct=0.04,
        slippage_pct=0.02,
    )


def test_plan_id_is_deterministic_and_serialized() -> None:
    first = _plan()
    second = _plan()

    assert first.plan_id == second.plan_id
    assert len(first.plan_id) == 64
    assert first.to_payload()["plan_id"] == first.plan_id


def test_plan_id_changes_when_execution_assumptions_change() -> None:
    first = _plan()
    second = BaselineCampaignPlan(
        identifier=first.identifier,
        datasets=first.datasets,
        strategies=first.strategies,
        risk_modes=first.risk_modes,
        variant_ids=first.variant_ids,
        fee_pct=first.fee_pct,
        slippage_pct=0.05,
    )

    assert first.plan_id != second.plan_id


def test_dataset_values_are_deduplicated_without_reordering() -> None:
    dataset = BaselineDatasetRef(
        dataset_id="fixture",
        content_hash="hash",
        symbols=("BTCUSDT", "BTCUSDT", "ETHUSDT"),
        market_regimes=("bullish", "bullish", "ranging"),
    )

    assert dataset.symbols == ("BTCUSDT", "ETHUSDT")
    assert dataset.market_regimes == ("bullish", "ranging")


def test_manifest_payload_orders_risk_modes_deterministically() -> None:
    manifest = BaselineCampaignManifest(
        plan=_plan(),
        campaign_ids_by_risk_mode={RiskMode.STANDARD: "campaign-standard"},
    )

    payload = manifest.to_payload()
    assert list(payload["campaign_ids_by_risk_mode"]) == ["STANDARD"]
    assert payload["plan"]["plan_id"] == manifest.plan.plan_id


def test_invalid_or_duplicate_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="dataset ids must be unique"):
        BaselineCampaignPlan(
            identifier="duplicate",
            datasets=(_dataset(), _dataset()),
            strategies=(StrategyType.TREND_PULLBACK,),
            risk_modes=(RiskMode.STANDARD,),
            variant_ids=("baseline",),
            fee_pct=0.04,
            slippage_pct=0.02,
        )

    with pytest.raises(ValueError, match="cannot be negative"):
        BaselineCampaignPlan(
            identifier="negative-cost",
            datasets=(_dataset(),),
            strategies=(StrategyType.TREND_PULLBACK,),
            risk_modes=(RiskMode.STANDARD,),
            variant_ids=("baseline",),
            fee_pct=-0.01,
            slippage_pct=0.02,
        )
