"""Historical research campaign CLI command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from apex.application import bootstrap
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.backtest_output import render_campaign
from apex.presentation.terminal import emit_terminal
from apex.research.campaign import (
    ArchiveSpec,
    CampaignConfig,
    CampaignManifest,
    PublicDataImporter,
    latest_complete_utc_months,
    write_manifest,
)
from apex.research.training import train_campaign_models


def register_research_commands(app: typer.Typer) -> None:
    """Register historical research workflows under a dedicated command group."""

    research_app = typer.Typer(
        help="Prepare, verify, and optionally train on historical public market datasets.",
        no_args_is_help=True,
    )

    @research_app.command("campaign")
    def campaign(
        start: Annotated[str | None, typer.Option("--start", help="UTC month/date start.")] = None,
        end: Annotated[str | None, typer.Option("--end", help="UTC month/date end.")] = None,
        symbols_file: Annotated[
            Path | None,
            typer.Option("--symbols-file", exists=True, dir_okay=False),
        ] = None,
        dataset_dir: Annotated[
            Path,
            typer.Option("--dataset-dir", file_okay=False),
        ] = Path("data/research/binance_um"),
        download_missing: Annotated[bool, typer.Option("--download-missing")] = False,
        train_model: Annotated[bool, typer.Option("--train-model")] = False,
        report_file: Annotated[
            Path | None,
            typer.Option(
                "--report-file",
                help="Write the complete structured campaign payload to this JSON file.",
            ),
        ] = None,
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
        config_dir: Annotated[
            Path,
            typer.Option(
                "--config-dir",
                exists=True,
                file_okay=False,
                help="Configuration directory containing Apex YAML settings.",
            ),
        ] = Path("config"),
    ) -> None:
        """Prepare and verify a point-in-time historical research campaign."""

        output_mode = normalize_cli_output_mode(output)
        bootstrap(config_dir)
        payload = _run_public_data_campaign(
            dataset_dir=dataset_dir,
            symbols_file=symbols_file,
            start=start,
            end=end,
            download_missing=download_missing,
            train_model=train_model,
        )
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
            )
        _emit(payload, render_campaign(payload), output_mode)

    app.add_typer(
        research_app,
        name="research",
        rich_help_panel="Research",
    )


def _run_public_data_campaign(
    *,
    dataset_dir: Path,
    symbols_file: Path | None,
    start: str | None,
    end: str | None,
    download_missing: bool,
    train_model: bool,
) -> dict[str, Any]:
    months = latest_complete_utc_months(datetime.now(UTC), 24)
    if start is not None:
        months = tuple(month for month in months if month >= start[:7])
    if end is not None:
        months = tuple(month for month in months if month <= end[:7])
    if not months:
        raise typer.BadParameter("campaign date range contains no complete UTC months")
    universe_path = symbols_file or dataset_dir / "universe_by_month.json"
    if not universe_path.exists():
        if not download_missing:
            raise typer.BadParameter(
                "point-in-time universe is absent; use --download-missing to build it "
                "from trailing Binance 1d quote volume"
            )
        with PublicDataImporter(CampaignConfig(dataset_dir=dataset_dir)) as importer:
            universe, universe_missing = importer.build_dynamic_universe(months, limit=30)
        universe_path.parent.mkdir(parents=True, exist_ok=True)
        universe_path.write_text(
            json.dumps({key: list(value) for key, value in universe.items()}, indent=2) + "\n"
        )
    else:
        raw_universe = json.loads(universe_path.read_text())
        universe_missing = {}
        if isinstance(raw_universe, list):
            universe = {
                month: tuple(str(item).upper() for item in raw_universe) for month in months
            }
        elif isinstance(raw_universe, dict):
            universe = {
                month: tuple(str(item).upper() for item in raw_universe.get(month, ()))[:30]
                for month in months
            }
        else:
            raise typer.BadParameter("symbols file must be a JSON list or month-to-symbol mapping")
    files: dict[str, str] = {}
    missing: dict[str, str] = dict(universe_missing)
    if download_missing:
        with PublicDataImporter(CampaignConfig(dataset_dir=dataset_dir)) as importer:
            for month in months:
                for symbol_name in universe[month]:
                    for data_type in ("klines", "fundingRate", "aggTrades"):
                        spec = ArchiveSpec(
                            symbol_name,
                            month,
                            data_type=data_type,
                            timeframe="1m" if data_type == "klines" else None,
                        )
                        try:
                            path, checksum = importer.download(spec)
                            files[str(path.relative_to(dataset_dir))] = checksum
                        except (httpx.HTTPError, OSError, ValueError) as exc:
                            missing[f"{month}:{symbol_name}:{data_type}"] = (
                                f"{type(exc).__name__}: {exc}"
                            )
    manifest = CampaignManifest(
        schema_version=1,
        created_at=datetime.now(UTC).isoformat(),
        complete_months=months,
        universe_by_month=universe,
        files=files,
        missing=missing,
    )
    manifest_path = dataset_dir / "campaign_manifest.json"
    write_manifest(manifest_path, manifest)
    training_result = train_campaign_models(dataset_dir) if train_model else None
    unique_symbols = sorted({symbol for values in universe.values() for symbol in values})
    return {
        "schema_version": 1,
        "campaign": True,
        "months": list(months),
        "date_range": {"start": months[0], "end": months[-1]},
        "dataset_dir": str(dataset_dir),
        "universe_path": str(universe_path),
        "universe_size": 30,
        "symbol_count": len(unique_symbols),
        "symbols": unique_symbols,
        "universe_by_month": {month: list(symbols) for month, symbols in universe.items()},
        "verified_file_count": len(files),
        "verified_files": dict(sorted(files.items())),
        "missing_file_count": len(missing),
        "missing_files": dict(sorted(missing.items())),
        "manifest": str(manifest_path),
        "manifest_hash": manifest.checksum,
        "manifest_schema_version": manifest.schema_version,
        "train_model_requested": train_model,
        "model_training": training_result if train_model else "not requested",
        "artifacts": {
            "dataset_dir": str(dataset_dir),
            "universe": str(universe_path),
            "manifest": str(manifest_path),
        },
        "calibration_authoritative": False,
    }


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    emit_terminal(text)


__all__ = ["register_research_commands"]
