"""Strict JSON boundary for provider-independent spot orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from apex.application.spot_analysis import (
    SpotAnalysisResult,
    spot_analysis_result_to_payload,
)
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    analyze_spot_orchestration,
)
from apex.config.spot import SpotProductConfig, load_spot_product_config
from apex.config.spot_strategies import SpotStrategyConfig, load_spot_strategy_config

DEFAULT_SPOT_CONFIG_PATH = Path("config/spot.yaml")
DEFAULT_SPOT_STRATEGY_CONFIG_PATH = Path("config/spot_strategies.yaml")


def load_spot_orchestration_input(path: str | Path) -> SpotOrchestrationInput:
    """Load and strictly validate one canonical orchestration JSON object."""

    loaded: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("spot orchestration input must contain a JSON object")
    return SpotOrchestrationInput.model_validate(cast(dict[str, Any], loaded))


def analyze_spot_orchestration_input(
    input_model: SpotOrchestrationInput,
    *,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
) -> SpotAnalysisResult:
    """Run the canonical orchestration bridge from validated input."""

    return analyze_spot_orchestration(
        input_model,
        product_config=product_config,
        strategy_config=strategy_config,
    )


def analyze_spot_orchestration_from_files(
    *,
    input_path: str | Path,
    product_config_path: str | Path = DEFAULT_SPOT_CONFIG_PATH,
    strategy_config_path: str | Path = DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
) -> SpotAnalysisResult:
    """Load configs and strict input, then run provider-independent orchestration."""

    input_model = load_spot_orchestration_input(input_path)
    product_config = load_spot_product_config(product_config_path)
    strategy_config = load_spot_strategy_config(strategy_config_path)
    return analyze_spot_orchestration_input(
        input_model,
        product_config=product_config,
        strategy_config=strategy_config,
    )


def write_spot_orchestration_result(
    path: str | Path,
    result: SpotAnalysisResult,
) -> None:
    """Write the same deterministic payload emitted by the CLI."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(spot_analysis_result_to_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
