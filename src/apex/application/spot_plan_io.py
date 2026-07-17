"""Typed JSON boundary for canonical spot planning requests and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_planning import (
    SpotPlanningRequest,
    SpotPlanningResult,
    build_spot_plan,
)
from apex.config.spot import SpotProductConfig, load_spot_product_config
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_strategy import SpotStrategyCandidate

SPOT_PLAN_SCHEMA_VERSION = 1


class SpotPlanningInput(BaseModel):
    """Validated JSON input for one canonical spot plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: SpotStrategyCandidate
    account: SpotAccountInput
    current_price: float = Field(gt=0)
    support_price: float = Field(gt=0)
    resistance_price: float = Field(gt=0)
    deeper_support_price: float = Field(gt=0)
    recovery_entry_price: float = Field(gt=0)
    correlated_sector_exposure: float = Field(default=0.0, ge=0)

    def to_request(self) -> SpotPlanningRequest:
        """Convert the validated transport model into the application request."""

        return SpotPlanningRequest(
            candidate=self.candidate,
            account=self.account,
            current_price=self.current_price,
            support_price=self.support_price,
            resistance_price=self.resistance_price,
            deeper_support_price=self.deeper_support_price,
            recovery_entry_price=self.recovery_entry_price,
            correlated_sector_exposure=self.correlated_sector_exposure,
        )


def load_spot_planning_input(path: str | Path) -> SpotPlanningInput:
    """Load and validate a canonical spot planning input object."""

    loaded: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("spot planning input must contain a JSON object")
    return SpotPlanningInput.model_validate(cast(dict[str, Any], loaded))


def build_spot_plan_from_input(
    planning_input: SpotPlanningInput,
    *,
    config: SpotProductConfig,
) -> SpotPlanningResult:
    """Build a canonical spot plan from validated transport input."""

    return build_spot_plan(planning_input.to_request(), config=config)


def build_spot_plan_from_files(
    *,
    input_path: str | Path,
    config_path: str | Path,
) -> SpotPlanningResult:
    """Load configuration and input files, then build one canonical spot plan."""

    planning_input = load_spot_planning_input(input_path)
    config = load_spot_product_config(config_path)
    return build_spot_plan_from_input(planning_input, config=config)


def spot_planning_result_to_payload(result: SpotPlanningResult) -> dict[str, Any]:
    """Serialize a spot planning result without futures-only fields."""

    return {
        "schema_version": SPOT_PLAN_SCHEMA_VERSION,
        "entry_plan": result.entry_plan.model_dump(mode="json"),
        "stop_plan": result.stop_plan.model_dump(mode="json"),
        "position_plan": result.position_plan.model_dump(mode="json"),
        "target_plan": result.target_plan.model_dump(mode="json"),
        "lifecycle": result.lifecycle.model_dump(mode="json"),
        "warnings": [
            "spot planning output is research and paper-trading guidance only",
            "historical and forward-paper validation remain required",
        ],
    }


def write_spot_planning_result(path: str | Path, result: SpotPlanningResult) -> None:
    """Write a deterministic canonical spot planning payload."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = spot_planning_result_to_payload(result)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
