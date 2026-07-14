"""Deterministic historical-edge contracts and aggregation.

This module never infers profitability from incomplete data. It aggregates only
completed chronological samples and labels low-sample results explicitly.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class MarketType(StrEnum):
    """Supported market domains for historical evidence."""

    FUTURES = "FUTURES"
    SPOT = "SPOT"


class DatasetSplit(StrEnum):
    """Chronological dataset partitions."""

    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class EvidenceQuality(StrEnum):
    """Sample-quality state derived only from completed observations."""

    INSUFFICIENT = "INSUFFICIENT"
    PRELIMINARY = "PRELIMINARY"
    ESTABLISHED = "ESTABLISHED"


@dataclass(frozen=True, slots=True)
class DatasetPartition:
    """One non-overlapping chronological partition."""

    split: DatasetSplit
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.start_at, "partition start")
        _require_aware(self.end_at, "partition end")
        if self.end_at <= self.start_at:
            raise ValueError("partition end must be after partition start")


@dataclass(frozen=True, slots=True)
class HistoricalDatasetMetadata:
    """Stable dataset identity and explicit chronological split definition."""

    dataset_id: str
    market_type: MarketType
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    source: str
    first_observation_at: datetime
    last_observation_at: datetime
    observation_count: int
    partitions: tuple[DatasetPartition, ...]
    content_hash: str

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset id is required")
        if not self.symbols:
            raise ValueError("dataset requires at least one symbol")
        if not self.timeframes:
            raise ValueError("dataset requires at least one timeframe")
        if not self.source.strip():
            raise ValueError("dataset source is required")
        _require_aware(self.first_observation_at, "first observation")
        _require_aware(self.last_observation_at, "last observation")
        if self.last_observation_at < self.first_observation_at:
            raise ValueError("last observation cannot precede first observation")
        if self.observation_count <= 0:
            raise ValueError("observation count must be positive")
        _validate_sha256(self.content_hash, "content hash")
        _validate_partitions(self.partitions)


@dataclass(frozen=True, slots=True)
class HistoricalOutcome:
    """One completed chronological setup outcome."""

    setup_id: str
    dataset_id: str
    split: DatasetSplit
    market_type: MarketType
    strategy: str
    symbol: str
    regime: str
    score_band: str
    opened_at: datetime
    closed_at: datetime
    net_return: float
    r_multiple: float
    maximum_favorable_excursion_r: float
    maximum_adverse_excursion_r: float
    won: bool

    def __post_init__(self) -> None:
        if not self.setup_id.strip() or not self.dataset_id.strip():
            raise ValueError("setup id and dataset id are required")
        for field_name in ("strategy", "symbol", "regime", "score_band"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name.replace('_', ' ')} is required")
        _require_aware(self.opened_at, "outcome open time")
        _require_aware(self.closed_at, "outcome close time")
        if self.closed_at <= self.opened_at:
            raise ValueError("outcome close time must be after open time")


@dataclass(frozen=True, slots=True)
class EvidenceThresholds:
    """Minimum completed samples for each evidence-quality state."""

    preliminary_samples: int = 20
    established_samples: int = 50

    def __post_init__(self) -> None:
        if self.preliminary_samples <= 0:
            raise ValueError("preliminary sample threshold must be positive")
        if self.established_samples < self.preliminary_samples:
            raise ValueError("established threshold cannot be below preliminary threshold")


@dataclass(frozen=True, slots=True)
class HistoricalEdgeMetrics:
    """Setup-specific aggregate metrics for one exact evidence segment."""

    market_type: MarketType
    strategy: str
    split: DatasetSplit
    symbol: str | None
    regime: str | None
    score_band: str | None
    sample_count: int
    wins: int
    losses: int
    win_rate: float | None
    expectancy_r: float | None
    average_win_r: float | None
    average_loss_r: float | None
    profit_factor: float | None
    average_mfe_r: float | None
    average_mae_r: float | None
    evidence_quality: EvidenceQuality
    insufficient_reason: str | None
    dataset_ids: tuple[str, ...]
    result_hash: str

    def __post_init__(self) -> None:
        if self.sample_count != self.wins + self.losses:
            raise ValueError("sample count must equal wins plus losses")
        _validate_sha256(self.result_hash, "result hash")


def build_dataset_metadata(
    *,
    dataset_id: str,
    market_type: MarketType,
    symbols: Sequence[str],
    timeframes: Sequence[str],
    source: str,
    first_observation_at: datetime,
    last_observation_at: datetime,
    observation_count: int,
    partitions: Sequence[DatasetPartition],
    content_payload: object,
) -> HistoricalDatasetMetadata:
    """Build canonical metadata with deterministic ordering and hashing."""

    return HistoricalDatasetMetadata(
        dataset_id=dataset_id,
        market_type=market_type,
        symbols=tuple(sorted(set(symbols))),
        timeframes=tuple(sorted(set(timeframes))),
        source=source,
        first_observation_at=first_observation_at,
        last_observation_at=last_observation_at,
        observation_count=observation_count,
        partitions=tuple(sorted(partitions, key=lambda item: item.start_at)),
        content_hash=stable_hash(content_payload),
    )


def aggregate_historical_edge(
    outcomes: Iterable[HistoricalOutcome],
    *,
    market_type: MarketType,
    strategy: str,
    split: DatasetSplit,
    symbol: str | None = None,
    regime: str | None = None,
    score_band: str | None = None,
    thresholds: EvidenceThresholds = EvidenceThresholds(),
) -> HistoricalEdgeMetrics:
    """Aggregate completed outcomes for one exact, leakage-safe segment."""

    selected = tuple(
        outcome
        for outcome in outcomes
        if outcome.market_type is market_type
        and outcome.strategy == strategy
        and outcome.split is split
        and (symbol is None or outcome.symbol == symbol)
        and (regime is None or outcome.regime == regime)
        and (score_band is None or outcome.score_band == score_band)
    )
    selected = tuple(sorted(selected, key=lambda item: (item.closed_at, item.setup_id)))
    sample_count = len(selected)
    wins = sum(outcome.won for outcome in selected)
    losses = sample_count - wins
    quality = _evidence_quality(sample_count, thresholds)
    insufficient_reason = None
    if quality is EvidenceQuality.INSUFFICIENT:
        insufficient_reason = (
            f"requires at least {thresholds.preliminary_samples} completed samples; "
            f"found {sample_count}"
        )

    win_values = tuple(outcome.r_multiple for outcome in selected if outcome.won)
    loss_values = tuple(outcome.r_multiple for outcome in selected if not outcome.won)
    gross_profit = sum(value for value in win_values if value > 0.0)
    gross_loss = abs(sum(value for value in loss_values if value < 0.0))
    payload = {
        "market_type": market_type.value,
        "strategy": strategy,
        "split": split.value,
        "symbol": symbol,
        "regime": regime,
        "score_band": score_band,
        "outcomes": [_outcome_payload(outcome) for outcome in selected],
        "thresholds": {
            "preliminary_samples": thresholds.preliminary_samples,
            "established_samples": thresholds.established_samples,
        },
    }
    return HistoricalEdgeMetrics(
        market_type=market_type,
        strategy=strategy,
        split=split,
        symbol=symbol,
        regime=regime,
        score_band=score_band,
        sample_count=sample_count,
        wins=wins,
        losses=losses,
        win_rate=_average(tuple(1.0 if outcome.won else 0.0 for outcome in selected)),
        expectancy_r=_average(tuple(outcome.r_multiple for outcome in selected)),
        average_win_r=_average(win_values),
        average_loss_r=_average(loss_values),
        profit_factor=None if gross_loss == 0.0 else gross_profit / gross_loss,
        average_mfe_r=_average(
            tuple(outcome.maximum_favorable_excursion_r for outcome in selected)
        ),
        average_mae_r=_average(tuple(outcome.maximum_adverse_excursion_r for outcome in selected)),
        evidence_quality=quality,
        insufficient_reason=insufficient_reason,
        dataset_ids=tuple(sorted({outcome.dataset_id for outcome in selected})),
        result_hash=stable_hash(payload),
    )


def aggregate_by_setup(
    outcomes: Iterable[HistoricalOutcome],
    *,
    split: DatasetSplit,
    thresholds: EvidenceThresholds = EvidenceThresholds(),
) -> Mapping[tuple[MarketType, str], HistoricalEdgeMetrics]:
    """Aggregate futures and spot outcomes separately by strategy."""

    materialized = tuple(outcomes)
    keys: dict[tuple[MarketType, str], None] = {}
    for outcome in materialized:
        if outcome.split is split:
            keys[(outcome.market_type, outcome.strategy)] = None
    result = {
        key: aggregate_historical_edge(
            materialized,
            market_type=key[0],
            strategy=key[1],
            split=split,
            thresholds=thresholds,
        )
        for key in sorted(keys, key=lambda item: (item[0].value, item[1]))
    }
    return MappingProxyType(result)


def stable_hash(payload: object) -> str:
    """Return a deterministic SHA-256 digest for JSON-compatible content."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_partitions(partitions: Sequence[DatasetPartition]) -> None:
    if not partitions:
        raise ValueError("dataset requires explicit train, validation, and test partitions")
    split_counts: defaultdict[DatasetSplit, int] = defaultdict(int)
    ordered = sorted(partitions, key=lambda item: item.start_at)
    for partition in ordered:
        split_counts[partition.split] += 1
    if set(split_counts) != set(DatasetSplit) or any(count != 1 for count in split_counts.values()):
        raise ValueError("dataset requires exactly one TRAIN, VALIDATION, and TEST partition")
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current.start_at < previous.end_at:
            raise ValueError("dataset partitions must not overlap")
    if tuple(partition.split for partition in ordered) != (
        DatasetSplit.TRAIN,
        DatasetSplit.VALIDATION,
        DatasetSplit.TEST,
    ):
        raise ValueError("dataset partitions must be chronological: TRAIN, VALIDATION, TEST")


def _evidence_quality(sample_count: int, thresholds: EvidenceThresholds) -> EvidenceQuality:
    if sample_count < thresholds.preliminary_samples:
        return EvidenceQuality.INSUFFICIENT
    if sample_count < thresholds.established_samples:
        return EvidenceQuality.PRELIMINARY
    return EvidenceQuality.ESTABLISHED


def _average(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _outcome_payload(outcome: HistoricalOutcome) -> dict[str, object]:
    return {
        "setup_id": outcome.setup_id,
        "dataset_id": outcome.dataset_id,
        "split": outcome.split.value,
        "market_type": outcome.market_type.value,
        "strategy": outcome.strategy,
        "symbol": outcome.symbol,
        "regime": outcome.regime,
        "score_band": outcome.score_band,
        "opened_at": outcome.opened_at.isoformat(),
        "closed_at": outcome.closed_at.isoformat(),
        "net_return": outcome.net_return,
        "r_multiple": outcome.r_multiple,
        "maximum_favorable_excursion_r": outcome.maximum_favorable_excursion_r,
        "maximum_adverse_excursion_r": outcome.maximum_adverse_excursion_r,
        "won": outcome.won,
    }


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _validate_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a SHA-256 hex digest")
