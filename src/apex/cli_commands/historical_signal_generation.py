"""CLI command for deterministic historical signal campaign generation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import typer

from apex.historical_signals import (
    HistoricalSignalCampaignManifest,
    generate_and_persist_historical_signal_campaign,
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,
)


def register_historical_signal_generation_commands(
    dataset_app: typer.Typer,
) -> None:
    """Register the N4.6.3 historical signal campaign command."""

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
        assumptions_file: Annotated[
            Path,
            typer.Option(
                "--assumptions",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Deterministic JSON object describing replay assumptions.",
            ),
        ],
        records_output: Annotated[
            Path,
            typer.Option(
                "--records-output",
                dir_okay=False,
                help="New schema-v2 historical signal JSONL output.",
            ),
        ],
        manifest_output: Annotated[
            Path,
            typer.Option(
                "--manifest-output",
                dir_okay=False,
                help="New completed historical signal campaign manifest.",
            ),
        ],
        candle_limit: Annotated[
            int,
            typer.Option(
                "--candle-limit",
                min=40,
                help="Closed candles exposed per timeframe and decision.",
            ),
        ] = 200,
    ) -> None:
        """Generate and atomically persist one verified historical signal campaign."""

        try:
            _validate_output_paths(
                records_output=records_output,
                manifest_output=manifest_output,
            )
            assumptions = _load_assumptions(assumptions_file)
            manifest = generate_and_persist_historical_signal_campaign(
                plan_path=plan_file,
                execution_manifest_path=dataset_execution_manifest,
                records_path=records_output,
                manifest_path=manifest_output,
                assumptions=assumptions,
                candle_limit=candle_limit,
            )
            verified_manifest = load_historical_signal_campaign_manifest(manifest_output)
            records = load_historical_signal_records(
                records_output,
                symbol_order=verified_manifest.symbol_order,
                expected_content_hash=verified_manifest.records_content_hash,
            )
            if verified_manifest != manifest:
                raise ValueError("historical signal campaign manifest changed after CLI reload")
            if len(records) != verified_manifest.record_count:
                raise ValueError("historical signal record count changed after CLI reload")
        except (
            FileExistsError,
            FileNotFoundError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise typer.BadParameter(str(exc)) from exc

        _echo_completion(
            manifest=verified_manifest,
            records_output=records_output,
            manifest_output=manifest_output,
            accepted_count=sum(record.accepted for record in records),
            rejected_count=sum(not record.accepted for record in records),
        )


def _validate_output_paths(
    *,
    records_output: Path,
    manifest_output: Path,
) -> None:
    if records_output.resolve(strict=False) == manifest_output.resolve(strict=False):
        raise ValueError("historical signal records and manifest output paths must differ")


def _load_assumptions(path: Path) -> Mapping[str, object]:
    """Load one deterministic assumptions object without weakening its types."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical signal assumptions must be a JSON object")
    return {str(key): value for key, value in payload.items()}


def _echo_completion(
    *,
    manifest: HistoricalSignalCampaignManifest,
    records_output: Path,
    manifest_output: Path,
    accepted_count: int,
    rejected_count: int,
) -> None:
    counts = {split.value: count for split, count in manifest.counts_by_split}
    typer.echo(
        "HISTORICAL_SIGNAL_CAMPAIGN_COMPLETED "
        f"| signal_campaign_id={manifest.signal_campaign_id} "
        f"| campaign_id={manifest.campaign_id} "
        f"| plan_id={manifest.dataset_campaign_plan_id} "
        f"| execution_id={manifest.dataset_campaign_execution_id} "
        f"| assumptions_hash={manifest.assumptions_hash} "
        f"| total={manifest.record_count} "
        f"| accepted={accepted_count} "
        f"| rejected={rejected_count} "
        f"| train={counts['train']} "
        f"| validation={counts['validation']} "
        f"| final_test={counts['final_test']} "
        f"| records={records_output} "
        f"| manifest={manifest_output}"
    )
