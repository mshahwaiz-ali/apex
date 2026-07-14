"""Contracts and persistence for deterministic historical signal campaigns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION: Final = 1


class HistoricalSignalSplitRole(StrEnum):
    """Frozen dataset role used to generate one historical decision."""

    TRAIN = "train"
    VALIDATION = "validation"
    FINAL_TEST = "final_test"


@dataclass(frozen=True, slots=True)
class HistoricalSignalDatasetRef:
    """Immutable source-dataset identity for one timeframe."""

    timeframe: str
    dataset_id: str
    content_hash: str
    path: str

    def __post_init__(self) -> None:
        if not self.timeframe.strip() or not self.dataset_id.strip() or not self.path.strip():
            raise ValueError("historical signal dataset reference fields cannot be empty")
        if not _is_sha256(self.content_hash):
            raise ValueError("historical signal dataset hash must be SHA-256")

    def to_payload(self) -> dict[str, object]:
        return {
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "content_hash": self.content_hash,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalRecord:
    """One frozen no-lookahead analysis decision."""

    record_id: str
    campaign_id: str
    symbol: str
    split_role: HistoricalSignalSplitRole
    decision_time: datetime
    replay_timeframe: str
    source_datasets: tuple[HistoricalSignalDatasetRef, ...]
    analysis: dict[str, object]

    def __post_init__(self) -> None:
        for value in (self.record_id, self.campaign_id, self.symbol, self.replay_timeframe):
            if not value.strip():
                raise ValueError("historical signal record fields cannot be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("historical signal decision time must be timezone-aware")
        if not self.source_datasets:
            raise ValueError("historical signal record requires source datasets")
        if len({item.timeframe for item in self.source_datasets}) != len(self.source_datasets):
            raise ValueError("historical signal source timeframes must be unique")

    def to_payload(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "campaign_id": self.campaign_id,
            "symbol": self.symbol,
            "split_role": self.split_role.value,
            "decision_time": self.decision_time.isoformat(),
            "replay_timeframe": self.replay_timeframe,
            "source_datasets": [item.to_payload() for item in self.source_datasets],
            "analysis": self.analysis,
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalCampaignManifest:
    """Compact audit manifest for a completed historical signal campaign."""

    campaign_id: str
    dataset_campaign_id: str
    execution_manifest_path: str
    records_path: str
    replay_timeframe: str
    analysis_timeframes: tuple[str, ...]
    candle_limit: int
    decision_interval_candles: int
    record_count: int
    train_count: int
    validation_count: int
    final_test_count: int
    records_hash: str
    schema_version: int = HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for value in (
            self.campaign_id,
            self.dataset_campaign_id,
            self.execution_manifest_path,
            self.records_path,
            self.replay_timeframe,
        ):
            if not value.strip():
                raise ValueError("historical signal campaign fields cannot be empty")
        if self.schema_version != HISTORICAL_SIGNAL_CAMPAIGN_SCHEMA_VERSION:
            raise ValueError("unsupported historical signal campaign schema version")
        if self.candle_limit < 40 or self.decision_interval_candles < 1:
            raise ValueError("invalid historical signal campaign cadence")
        if self.replay_timeframe not in self.analysis_timeframes:
            raise ValueError("replay timeframe must be included in analysis timeframes")
        if self.record_count != self.train_count + self.validation_count + self.final_test_count:
            raise ValueError("historical signal split counts must equal record count")
        if not _is_sha256(self.records_hash):
            raise ValueError("historical signal records hash must be SHA-256")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "dataset_campaign_id": self.dataset_campaign_id,
            "execution_manifest_path": self.execution_manifest_path,
            "records_path": self.records_path,
            "replay_timeframe": self.replay_timeframe,
            "analysis_timeframes": list(self.analysis_timeframes),
            "candle_limit": self.candle_limit,
            "decision_interval_candles": self.decision_interval_candles,
            "record_count": self.record_count,
            "train_count": self.train_count,
            "validation_count": self.validation_count,
            "final_test_count": self.final_test_count,
            "records_hash": self.records_hash,
        }


def write_historical_signal_records(path: Path, records: tuple[HistoricalSignalRecord, ...]) -> str:
    """Write deterministic JSONL records atomically and return their SHA-256 hash."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(
        json.dumps(record.to_payload(), sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_historical_signal_manifest(path: Path, manifest: HistoricalSignalCampaignManifest) -> None:
    """Write the campaign manifest atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def historical_signal_record_id(
    campaign_id: str,
    symbol: str,
    split_role: HistoricalSignalSplitRole,
    decision_time: datetime,
) -> str:
    """Build a stable ID from frozen campaign and decision identity."""

    canonical = "|".join((campaign_id, symbol, split_role.value, decision_time.isoformat()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
