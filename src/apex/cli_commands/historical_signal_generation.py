"""CLI command for deterministic historical Apex signal generation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    HistoricalSignalExecutionManifest,
    generate_historical_signals,
    load_default_risk_config,
    write_historical_signal_generation,
)
from apex.backtesting import (
    load_historical_signal_campaign_inputs,
)
from apex.domain import MarketCategory


def register_historical_signal_generation_commands(
    dataset_app: typer.Typer,
) -> None:
    """Register the N4.7 historical signal-generation command."""

    @dataset_app.command("historical-signals-generate")
    def historical_signals_generate(
        plan_file: Annotated[
            Path,
            typer.Option(
                "--plan",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Frozen aligned dataset campaign plan.",
            ),
        ],
        dataset_execution_manifest: Annotated[
            Path,
            typer.Option(
                "--dataset-execution-manifest",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Verified aligned dataset execution manifest.",
            ),
        ],
        records_output: Annotated[
            Path,
            typer.Option(
                "--records-output",
                dir_okay=False,
                help="New JSONL output for historical decisions.",
            ),
        ],
        execution_manifest_output: Annotated[
            Path,
            typer.Option(
                "--execution-manifest-output",
                dir_okay=False,
                help="New historical signal execution manifest.",
            ),
        ],
        risk_config: Annotated[
            Path,
            typer.Option(
                "--risk-config",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ] = Path("config/risk.yaml"),
        configuration_files: Annotated[
            list[Path] | None,
            typer.Option(
                "--configuration-file",
                exists=True,
                dir_okay=False,
                readable=True,
                help=("Additional configuration file to hash. Repeat for every relevant file."),
            ),
        ] = None,
        candle_limit: Annotated[
            int,
            typer.Option(
                "--candle-limit",
                min=40,
                help="Closed candles exposed per timeframe and decision.",
            ),
        ] = 200,
        scanner_type: Annotated[
            MarketCategory,
            typer.Option(
                "--scanner-type",
                case_sensitive=False,
            ),
        ] = MarketCategory.NORMAL_MARKET,
    ) -> None:
        """Generate reproducible historical decisions using the live engine."""

        try:
            _validate_output_paths(
                records_output=records_output,
                execution_manifest_output=(execution_manifest_output),
            )
            inputs = load_historical_signal_campaign_inputs(
                plan_path=plan_file,
                execution_manifest_path=(dataset_execution_manifest),
            )
            risk = load_default_risk_config(risk_config)
            result = generate_historical_signals(
                inputs=inputs,
                candle_limit=candle_limit,
                risk_config=risk,
                scanner_type=scanner_type,
            )
            manifest = write_historical_signal_generation(
                inputs=inputs,
                result=result,
                records_path=records_output,
                execution_manifest_path=(execution_manifest_output),
                configuration_paths=_configuration_paths(
                    risk_config=risk_config,
                    additional=tuple(configuration_files or ()),
                ),
            )
        except (
            FileExistsError,
            FileNotFoundError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise typer.BadParameter(str(exc)) from exc

        _echo_completion(
            manifest=manifest,
            execution_manifest_output=(execution_manifest_output),
        )


def _configuration_paths(
    *,
    risk_config: Path,
    additional: tuple[Path, ...],
) -> tuple[Path, ...]:
    """Return unique configuration paths in deterministic order."""

    ordered = (risk_config, *additional)
    unique: list[Path] = []
    seen: set[Path] = set()

    for path in ordered:
        normalized = path.resolve(strict=False)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path)

    return tuple(unique)


def _validate_output_paths(
    *,
    records_output: Path,
    execution_manifest_output: Path,
) -> None:
    if records_output.resolve(strict=False) == execution_manifest_output.resolve(strict=False):
        raise ValueError(
            "historical signal records and execution manifest must use different paths"
        )


def _echo_completion(
    *,
    manifest: HistoricalSignalExecutionManifest,
    execution_manifest_output: Path,
) -> None:
    typer.echo(
        "HISTORICAL_SIGNALS_GENERATED "
        f"| campaign_id={manifest.campaign_id} "
        f"| total={manifest.total_records} "
        f"| accepted={manifest.accepted_records} "
        f"| rejected={manifest.rejected_records} "
        f"| failed={manifest.failed_records} "
        f"| records_hash={manifest.records_hash} "
        f"| configuration_hash={manifest.configuration_hash} "
        f"| records={manifest.records_path} "
        f"| manifest={execution_manifest_output}"
    )
