"""Curated historical dataset manifests and deterministic validation."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from apex.application.historical_edge import DatasetPartition, MarketType

HISTORICAL_DATASET_MANIFEST_SCHEMA_VERSION = 1
_REQUIRED_FIELDS = (
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
_TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class DatasetValidationState(StrEnum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"


class DatasetIssueSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


class DatasetIssueCode(StrEnum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MALFORMED_TIMESTAMP = "MALFORMED_TIMESTAMP"
    NAIVE_TIMESTAMP = "NAIVE_TIMESTAMP"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
    IMPOSSIBLE_OHLC = "IMPOSSIBLE_OHLC"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    MISSING_INTERVAL = "MISSING_INTERVAL"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    FIRST_TIMESTAMP_MISMATCH = "FIRST_TIMESTAMP_MISMATCH"
    LAST_TIMESTAMP_MISMATCH = "LAST_TIMESTAMP_MISMATCH"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    TIMEFRAME_MISMATCH = "TIMEFRAME_MISMATCH"
    PARTITION_OUT_OF_RANGE = "PARTITION_OUT_OF_RANGE"


@dataclass(frozen=True, slots=True)
class DatasetValidationIssue:
    code: DatasetIssueCode
    severity: DatasetIssueSeverity
    message: str
    row_index: int | None = None
    symbol: str | None = None
    timeframe: str | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DatasetValidationResult:
    state: DatasetValidationState
    issues: tuple[DatasetValidationIssue, ...]
    record_count: int
    duplicate_count: int
    missing_interval_count: int
    malformed_row_count: int
    out_of_order_row_count: int
    content_hash: str

    @property
    def is_acceptable(self) -> bool:
        return self.state is not DatasetValidationState.INVALID


@dataclass(frozen=True, slots=True)
class CuratedDatasetManifest:
    dataset_id: str
    market_type: MarketType
    source_type: str
    source_identifier: str
    exchange_provider: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    candle_count: int
    first_timestamp: datetime
    last_timestamp: datetime
    timezone: str
    expected_interval: str
    content_hash: str
    schema_version: int
    created_at: datetime
    partitions: tuple[DatasetPartition, ...]
    notes: str | None
    data_quality_flags: tuple[str, ...]
    duplicate_count: int
    missing_interval_count: int
    malformed_row_count: int
    out_of_order_row_count: int

    def __post_init__(self) -> None:
        required = (self.dataset_id, self.source_type, self.source_identifier, self.exchange_provider)
        if any(not value.strip() for value in required):
            raise ValueError("manifest identity fields are required")
        if not self.symbols or not self.timeframes:
            raise ValueError("manifest requires symbols and timeframes")
        if self.candle_count <= 0:
            raise ValueError("manifest candle count must be positive")
        for value, label in (
            (self.first_timestamp, "first timestamp"),
            (self.last_timestamp, "last timestamp"),
            (self.created_at, "created timestamp"),
        ):
            _require_aware(value, label)
        if self.last_timestamp < self.first_timestamp:
            raise ValueError("manifest last timestamp cannot precede first timestamp")
        _validate_sha256(self.content_hash)
        if self.schema_version <= 0:
            raise ValueError("manifest schema version must be positive")
        counts = (
            self.duplicate_count,
            self.missing_interval_count,
            self.malformed_row_count,
            self.out_of_order_row_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("manifest quality counts cannot be negative")


@dataclass(frozen=True, slots=True)
class CuratedDatasetBuildResult:
    manifest: CuratedDatasetManifest | None
    validation: DatasetValidationResult


@dataclass(frozen=True, slots=True)
class _ParsedRecord:
    row_index: int
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def validate_curated_candles(
    records: Sequence[Mapping[str, object]],
    *,
    expected_symbols: Sequence[str] = (),
    expected_timeframes: Sequence[str] = (),
    expected_interval: str | None = None,
    expected_count: int | None = None,
    expected_first_timestamp: datetime | None = None,
    expected_last_timestamp: datetime | None = None,
    partitions: Sequence[DatasetPartition] = (),
) -> DatasetValidationResult:
    """Validate raw candle records without silently sorting or repairing them."""

    issues: list[DatasetValidationIssue] = []
    parsed: list[_ParsedRecord] = []
    malformed_rows: set[int] = set()
    for index, record in enumerate(records):
        missing = tuple(field for field in _REQUIRED_FIELDS if field not in record)
        if missing:
            malformed_rows.add(index)
            issues.append(
                DatasetValidationIssue(
                    DatasetIssueCode.MISSING_REQUIRED_FIELD,
                    DatasetIssueSeverity.ERROR,
                    f"missing required fields: {', '.join(missing)}",
                    row_index=index,
                )
            )
            continue
        parsed_record, row_issues = _parse_record(index, record)
        issues.extend(row_issues)
        if parsed_record is None:
            malformed_rows.add(index)
        else:
            parsed.append(parsed_record)

    duplicate_count = _append_duplicate_issues(parsed, issues)
    out_of_order_count = _append_order_issues(parsed, issues)
    missing_interval_count = _append_interval_issues(
        parsed, issues, expected_interval=expected_interval
    )
    _append_expectation_issues(
        parsed,
        issues,
        expected_symbols=expected_symbols,
        expected_timeframes=expected_timeframes,
        expected_count=expected_count,
        expected_first_timestamp=expected_first_timestamp,
        expected_last_timestamp=expected_last_timestamp,
    )
    _append_partition_issues(parsed, partitions, issues)

    ordered_issues = tuple(sorted(issues, key=_issue_sort_key))
    has_errors = any(issue.severity is DatasetIssueSeverity.ERROR for issue in ordered_issues)
    has_warnings = any(issue.severity is DatasetIssueSeverity.WARNING for issue in ordered_issues)
    state = (
        DatasetValidationState.INVALID
        if has_errors
        else DatasetValidationState.VALID_WITH_WARNINGS
        if has_warnings
        else DatasetValidationState.VALID
    )
    return DatasetValidationResult(
        state=state,
        issues=ordered_issues,
        record_count=len(records),
        duplicate_count=duplicate_count,
        missing_interval_count=missing_interval_count,
        malformed_row_count=len(malformed_rows),
        out_of_order_row_count=out_of_order_count,
        content_hash=canonical_candle_content_hash(records),
    )


def build_curated_dataset_manifest(
    *,
    dataset_id: str,
    market_type: MarketType,
    source_type: str,
    source_identifier: str,
    exchange_provider: str,
    records: Sequence[Mapping[str, object]],
    expected_interval: str,
    partitions: Sequence[DatasetPartition],
    created_at: datetime,
    timezone: str = "UTC",
    notes: str | None = None,
    expected_symbols: Sequence[str] = (),
    expected_timeframes: Sequence[str] = (),
) -> CuratedDatasetBuildResult:
    validation = validate_curated_candles(
        records,
        expected_symbols=expected_symbols,
        expected_timeframes=expected_timeframes,
        expected_interval=expected_interval,
        partitions=partitions,
    )
    if validation.state is DatasetValidationState.INVALID:
        return CuratedDatasetBuildResult(None, validation)

    valid = tuple(
        parsed
        for index, record in enumerate(records)
        if (parsed := _parse_record(index, record)[0]) is not None
    )
    timestamps = tuple(record.open_time for record in valid)
    manifest = CuratedDatasetManifest(
        dataset_id=dataset_id,
        market_type=market_type,
        source_type=source_type,
        source_identifier=source_identifier,
        exchange_provider=exchange_provider,
        symbols=tuple(sorted({record.symbol for record in valid})),
        timeframes=tuple(sorted({record.timeframe for record in valid})),
        candle_count=len(records),
        first_timestamp=min(timestamps),
        last_timestamp=max(timestamps),
        timezone=timezone,
        expected_interval=expected_interval,
        content_hash=validation.content_hash,
        schema_version=HISTORICAL_DATASET_MANIFEST_SCHEMA_VERSION,
        created_at=created_at,
        partitions=tuple(sorted(partitions, key=lambda item: item.start_at)),
        notes=notes,
        data_quality_flags=tuple(sorted({issue.code.value for issue in validation.issues})),
        duplicate_count=validation.duplicate_count,
        missing_interval_count=validation.missing_interval_count,
        malformed_row_count=validation.malformed_row_count,
        out_of_order_row_count=validation.out_of_order_row_count,
    )
    return CuratedDatasetBuildResult(manifest, validation)


def canonical_candle_content_hash(records: Sequence[Mapping[str, object]]) -> str:
    payload = [_canonical_record(record) for record in records]
    payload.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _parse_record(
    index: int, record: Mapping[str, object]
) -> tuple[_ParsedRecord | None, tuple[DatasetValidationIssue, ...]]:
    symbol = str(record["symbol"]).strip()
    timeframe = str(record["timeframe"]).strip()
    open_time = _parse_timestamp(record["open_time"])
    close_time = _parse_timestamp(record["close_time"])
    common = {"row_index": index, "symbol": symbol or None, "timeframe": timeframe or None}
    if open_time is None or close_time is None:
        return None, (
            DatasetValidationIssue(
                DatasetIssueCode.MALFORMED_TIMESTAMP,
                DatasetIssueSeverity.ERROR,
                "open_time and close_time must be datetime values",
                **common,
            ),
        )
    if not _is_aware(open_time) or not _is_aware(close_time):
        return None, (
            DatasetValidationIssue(
                DatasetIssueCode.NAIVE_TIMESTAMP,
                DatasetIssueSeverity.ERROR,
                "candle timestamps must be timezone-aware",
                observed_at=open_time,
                **common,
            ),
        )
    try:
        values = tuple(float(record[name]) for name in ("open", "high", "low", "close", "volume"))
    except (TypeError, ValueError):
        return None, (
            DatasetValidationIssue(
                DatasetIssueCode.NON_FINITE_NUMBER,
                DatasetIssueSeverity.ERROR,
                "OHLCV fields must be numeric",
                observed_at=open_time,
                **common,
            ),
        )
    open_price, high, low, close, volume = values
    issues: list[DatasetValidationIssue] = []
    if not all(math.isfinite(value) for value in values):
        issues.append(DatasetValidationIssue(DatasetIssueCode.NON_FINITE_NUMBER, DatasetIssueSeverity.ERROR, "OHLCV fields must be finite", observed_at=open_time, **common))
    if min(open_price, high, low, close) <= 0 or high < max(open_price, close, low) or low > min(open_price, close, high):
        issues.append(DatasetValidationIssue(DatasetIssueCode.IMPOSSIBLE_OHLC, DatasetIssueSeverity.ERROR, "invalid OHLC geometry", observed_at=open_time, **common))
    if volume < 0:
        issues.append(DatasetValidationIssue(DatasetIssueCode.NEGATIVE_VOLUME, DatasetIssueSeverity.ERROR, "volume cannot be negative", observed_at=open_time, **common))
    if close_time <= open_time:
        issues.append(DatasetValidationIssue(DatasetIssueCode.INVALID_INTERVAL, DatasetIssueSeverity.ERROR, "close_time must be after open_time", observed_at=open_time, **common))
    return (
        _ParsedRecord(index, symbol, timeframe, open_time, close_time, open_price, high, low, close, volume),
        tuple(issues),
    )


def _append_duplicate_issues(parsed: Sequence[_ParsedRecord], issues: list[DatasetValidationIssue]) -> int:
    counts = Counter((item.symbol, item.timeframe, item.open_time) for item in parsed)
    duplicate_keys = {key for key, count in counts.items() if count > 1}
    for item in parsed:
        if (item.symbol, item.timeframe, item.open_time) in duplicate_keys:
            issues.append(DatasetValidationIssue(DatasetIssueCode.DUPLICATE_TIMESTAMP, DatasetIssueSeverity.ERROR, "duplicate timestamp for symbol/timeframe", item.row_index, item.symbol, item.timeframe, item.open_time))
    return sum(count - 1 for count in counts.values() if count > 1)


def _append_order_issues(parsed: Sequence[_ParsedRecord], issues: list[DatasetValidationIssue]) -> int:
    previous: dict[tuple[str, str], datetime] = {}
    count = 0
    for item in parsed:
        key = (item.symbol, item.timeframe)
        last = previous.get(key)
        if last is not None and item.open_time <= last:
            count += 1
            issues.append(DatasetValidationIssue(DatasetIssueCode.OUT_OF_ORDER, DatasetIssueSeverity.ERROR, "records must be strictly chronological", item.row_index, item.symbol, item.timeframe, item.open_time))
        previous[key] = item.open_time
    return count


def _append_interval_issues(parsed: Sequence[_ParsedRecord], issues: list[DatasetValidationIssue], *, expected_interval: str | None) -> int:
    groups: defaultdict[tuple[str, str], list[_ParsedRecord]] = defaultdict(list)
    for item in parsed:
        groups[(item.symbol, item.timeframe)].append(item)
    missing_count = 0
    for (symbol, timeframe), group in groups.items():
        interval_name = expected_interval or timeframe
        seconds = _TIMEFRAME_SECONDS.get(interval_name)
        if seconds is None:
            issues.append(DatasetValidationIssue(DatasetIssueCode.INVALID_INTERVAL, DatasetIssueSeverity.ERROR, f"unsupported interval: {interval_name}", symbol=symbol, timeframe=timeframe))
            continue
        expected_delta = timedelta(seconds=seconds)
        ordered = sorted(group, key=lambda item: item.open_time)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            delta = current.open_time - previous.open_time
            if delta > expected_delta:
                missing = max(int(delta / expected_delta) - 1, 1)
                missing_count += missing
                issues.append(DatasetValidationIssue(DatasetIssueCode.MISSING_INTERVAL, DatasetIssueSeverity.WARNING, f"detected {missing} missing interval(s)", current.row_index, symbol, timeframe, current.open_time))
            elif delta != expected_delta:
                issues.append(DatasetValidationIssue(DatasetIssueCode.INVALID_INTERVAL, DatasetIssueSeverity.ERROR, "timestamp delta does not match expected interval", current.row_index, symbol, timeframe, current.open_time))
    return missing_count


def _append_expectation_issues(
    parsed: Sequence[_ParsedRecord],
    issues: list[DatasetValidationIssue],
    *,
    expected_symbols: Sequence[str],
    expected_timeframes: Sequence[str],
    expected_count: int | None,
    expected_first_timestamp: datetime | None,
    expected_last_timestamp: datetime | None,
) -> None:
    if expected_symbols and {item.symbol for item in parsed} != set(expected_symbols):
        issues.append(DatasetValidationIssue(DatasetIssueCode.SYMBOL_MISMATCH, DatasetIssueSeverity.ERROR, "symbols do not match manifest declaration"))
    if expected_timeframes and {item.timeframe for item in parsed} != set(expected_timeframes):
        issues.append(DatasetValidationIssue(DatasetIssueCode.TIMEFRAME_MISMATCH, DatasetIssueSeverity.ERROR, "timeframes do not match manifest declaration"))
    if expected_count is not None and len(parsed) != expected_count:
        issues.append(DatasetValidationIssue(DatasetIssueCode.COUNT_MISMATCH, DatasetIssueSeverity.ERROR, f"expected {expected_count} records; found {len(parsed)}"))
    if not parsed:
        return
    first = min(item.open_time for item in parsed)
    last = max(item.open_time for item in parsed)
    if expected_first_timestamp is not None and first != expected_first_timestamp:
        issues.append(DatasetValidationIssue(DatasetIssueCode.FIRST_TIMESTAMP_MISMATCH, DatasetIssueSeverity.ERROR, "first timestamp mismatch", observed_at=first))
    if expected_last_timestamp is not None and last != expected_last_timestamp:
        issues.append(DatasetValidationIssue(DatasetIssueCode.LAST_TIMESTAMP_MISMATCH, DatasetIssueSeverity.ERROR, "last timestamp mismatch", observed_at=last))


def _append_partition_issues(parsed: Sequence[_ParsedRecord], partitions: Sequence[DatasetPartition], issues: list[DatasetValidationIssue]) -> None:
    if not parsed:
        return
    first = min(item.open_time for item in parsed)
    last_close = max(item.close_time for item in parsed)
    for partition in partitions:
        if partition.start_at < first or partition.end_at > last_close:
            issues.append(DatasetValidationIssue(DatasetIssueCode.PARTITION_OUT_OF_RANGE, DatasetIssueSeverity.ERROR, f"{partition.split.value} partition is outside dataset range", observed_at=partition.start_at))


def _canonical_record(record: Mapping[str, object]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(record):
        value = record[key]
        if isinstance(value, datetime):
            result[key] = _canonical_timestamp(value)
        elif isinstance(value, float) and not math.isfinite(value):
            result[key] = str(value)
        else:
            result[key] = value
    return result


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _canonical_timestamp(value: datetime) -> str:
    return (value.astimezone(UTC) if _is_aware(value) else value).isoformat()


def _issue_sort_key(issue: DatasetValidationIssue) -> tuple[str, int, str, str, str]:
    return (issue.severity.value, -1 if issue.row_index is None else issue.row_index, issue.code.value, issue.symbol or "", issue.timeframe or "")


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _require_aware(value: datetime, label: str) -> None:
    if not _is_aware(value):
        raise ValueError(f"{label} must be timezone-aware")


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("content hash must be a SHA-256 hex digest")
