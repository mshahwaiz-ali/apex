"""Deterministic persistence for historical signal-generation results."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.application.historical_signal_generation import (
    HistoricalSignalGenerationResult,
    HistoricalSignalRecord,
)
from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
)
from apex.historical_signals.persistence import (
    load_historical_signal_campaign_manifest,
    load_historical_signal_records,
)

HISTORICAL_SIGNAL_EXECUTION_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class HistoricalSignalExecutionManifest:
    """Audit manifest for one persisted historical signal-generation run."""

    campaign_id: str
    records_path: str
    records_hash: str
    configuration_hash: str
    total_records: int
    accepted_records: int
    rejected_records: int
    failed_records: int
    split_counts: tuple[tuple[str, int], ...]
    source_datasets: tuple[dict[str, object], ...]
    schema_version: int = HISTORICAL_SIGNAL_EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != HISTORICAL_SIGNAL_EXECUTION_SCHEMA_VERSION:
            raise ValueError("unsupported historical signal execution schema version")
        for value in (
            self.campaign_id,
            self.records_path,
        ):
            if not value.strip():
                raise ValueError("historical signal execution fields cannot be empty")
        for value in (
            self.records_hash,
            self.configuration_hash,
        ):
            if not _is_sha256(value):
                raise ValueError("historical signal execution hashes must be SHA-256")
        if self.total_records < 1:
            raise ValueError("historical signal execution requires records")
        if (
            min(
                self.accepted_records,
                self.rejected_records,
                self.failed_records,
            )
            < 0
        ):
            raise ValueError("historical signal execution counts cannot be negative")
        if self.accepted_records + self.rejected_records != self.total_records:
            raise ValueError(
                "historical signal accepted and rejected counts must equal total records"
            )
        if self.failed_records > self.rejected_records:
            raise ValueError("historical signal failures must be rejected records")
        if sum(count for _, count in self.split_counts) != self.total_records:
            raise ValueError("historical signal split counts must equal total records")
        if not self.source_datasets:
            raise ValueError("historical signal execution requires source datasets")

    def to_payload(self) -> dict[str, object]:
        """Return deterministic JSON-ready manifest content."""

        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "status": "completed",
            "records_path": self.records_path,
            "records_hash": self.records_hash,
            "configuration_hash": self.configuration_hash,
            "total_records": self.total_records,
            "accepted_records": self.accepted_records,
            "rejected_records": self.rejected_records,
            "failed_records": self.failed_records,
            "split_counts": {split: count for split, count in self.split_counts},
            "source_datasets": list(self.source_datasets),
        }


def hash_configuration_files(
    paths: tuple[Path, ...],
) -> str:
    """Hash ordered configuration paths and their exact byte content."""

    if not paths:
        raise ValueError("historical signal generation requires configuration files")

    canonical: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"configuration file does not exist: {path}")
        canonical.append(
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    return _hash_json(canonical)


def hash_historical_signal_records(
    records: tuple[HistoricalSignalRecord, ...],
) -> str:
    """Hash canonical record payloads in chronological order."""

    if not records:
        raise ValueError("historical signal record hashing requires records")
    return _hash_json([record.to_payload() for record in records])


def write_historical_signal_generation(
    *,
    inputs: HistoricalSignalCampaignInputs,
    result: HistoricalSignalGenerationResult,
    records_path: Path,
    execution_manifest_path: Path,
    configuration_paths: tuple[Path, ...],
) -> HistoricalSignalExecutionManifest:
    """Atomically persist records and a verified execution manifest."""

    if result.campaign_id != inputs.campaign_id:
        raise ValueError("historical signal result campaign does not match inputs")

    normalized_outputs = (
        records_path.resolve(strict=False),
        execution_manifest_path.resolve(strict=False),
    )
    if normalized_outputs[0] == normalized_outputs[1]:
        raise ValueError("historical signal output paths must be unique")

    existing = tuple(
        path
        for path in (
            records_path,
            execution_manifest_path,
        )
        if path.exists()
    )
    if existing:
        raise FileExistsError(
            f"historical signal generation refuses to overwrite existing artifact: {existing[0]}"
        )

    configuration_hash = hash_configuration_files(configuration_paths)
    records_hash = hash_historical_signal_records(result.records)

    split_counter = Counter(record.split.value for record in result.records)
    split_counts = tuple(sorted(split_counter.items()))

    failed_records = sum(record.failure_reason is not None for record in result.records)

    manifest = HistoricalSignalExecutionManifest(
        campaign_id=inputs.campaign_id,
        records_path=records_path.as_posix(),
        records_hash=records_hash,
        configuration_hash=configuration_hash,
        total_records=len(result.records),
        accepted_records=result.accepted_count,
        rejected_records=result.rejected_count,
        failed_records=failed_records,
        split_counts=split_counts,
        source_datasets=tuple(dataset.to_payload() for dataset in inputs.source_datasets),
    )

    created_paths: list[Path] = []
    temporary_paths: list[Path] = []

    try:
        records_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        records_temporary = records_path.with_suffix(records_path.suffix + ".tmp")
        temporary_paths.append(records_temporary)
        records_temporary.write_text(
            "".join(_canonical_json(record.to_payload()) + "\n" for record in result.records),
            encoding="utf-8",
        )
        records_temporary.replace(records_path)
        created_paths.append(records_path)

        reloaded_payloads = load_historical_signal_record_payloads(records_path)
        if _hash_json(reloaded_payloads) != records_hash:
            raise ValueError("historical signal record hash changed after reload")

        execution_manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        manifest_temporary = execution_manifest_path.with_suffix(
            execution_manifest_path.suffix + ".tmp"
        )
        temporary_paths.append(manifest_temporary)
        manifest_temporary.write_text(
            json.dumps(
                manifest.to_payload(),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest_temporary.replace(execution_manifest_path)
        created_paths.append(execution_manifest_path)

        loaded_manifest = load_historical_signal_execution_manifest(execution_manifest_path)
        if loaded_manifest != manifest:
            raise ValueError("historical signal execution manifest changed after reload")

        return manifest
    except Exception:
        for path in reversed(created_paths):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary_paths:
            with suppress(OSError):
                path.unlink(missing_ok=True)


def load_historical_signal_record_payloads(
    path: Path,
) -> tuple[dict[str, object], ...]:
    """Load JSONL records without weakening their canonical hash."""

    payloads: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise ValueError("historical signal records cannot contain blank lines")
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"historical signal record must be an object at line {line_number}")
        payloads.append(payload)

    if not payloads:
        raise ValueError("historical signal records file is empty")
    return tuple(payloads)


def load_historical_signal_execution_manifest(
    path: Path,
) -> HistoricalSignalExecutionManifest:
    """Load legacy or schema-v2 historical signal campaign metadata."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical signal execution payload must be an object")

    if "signal_campaign_id" in payload:
        return _load_schema_v2_signal_campaign(path)

    return _load_legacy_signal_execution_manifest(payload)


