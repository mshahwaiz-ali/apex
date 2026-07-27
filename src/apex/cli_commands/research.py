"""Historical research campaign CLI command."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from apex.application import bootstrap
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.backtest_output import render_campaign
from apex.presentation.terminal import emit_terminal
from apex.research.campaign import (
    SUPPORTED_MONTHLY_DATA_TYPES,
    ArchiveSpec,
    CampaignConfig,
    CampaignManifest,
    PublicDataImporter,
    latest_complete_utc_months,
    write_manifest,
)
from apex.research.evaluation import (
    evaluate_walk_forward_campaign,
    load_evaluation_outcomes,
    write_evaluation_report,
)
from apex.research.experiment import (
    default_experiment_manifest,
    load_experiment_manifest,
    write_experiment_manifest,
)
from apex.research.precision import export_training_rows
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
        data_types: Annotated[
            str,
            typer.Option(
                "--data-types",
                help=(
                    "Comma-separated monthly archives: klines, fundingRate, aggTrades, "
                    "markPriceKlines, indexPriceKlines, premiumIndexKlines."
                ),
            ),
        ] = "klines,fundingRate,aggTrades",
        include_daily_metrics: Annotated[
            bool,
            typer.Option(
                "--include-daily-metrics",
                help="Download checksum-verified daily 5-minute OI/ratio archives.",
            ),
        ] = False,
        experiment_spec: Annotated[
            Path | None,
            typer.Option(
                "--experiment-spec",
                exists=True,
                dir_okay=False,
                help="Optional versioned walk-forward experiment manifest.",
            ),
        ] = None,
        outcomes_file: Annotated[
            Path | None,
            typer.Option(
                "--outcomes-file",
                exists=True,
                dir_okay=False,
                help="Optional JSONL outcomes for purged walk-forward evaluation.",
            ),
        ] = None,
        feature_snapshots_file: Annotated[
            Path | None,
            typer.Option(
                "--feature-snapshots-file",
                exists=True,
                dir_okay=False,
                help="Decision-time CandidateFeatureSnapshot JSONL exported by archive replay.",
            ),
        ] = None,
        candidate_outcomes_file: Annotated[
            Path | None,
            typer.Option(
                "--candidate-outcomes-file",
                exists=True,
                dir_okay=False,
                help="Separate resolved CandidateOutcomeLabel JSONL from archive replay.",
            ),
        ] = None,
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
            data_types=data_types,
            include_daily_metrics=include_daily_metrics,
            experiment_spec=experiment_spec,
            outcomes_file=outcomes_file,
            feature_snapshots_file=feature_snapshots_file,
            candidate_outcomes_file=candidate_outcomes_file,
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
    data_types: str = "klines,fundingRate,aggTrades",
    include_daily_metrics: bool = False,
    experiment_spec: Path | None = None,
    outcomes_file: Path | None = None,
    feature_snapshots_file: Path | None = None,
    candidate_outcomes_file: Path | None = None,
) -> dict[str, Any]:
    months = latest_complete_utc_months(datetime.now(UTC), 24)
    if start is not None:
        months = tuple(month for month in months if month >= start[:7])
    if end is not None:
        months = tuple(month for month in months if month <= end[:7])
    if not months:
        raise typer.BadParameter("campaign date range contains no complete UTC months")
    selected_data_types = _parse_campaign_data_types(data_types)
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
        with PublicDataImporter(
            CampaignConfig(dataset_dir=dataset_dir, data_types=selected_data_types)
        ) as importer:
            for month in months:
                for symbol_name in universe[month]:
                    for data_type in selected_data_types:
                        spec = ArchiveSpec(
                            symbol_name,
                            month,
                            data_type=data_type,
                            timeframe=(
                                "1m"
                                if data_type == "klines" or data_type.endswith("Klines")
                                else None
                            ),
                        )
                        try:
                            path, checksum = importer.download(spec)
                            files[str(path.relative_to(dataset_dir))] = checksum
                        except (httpx.HTTPError, OSError, ValueError) as exc:
                            missing[f"{month}:{symbol_name}:{data_type}"] = (
                                f"{type(exc).__name__}: {exc}"
                            )
            if include_daily_metrics:
                for date in _complete_utc_dates(months):
                    month = date[:7]
                    for symbol_name in universe.get(month, ()):
                        spec = ArchiveSpec(
                            symbol_name,
                            date,
                            data_type="metrics",
                            timeframe=None,
                        )
                        try:
                            path, checksum = importer.download(spec)
                            files[str(path.relative_to(dataset_dir))] = checksum
                        except (httpx.HTTPError, OSError, ValueError) as exc:
                            missing[f"{date}:{symbol_name}:metrics"] = (
                                f"{type(exc).__name__}: {exc}"
                            )
    manifest = CampaignManifest(
        schema_version=2,
        created_at=datetime.now(UTC).isoformat(),
        complete_months=months,
        universe_by_month=universe,
        files=files,
        missing=missing,
    )
    manifest_path = dataset_dir / "campaign_manifest.json"
    write_manifest(manifest_path, manifest)
    if (feature_snapshots_file is None) != (candidate_outcomes_file is None):
        raise typer.BadParameter(
            "feature snapshots and candidate outcomes must be provided together"
        )
    feature_export = (
        export_training_rows(
            feature_snapshots_file,
            candidate_outcomes_file,
            dataset_dir / "feature_rows.jsonl",
        )
        if feature_snapshots_file is not None and candidate_outcomes_file is not None
        else None
    )
    training_result = train_campaign_models(dataset_dir) if train_model else None
    unique_symbols = sorted({symbol for values in universe.values() for symbol in values})
    experiment = (
        load_experiment_manifest(experiment_spec)
        if experiment_spec is not None
        else default_experiment_manifest(
            dataset_fingerprint=manifest.checksum,
            symbols=tuple(unique_symbols),
        )
    )
    experiment_path = dataset_dir / "experiment_manifest.json"
    write_experiment_manifest(experiment_path, experiment)
    experiment_dataset_match = experiment.dataset_fingerprint == manifest.checksum
    evaluation_report: dict[str, Any] | None = None
    evaluation_path: Path | None = None
    if outcomes_file is not None:
        if not experiment_dataset_match:
            evaluation_report = {
                "available": False,
                "reason": "experiment dataset fingerprint does not match campaign manifest",
                "promotion": {
                    "promoted": False,
                    "authority": "research_only",
                    "failed_gates": ["dataset fingerprint mismatch"],
                },
            }
        else:
            try:
                evaluation_report = evaluate_walk_forward_campaign(
                    load_evaluation_outcomes(outcomes_file),
                    experiment,
                )
            except ValueError as exc:
                evaluation_report = {
                    "available": False,
                    "reason": str(exc),
                    "promotion": {
                        "promoted": False,
                        "authority": "research_only",
                        "failed_gates": [str(exc)],
                    },
                }
        evaluation_path = dataset_dir / "evaluation_report.json"
        write_evaluation_report(evaluation_path, evaluation_report)
    return {
        "schema_version": 6,
        "legacy_schema_version": 1,
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
        "requested_monthly_data_types": list(selected_data_types),
        "daily_metrics_requested": include_daily_metrics,
        "historical_evidence_coverage": _historical_evidence_coverage(
            files,
            missing,
        ),
        "missing_file_count": len(missing),
        "missing_files": dict(sorted(missing.items())),
        "manifest": str(manifest_path),
        "manifest_hash": manifest.checksum,
        "manifest_schema_version": manifest.schema_version,
        "evaluation_manifest": experiment.as_payload(),
        "evaluation_manifest_path": str(experiment_path),
        "evaluation_manifest_dataset_match": experiment_dataset_match,
        "evaluation_report": (
            evaluation_report
            if evaluation_report is not None
            else {
                "available": False,
                "reason": "no outcomes file supplied",
                "promotion": {
                    "promoted": False,
                    "authority": "research_only",
                },
            }
        ),
        "train_model_requested": train_model,
        "model_training": training_result if train_model else "not requested",
        "candidate_feature_export": (
            feature_export
            if feature_export is not None
            else {
                "available": False,
                "reason": "feature snapshots and candidate outcomes were not supplied",
            }
        ),
        "artifacts": {
            "dataset_dir": str(dataset_dir),
            "universe": str(universe_path),
            "manifest": str(manifest_path),
            "experiment_manifest": str(experiment_path),
            "evaluation_report": (None if evaluation_path is None else str(evaluation_path)),
        },
        "calibration_authoritative": False,
        "metric_authority": {
            "calibration": "non_authoritative_until_untouched_outcomes",
            "promotion": "research_only",
        },
    }


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    emit_terminal(text)


def _parse_campaign_data_types(value: str) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
    if not selected:
        raise typer.BadParameter("at least one campaign data type is required")
    unsupported = set(selected).difference(SUPPORTED_MONTHLY_DATA_TYPES)
    if unsupported:
        raise typer.BadParameter(
            f"unsupported monthly data types: {', '.join(sorted(unsupported))}"
        )
    return selected


def _complete_utc_dates(
    months: tuple[str, ...],
    *,
    as_of: datetime | None = None,
) -> tuple[str, ...]:
    today = (as_of or datetime.now(UTC)).date()
    dates: list[str] = []
    for month in months:
        cursor = datetime.fromisoformat(f"{month}-01T00:00:00+00:00")
        if cursor.month == 12:
            boundary = cursor.replace(year=cursor.year + 1, month=1)
        else:
            boundary = cursor.replace(month=cursor.month + 1)
        while cursor < boundary and cursor.date() < today:
            dates.append(cursor.date().isoformat())
            cursor += timedelta(days=1)
    return tuple(dates)


def _historical_evidence_coverage(
    files: Mapping[str, str],
    missing: Mapping[str, str],
) -> dict[str, object]:
    counts = {
        data_type: sum(1 for path in files if path.split("/", maxsplit=1)[0] == data_type)
        for data_type in (*sorted(SUPPORTED_MONTHLY_DATA_TYPES), "metrics")
    }
    return {
        "verified_archives_by_type": counts,
        "funding_events": "available" if counts["fundingRate"] else "unavailable",
        "aggregate_taker_flow": "available" if counts["aggTrades"] else "unavailable",
        "open_interest_metrics": "available" if counts["metrics"] else "unavailable",
        "mark_price_lineage": "available" if counts["markPriceKlines"] else "unavailable",
        "index_price_lineage": "available" if counts["indexPriceKlines"] else "unavailable",
        "premium_index_lineage": ("available" if counts["premiumIndexKlines"] else "unavailable"),
        "contract_metadata_history": {
            "available": False,
            "reason": "point-in-time exchange-info snapshots were not supplied",
        },
        "missing_archive_count": len(missing),
    }


__all__ = ["register_research_commands"]
