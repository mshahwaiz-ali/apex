"""Deterministic V2 baseline campaign planning and manifest hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from apex.domain import RiskMode
from apex.strategies import StrategyType

BASELINE_CAMPAIGN_PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BaselineDatasetRef:
    """One curated historical dataset included in a baseline campaign."""

    dataset_id: str
    content_hash: str
    symbols: tuple[str, ...]
    market_regimes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.content_hash.strip():
            raise ValueError("dataset id and content hash are required")
        if not self.symbols or any(not symbol.strip() for symbol in self.symbols):
            raise ValueError("baseline dataset requires non-empty symbols")
        if not self.market_regimes or any(not regime.strip() for regime in self.market_regimes):
            raise ValueError("baseline dataset requires non-empty market regimes")
        object.__setattr__(self, "symbols", tuple(dict.fromkeys(self.symbols)))
        object.__setattr__(self, "market_regimes", tuple(dict.fromkeys(self.market_regimes)))


@dataclass(frozen=True, slots=True)
class BaselineCampaignPlan:
    """Frozen empirical campaign scope before any baseline result is selected."""

    identifier: str
    datasets: tuple[BaselineDatasetRef, ...]
    strategies: tuple[StrategyType, ...]
    risk_modes: tuple[RiskMode, ...]
    variant_ids: tuple[str, ...]
    fee_pct: float
    slippage_pct: float

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("baseline campaign identifier cannot be empty")
        for name, values in (
            ("datasets", self.datasets),
            ("strategies", self.strategies),
            ("risk modes", self.risk_modes),
            ("variant ids", self.variant_ids),
        ):
            if not values:
                raise ValueError(f"baseline campaign requires {name}")
        if len({dataset.dataset_id for dataset in self.datasets}) != len(self.datasets):
            raise ValueError("baseline dataset ids must be unique")
        if len(set(self.strategies)) != len(self.strategies):
            raise ValueError("baseline strategies must be unique")
        if len(set(self.risk_modes)) != len(self.risk_modes):
            raise ValueError("baseline risk modes must be unique")
        if len(set(self.variant_ids)) != len(self.variant_ids):
            raise ValueError("baseline variant ids must be unique")
        if self.fee_pct < 0.0 or self.slippage_pct < 0.0:
            raise ValueError("baseline execution costs cannot be negative")

    @property
    def plan_id(self) -> str:
        return _stable_hash(self.to_payload(include_plan_id=False))

    def to_payload(self, *, include_plan_id: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": BASELINE_CAMPAIGN_PLAN_SCHEMA_VERSION,
            "identifier": self.identifier,
            "datasets": [
                {
                    "dataset_id": dataset.dataset_id,
                    "content_hash": dataset.content_hash,
                    "symbols": list(dataset.symbols),
                    "market_regimes": list(dataset.market_regimes),
                }
                for dataset in self.datasets
            ],
            "strategies": [strategy.value for strategy in self.strategies],
            "risk_modes": [mode.value for mode in self.risk_modes],
            "variant_ids": list(self.variant_ids),
            "execution_costs": {
                "fee_pct": self.fee_pct,
                "slippage_pct": self.slippage_pct,
            },
        }
        if include_plan_id:
            payload["plan_id"] = self.plan_id
        return payload


@dataclass(frozen=True, slots=True)
class BaselineCampaignManifest:
    """Immutable binding between a frozen plan and completed campaign ids."""

    plan: BaselineCampaignPlan
    campaign_ids_by_risk_mode: dict[RiskMode, str]

    def __post_init__(self) -> None:
        if set(self.campaign_ids_by_risk_mode) != set(self.plan.risk_modes):
            raise ValueError("manifest campaign ids must cover every planned risk mode exactly")
        if any(not value.strip() for value in self.campaign_ids_by_risk_mode.values()):
            raise ValueError("manifest campaign ids cannot be empty")
        object.__setattr__(
            self,
            "campaign_ids_by_risk_mode",
            MappingProxyType(dict(self.campaign_ids_by_risk_mode)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": BASELINE_CAMPAIGN_PLAN_SCHEMA_VERSION,
            "plan": self.plan.to_payload(),
            "campaign_ids_by_risk_mode": {
                mode.value: self.campaign_ids_by_risk_mode[mode]
                for mode in sorted(self.campaign_ids_by_risk_mode, key=lambda item: item.value)
            },
        }


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