def _load_legacy_signal_execution_manifest(
    payload: dict[str, object],
) -> HistoricalSignalExecutionManifest:
    raw_split_counts = payload.get("split_counts")
    raw_sources = payload.get("source_datasets")
    if not isinstance(raw_split_counts, dict):
        raise ValueError("historical signal split counts must be an object")
    if not isinstance(raw_sources, list):
        raise ValueError("historical signal source datasets must be a list")

    sources: list[dict[str, object]] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            raise ValueError("historical signal source dataset must be an object")
        sources.append(item)

    return HistoricalSignalExecutionManifest(
        schema_version=_required_manifest_int(payload, "schema_version"),
        campaign_id=str(payload["campaign_id"]),
        records_path=str(payload["records_path"]),
        records_hash=str(payload["records_hash"]),
        configuration_hash=str(payload["configuration_hash"]),
        total_records=_required_manifest_int(payload, "total_records"),
        accepted_records=_required_manifest_int(payload, "accepted_records"),
        rejected_records=_required_manifest_int(payload, "rejected_records"),
        failed_records=_required_manifest_int(payload, "failed_records"),
        split_counts=tuple(
            sorted(
                (str(split), int(count))
                for split, count in raw_split_counts.items()
            )
        ),
        source_datasets=tuple(sources),
    )




def _required_manifest_int(
    payload: dict[str, object],
    key: str,
) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"historical signal {key} must be an integer")

    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(
            f"historical signal {key} must be an integer"
        ) from exc

    return result


def _load_schema_v2_signal_campaign(
    manifest_path: Path,
) -> HistoricalSignalExecutionManifest:
    manifest = load_historical_signal_campaign_manifest(manifest_path)
    records_path = _resolve_schema_v2_records_path(
        manifest_path=manifest_path,
        declared_path=Path(manifest.records_path),
    )
    records = load_historical_signal_records(
        records_path,
        symbol_order=manifest.symbol_order,
        expected_content_hash=manifest.records_content_hash,
    )
    payloads = tuple(record.to_payload() for record in records)

    source_datasets: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for record in records:
        for source in record.source_datasets:
            key = (
                record.symbol,
                source.timeframe,
                source.dataset_id,
                source.content_hash,
            )
            source_datasets[key] = {
                "symbol": record.symbol,
                "timeframe": source.timeframe,
                "dataset_id": source.dataset_id,
                "content_hash": source.content_hash,
                "signal_record_schema_version": record.schema_version,
            }

    accepted_records = sum(record.accepted for record in records)
    failed_records = sum(record.failure_reason is not None for record in records)
    return HistoricalSignalExecutionManifest(
        campaign_id=manifest.campaign_id,
        records_path=records_path.as_posix(),
        records_hash=_hash_json(payloads),
        configuration_hash=manifest.assumptions_hash,
        total_records=len(records),
        accepted_records=accepted_records,
        rejected_records=len(records) - accepted_records,
        failed_records=failed_records,
        split_counts=tuple(
            (split.value, count)
            for split, count in manifest.counts_by_split
        ),
        source_datasets=tuple(source_datasets[key] for key in sorted(source_datasets)),
    )


def _resolve_schema_v2_records_path(
    *,
    manifest_path: Path,
    declared_path: Path,
) -> Path:
    candidates = [declared_path]
    if not declared_path.is_absolute():
        candidates.append(manifest_path.parent / declared_path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError(
        f"historical signal records do not exist: {declared_path}"
    )


def _hash_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
