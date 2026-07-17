"""Atomic orchestration for the complete historical evidence pipeline."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apex.backtesting.historical_edge_io import write_historical_edge_report
from apex.backtesting.historical_futures_edge import build_historical_futures_edge_report
from apex.backtesting.historical_futures_edge_validation import (
    build_historical_futures_edge_validation_report,
    write_historical_futures_edge_validation_report,
)
from apex.paper_trading import PaperTradeStore
from apex.validation.evidence_bundle import load_evidence_bundle
from apex.validation.forward_edge import (
    ForwardEdgePolicy,
    build_forward_edge_report,
    write_forward_edge_report,
)

PIPELINE_MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class EvidencePipelineResult:
    """Published historical evidence pipeline artifact locations."""

    pipeline_id: str
    output_directory: Path
    manifest_path: Path
    historical_edge_path: Path
    historical_validation_path: Path
    forward_validation_path: Path | None
    evidence_bundle_path: Path


def run_evidence_pipeline(
    *,
    result_path: Path,
    execution_manifest_path: Path,
    dimensions: Mapping[str, str],
    output_directory: Path,
    generated_at: datetime,
    paper_store_path: Path | None = None,
    forward_policy: ForwardEdgePolicy | None = None,
    maximum_evidence_age: timedelta | None = None,
    force: bool = False,
) -> EvidencePipelineResult:
    """Build and atomically publish historical evidence artifacts."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("evidence pipeline generation time must be timezone-aware")
    normalized_dimensions = _normalize_dimensions(dimensions)
    if maximum_evidence_age is not None and maximum_evidence_age <= timedelta(0):
        raise ValueError("maximum evidence age must be positive")
    if output_directory.exists() and not force:
        raise FileExistsError(f"refusing to replace evidence pipeline directory: {output_directory}")

    parent = output_directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{output_directory.name}.staging"
    backup = parent / f".{output_directory.name}.backup"
    _remove_path(staging)
    _remove_path(backup)
    staging.mkdir(parents=True)

    edge_path = staging / "historical-edge.json"
    historical_validation_path = staging / "historical-validation.json"
    forward_validation_path = staging / "forward-validation.json"
    bundle_path = staging / "evidence-bundle.json"
    manifest_path = staging / "pipeline-manifest.json"

    try:
        edge = build_historical_futures_edge_report(
            result_path=result_path,
            execution_manifest_path=execution_manifest_path,
            generated_at=generated_at,
        )
        write_historical_edge_report(edge_path, edge)

        historical_validation = build_historical_futures_edge_validation_report(
            edge_report_path=edge_path,
            generated_at=generated_at,
        )
        write_historical_futures_edge_validation_report(
            historical_validation_path,
            historical_validation,
        )

        published_forward_path: Path | None = None
        if paper_store_path is not None:
            forward = build_forward_edge_report(
                historical_validation_path=historical_validation_path,
                paper_trades=PaperTradeStore(paper_store_path).load(),
                generated_at=generated_at,
                policy=forward_policy,
            )
            write_forward_edge_report(forward_validation_path, forward)
            published_forward_path = forward_validation_path

        bundle = load_evidence_bundle(
            historical_validation_path=historical_validation_path,
            forward_validation_path=published_forward_path,
            dimensions=normalized_dimensions,
            as_of=generated_at,
            maximum_age=maximum_evidence_age,
        )
        _write_json(bundle_path, bundle.to_payload())

        artifact_hashes = {
            "historical_edge": _hash_file(edge_path),
            "historical_validation": _hash_file(historical_validation_path),
            **(
                {"forward_validation": _hash_file(forward_validation_path)}
                if published_forward_path is not None
                else {}
            ),
            "evidence_bundle": _hash_file(bundle_path),
        }
        identity = {
            "campaign_id": bundle.campaign_id,
            "dimensions": normalized_dimensions,
            "source_result_hash": _hash_file(result_path),
            "source_execution_manifest_hash": _hash_file(execution_manifest_path),
            "paper_store_hash": (
                _hash_file(paper_store_path) if paper_store_path is not None else None
            ),
            "artifact_hashes": artifact_hashes,
        }
        pipeline_id = f"n4-evidence-pipeline-{_hash_json(identity)[:24]}"
        manifest = {
            "schema_version": PIPELINE_MANIFEST_SCHEMA_VERSION,
            "pipeline_id": pipeline_id,
            "generated_at": generated_at.isoformat(),
            "campaign_id": bundle.campaign_id,
            "status": "completed",
            "dimensions": normalized_dimensions,
            "includes_forward_paper": published_forward_path is not None,
            "bundle_status": bundle.status.value,
            "sources": {
                "result_path": result_path.as_posix(),
                "execution_manifest_path": execution_manifest_path.as_posix(),
                "paper_store_path": (
                    paper_store_path.as_posix() if paper_store_path is not None else None
                ),
                "result_hash": identity["source_result_hash"],
                "execution_manifest_hash": identity[
                    "source_execution_manifest_hash"
                ],
                "paper_store_hash": identity["paper_store_hash"],
            },
            "artifacts": {
                "historical_edge": "historical-edge.json",
                "historical_validation": "historical-validation.json",
                "forward_validation": (
                    "forward-validation.json" if published_forward_path is not None else None
                ),
                "evidence_bundle": "evidence-bundle.json",
            },
            "artifact_hashes": artifact_hashes,
            "warnings": [
                "Pipeline completion does not prove profitability or live readiness.",
                "Funded eligibility still depends on exact-segment approval policy.",
            ],
        }
        _write_json(manifest_path, manifest)
        _publish_directory(staging, output_directory, backup, force=force)
    except Exception:
        _remove_path(staging)
        if backup.exists() and not output_directory.exists():
            backup.replace(output_directory)
        raise

    return EvidencePipelineResult(
        pipeline_id=pipeline_id,
        output_directory=output_directory,
        manifest_path=output_directory / manifest_path.name,
        historical_edge_path=output_directory / edge_path.name,
        historical_validation_path=output_directory / historical_validation_path.name,
        forward_validation_path=(
            output_directory / forward_validation_path.name
            if paper_store_path is not None
            else None
        ),
        evidence_bundle_path=output_directory / bundle_path.name,
    )


def _publish_directory(
    staging: Path,
    output: Path,
    backup: Path,
    *,
    force: bool,
) -> None:
    if output.exists():
        if not force:
            raise FileExistsError(f"refusing to replace evidence pipeline directory: {output}")
        output.replace(backup)
    try:
        staging.replace(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise
    _remove_path(backup)


def _normalize_dimensions(value: Mapping[str, str]) -> dict[str, str]:
    if not value or not all(
        isinstance(key, str) and isinstance(item, str) and key.strip() and item.strip()
        for key, item in value.items()
    ):
        raise ValueError("pipeline dimensions must be a non-empty string mapping")
    return dict(sorted((key.strip(), item.strip()) for key, item in value.items()))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    if reloaded != payload:
        raise ValueError(f"pipeline artifact changed after reload: {path}")


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
