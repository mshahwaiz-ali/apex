"""CLI workflow for deterministic S10 empirical calibration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from apex.optimization import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    PerformanceSummary,
    StabilityPolicy,
    WalkForwardSplit,
    build_empirical_calibration_report,
    load_and_verify_empirical_calibration_report,
    performance_from_mapping,
    write_empirical_calibration_report,
)


def register_empirical_calibration_commands(optimize_app: typer.Typer) -> None:
    """Register the S10 empirical calibration command."""

    @optimize_app.command("empirical-calibrate")
    def empirical_calibrate(
        input_path: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        output_path: Annotated[
            Path,
            typer.Option("--output", dir_okay=False),
        ] = Path("data/optimization/empirical-calibration.json"),
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Select on train/validation, audit stability, then attach untouched final test."""

        try:
            payload = _load_object(input_path)
            split = WalkForwardSplit(**_mapping(payload, "split"))
            run_config_payload = _mapping(payload, "run_config")
            group = OptimizationGroup(str(run_config_payload["variable_group"]))
            run_config = OptimizationRunConfig(
                identifier=str(run_config_payload["identifier"]),
                variable_group=group,
                minimum_trades=int(run_config_payload.get("minimum_trades", 1)),
                minimum_expectancy_delta=float(
                    run_config_payload.get("minimum_expectancy_delta", 0.0)
                ),
                maximum_drawdown_increase_pct=float(
                    run_config_payload.get("maximum_drawdown_increase_pct", 0.0)
                ),
                require_profit_factor_not_worse=bool(
                    run_config_payload.get("require_profit_factor_not_worse", True)
                ),
                reject_symbol_dependency=bool(
                    run_config_payload.get("reject_symbol_dependency", True)
                ),
                maximum_symbol_trade_share=float(
                    run_config_payload.get("maximum_symbol_trade_share", 0.70)
                ),
                reject_strategy_dependency=bool(
                    run_config_payload.get("reject_strategy_dependency", False)
                ),
                maximum_strategy_trade_share=float(
                    run_config_payload.get("maximum_strategy_trade_share", 0.80)
                ),
                split=split,
            )
            parameter_payload = _mapping(payload, "parameter_set")
            parameter_set = CandidateParameterSet(
                identifier=str(parameter_payload["identifier"]),
                group=OptimizationGroup(str(parameter_payload["group"])),
                parameters=cast(
                    dict[str, str | int | float | bool],
                    _mapping(parameter_payload, "parameters"),
                ),
            )
            stability_payload = _mapping(payload, "stability_policy", required=False)
            stability_policy = StabilityPolicy(
                minimum_symbols=int(stability_payload.get("minimum_symbols", 2)),
                minimum_regimes=int(stability_payload.get("minimum_regimes", 1)),
                minimum_score_bands=int(stability_payload.get("minimum_score_bands", 1)),
                maximum_symbol_trade_share=float(
                    stability_payload.get("maximum_symbol_trade_share", 0.70)
                ),
                maximum_regime_trade_share=float(
                    stability_payload.get("maximum_regime_trade_share", 0.90)
                ),
                maximum_score_band_trade_share=float(
                    stability_payload.get("maximum_score_band_trade_share", 0.90)
                ),
            )
            report = build_empirical_calibration_report(
                split=split,
                run_config=run_config,
                parameter_set=parameter_set,
                train_baseline=performance_from_mapping(_mapping(payload, "train_baseline")),
                train_candidate=performance_from_mapping(_mapping(payload, "train_candidate")),
                validation_baseline=performance_from_mapping(
                    _mapping(payload, "validation_baseline")
                ),
                validation_candidate=performance_from_mapping(
                    _mapping(payload, "validation_candidate")
                ),
                final_test_baseline=_optional_performance(payload, "final_test_baseline"),
                final_test_candidate=_optional_performance(payload, "final_test_candidate"),
                stability_policy=stability_policy,
            )
            write_empirical_calibration_report(report, output_path, force=force)
            verified = load_and_verify_empirical_calibration_report(output_path)
        except (FileExistsError, KeyError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "EMPIRICAL_CALIBRATION_COMPLETED "
            f"| selected={verified.payload['selected_for_final_test_audit']} "
            f"| report_hash={verified.report_sha256} "
            f"| output={output_path}"
        )


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("empirical calibration input must be a JSON object")
    return cast(dict[str, Any], value)


def _mapping(
    container: dict[str, Any],
    key: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    value = container.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, dict) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"empirical calibration field must be an object: {key}")
    return cast(dict[str, Any], value)


def _optional_performance(
    container: dict[str, Any],
    key: str,
) -> PerformanceSummary | None:
    value = container.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"empirical calibration field must be an object: {key}")
    return performance_from_mapping(cast(dict[str, Any], value))
