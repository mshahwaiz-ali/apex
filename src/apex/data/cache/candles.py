"""Filesystem-backed cache for normalized candle series."""

from __future__ import annotations

import contextlib
import hashlib
import itertools
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from apex.domain.models import Candle

TIMEFRAME_INTERVALS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


@dataclass(frozen=True, slots=True)
class CandleCacheKey:
    """Unique identity for one cached candle request."""

    provider: str
    symbol: str
    timeframe: str
    limit: int

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider cannot be empty")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty")
        if self.limit < 1:
            raise ValueError("limit must be at least 1")

    @property
    def digest(self) -> str:
        """Return a stable filesystem-safe key."""

        raw = "|".join(
            (
                self.provider.lower().strip(),
                self.symbol.upper().strip(),
                self.timeframe.lower().strip(),
                str(self.limit),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CandleCacheResult:
    """Candles loaded from a fresh cache entry."""

    candles: tuple[Candle, ...]
    saved_at: datetime


def validate_candle_series(
    candles: tuple[Candle, ...],
    *,
    now: datetime | None = None,
    enforce_market_age: bool = True,
) -> None:
    """Validate ordering, intervals, duplicates, and active-candle placement."""

    if not candles:
        raise ValueError("candle series cannot be empty")

    timeframe = candles[0].timeframe.lower().strip()
    try:
        interval = TIMEFRAME_INTERVALS[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported candle timeframe: {timeframe}") from exc

    active_indexes = [index for index, candle in enumerate(candles) if not candle.is_closed]
    if len(active_indexes) > 1:
        raise ValueError("candle series cannot contain multiple active candles")
    if active_indexes and active_indexes[0] != len(candles) - 1:
        raise ValueError("active candle must be the final candle")

    for previous, current in itertools.pairwise(candles):
        if current.open_time == previous.open_time:
            raise ValueError("candle series contains duplicate timestamps")
        if current.open_time < previous.open_time:
            raise ValueError("candle series must be ordered by open time")
        if current.open_time - previous.open_time != interval:
            raise ValueError("candle series contains a missing or inconsistent interval")

    if enforce_market_age:
        reference_time = now or datetime.now(UTC)
        if reference_time.tzinfo is None:
            raise ValueError("validation clock must be timezone-aware")
        latest = candles[-1]
        if latest.is_closed and reference_time.astimezone(UTC) - latest.close_time > interval:
            raise ValueError("candle series is stale")


class FileCandleCache:
    """Store normalized candle responses as local JSON files."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        directory: Path | str = Path("data/cache/candles"),
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._directory = Path(directory)
        self._now = now or (lambda: datetime.now(UTC))

    def load(
        self,
        key: CandleCacheKey,
        *,
        max_age: timedelta,
    ) -> CandleCacheResult | None:
        """Return a fresh validated entry, otherwise return ``None``."""

        if max_age < timedelta(0):
            raise ValueError("max_age cannot be negative")

        path = self._path_for(key)

        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            return None
        if payload.get("key") != self._serialized_key(key):
            return None

        saved_at = self._parse_datetime(payload.get("saved_at"))
        if saved_at is None:
            return None

        now = self._normalized_now()
        age = now - saved_at
        if age < timedelta(0) or age > max_age:
            return None

        candle_payloads = payload.get("candles")
        if not isinstance(candle_payloads, list) or not candle_payloads:
            return None

        try:
            candles = tuple(
                Candle.model_validate(candle_payload) for candle_payload in candle_payloads
            )
            if not self._candles_match_key(candles, key):
                return None
            validate_candle_series(candles, now=now, enforce_market_age=False)
        except (ValidationError, TypeError, ValueError):
            return None

        return CandleCacheResult(candles=candles, saved_at=saved_at)

    def save(
        self,
        key: CandleCacheKey,
        candles: list[Candle] | tuple[Candle, ...],
    ) -> Path:
        """Atomically save a structurally validated candle series."""

        normalized_candles = tuple(candles)
        if not self._candles_match_key(normalized_candles, key):
            raise ValueError("candles do not match the cache key")
        validate_candle_series(
            normalized_candles,
            now=self._normalized_now(),
            enforce_market_age=False,
        )

        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(key)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "key": self._serialized_key(key),
            "saved_at": self._normalized_now().isoformat(),
            "candles": [candle.model_dump(mode="json") for candle in normalized_candles],
        }

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._directory,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.replace(path)
        finally:
            if temporary_path is not None:
                with contextlib.suppress(OSError):
                    temporary_path.unlink(missing_ok=True)

        return path

    def _path_for(self, key: CandleCacheKey) -> Path:
        return self._directory / f"{key.digest}.json"

    def _normalized_now(self) -> datetime:
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("cache clock must return a timezone-aware datetime")
        return now.astimezone(UTC)

    @staticmethod
    def _serialized_key(key: CandleCacheKey) -> dict[str, Any]:
        return {
            "provider": key.provider.lower().strip(),
            "symbol": key.symbol.upper().strip(),
            "timeframe": key.timeframe.lower().strip(),
            "limit": key.limit,
        }

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)

    @staticmethod
    def _candles_match_key(
        candles: tuple[Candle, ...],
        key: CandleCacheKey,
    ) -> bool:
        if not candles or len(candles) > key.limit:
            return False

        expected_provider = key.provider.lower().strip()
        expected_symbol = key.symbol.upper().strip()
        expected_timeframe = key.timeframe.lower().strip()

        return all(
            candle.source.lower().strip() == expected_provider
            and candle.symbol.upper().strip() == expected_symbol
            and candle.timeframe.lower().strip() == expected_timeframe
            for candle in candles
        )
