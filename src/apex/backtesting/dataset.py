"""Reproducible candle datasets for empirical futures campaigns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from apex.domain.models import Candle

FUTURES_DATASET_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class FuturesDatasetManifest:
    """Immutable identity and provenance for one candle dataset."""

    dataset_id: str
    symbol: str
    timeframe: str
    source: str
    extracted_at: datetime
    start_time: datetime
    end_time: datetime
    candle_count: int
    content_hash: str
    schema_version: int = FUTURES_DATASET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("dataset_id", "symbol", "timeframe", "source"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name.replace('_', ' ')} cannot be empty")

        for name in ("extracted_at", "start_time", "end_time"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name.replace('_', ' ')} must be timezone-aware")

        if self.start_time > self.end_time:
            raise ValueError("dataset start time cannot be after end time")
        if self.candle_count < 1:
            raise ValueError("dataset candle count must be positive")
        if self.schema_version != FUTURES_DATASET_SCHEMA_VERSION:
            raise ValueError("unsupported futures dataset schema version")
        if not _is_sha256(self.content_hash):
            raise ValueError("dataset content hash must be a SHA-256 hex digest")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source": self.source,
            "extracted_at": self.extracted_at.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "candle_count": self.candle_count,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class FuturesCandleDataset:
    """Validated candles bound to an immutable reproducibility manifest."""

    manifest: FuturesDatasetManifest
    candles: tuple[Candle, ...]

    def __post_init__(self) -> None:
        validate_dataset_candles(self.candles)

        first = self.candles[0]
        last = self.candles[-1]

        if self.manifest.symbol != first.symbol:
            raise ValueError("dataset manifest symbol does not match candles")
        if self.manifest.timeframe != first.timeframe:
            raise ValueError("dataset manifest timeframe does not match candles")
        if self.manifest.source != first.source:
            raise ValueError("dataset manifest source does not match candles")
        if self.manifest.start_time != first.open_time:
            raise ValueError("dataset manifest start time does not match candles")
        if self.manifest.end_time != last.close_time:
            raise ValueError("dataset manifest end time does not match candles")
        if self.manifest.candle_count != len(self.candles):
            raise ValueError("dataset manifest candle count does not match candles")
        if self.manifest.content_hash != hash_candles(self.candles):
            raise ValueError("dataset manifest content hash does not match candles")

    def to_payload(self) -> dict[str, object]:
        return {
            "manifest": self.manifest.to_payload(),
            "candles": [candle.model_dump(mode="json") for candle in self.candles],
        }


def build_futures_dataset(
    *,
    dataset_id: str,
    candles: tuple[Candle, ...],
    extracted_at: datetime,
) -> FuturesCandleDataset:
    """Build one deterministic dataset from normalized provider candles."""

    validate_dataset_candles(candles)
    first = candles[0]
    last = candles[-1]

    manifest = FuturesDatasetManifest(
        dataset_id=dataset_id,
        symbol=first.symbol,
        timeframe=first.timeframe,
        source=first.source,
        extracted_at=extracted_at,
        start_time=first.open_time,
        end_time=last.close_time,
        candle_count=len(candles),
        content_hash=hash_candles(candles),
    )
    return FuturesCandleDataset(manifest=manifest, candles=candles)


def validate_dataset_candles(candles: tuple[Candle, ...]) -> None:
    """Reject incomplete, mixed, duplicate, active, or unordered datasets."""

    if not candles:
        raise ValueError("futures dataset requires at least one candle")

    expected_symbol = candles[0].symbol
    expected_timeframe = candles[0].timeframe
    expected_source = candles[0].source

    previous_open_time: datetime | None = None
    seen_open_times: set[datetime] = set()

    for candle in candles:
        if candle.symbol != expected_symbol:
            raise ValueError("futures dataset cannot mix symbols")
        if candle.timeframe != expected_timeframe:
            raise ValueError("futures dataset cannot mix timeframes")
        if candle.source != expected_source:
            raise ValueError("futures dataset cannot mix providers")
        if not candle.is_closed:
            raise ValueError("futures dataset cannot contain active candles")
        if candle.open_time in seen_open_times:
            raise ValueError("futures dataset cannot contain duplicate candle times")
        if previous_open_time is not None and candle.open_time <= previous_open_time:
            raise ValueError("futures dataset candles must be chronological")

        seen_open_times.add(candle.open_time)
        previous_open_time = candle.open_time


def hash_candles(candles: tuple[Candle, ...]) -> str:
    """Return a stable SHA-256 digest of canonical candle content."""

    validate_dataset_candles(candles)
    canonical = [
        {
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "open_time": candle.open_time.isoformat(),
            "close_time": candle.close_time.isoformat(),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "is_closed": candle.is_closed,
            "source": candle.source,
        }
        for candle in candles
    ]
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_futures_dataset(
    path: Path,
    dataset: FuturesCandleDataset,
) -> None:
    """Persist one deterministic dataset with atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            dataset.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_futures_dataset(path: Path) -> FuturesCandleDataset:
    """Load and fully revalidate a persisted futures dataset."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("futures dataset payload must be an object")

    raw_manifest = payload.get("manifest")
    raw_candles = payload.get("candles")
    if not isinstance(raw_manifest, dict):
        raise ValueError("futures dataset manifest must be an object")
    if not isinstance(raw_candles, list):
        raise ValueError("futures dataset candles must be a list")

    manifest = FuturesDatasetManifest(
        schema_version=int(raw_manifest["schema_version"]),
        dataset_id=str(raw_manifest["dataset_id"]),
        symbol=str(raw_manifest["symbol"]),
        timeframe=str(raw_manifest["timeframe"]),
        source=str(raw_manifest["source"]),
        extracted_at=datetime.fromisoformat(str(raw_manifest["extracted_at"])),
        start_time=datetime.fromisoformat(str(raw_manifest["start_time"])),
        end_time=datetime.fromisoformat(str(raw_manifest["end_time"])),
        candle_count=int(raw_manifest["candle_count"]),
        content_hash=str(raw_manifest["content_hash"]),
    )
    candles = tuple(Candle.model_validate(item) for item in raw_candles)
    return FuturesCandleDataset(manifest=manifest, candles=candles)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
