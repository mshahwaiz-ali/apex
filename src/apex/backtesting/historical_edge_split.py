"""Chronological dataset splits and leakage guards for historical edge studies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.backtesting.contracts import SimulatedTrade


class HistoricalEdgeSplitRole(StrEnum):
    """Purpose assigned to one chronological evidence partition."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class HistoricalEdgeSplitConfig:
    """Deterministic chronological split ratios and purge rules."""

    train_ratio: float = 0.60
    validation_ratio: float = 0.20
    test_ratio: float = 0.20
    purge_trades: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("train ratio", self.train_ratio),
            ("validation ratio", self.validation_ratio),
            ("test ratio", self.test_ratio),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be positive and finite")
        if not math.isclose(
            self.train_ratio + self.validation_ratio + self.test_ratio,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("historical edge split ratios must sum to one")
        if self.purge_trades < 0:
            raise ValueError("historical edge purge trades cannot be negative")


@dataclass(frozen=True, slots=True)
class HistoricalEdgeSplit:
    """One leakage-guarded chronological evidence partition."""

    role: HistoricalEdgeSplitRole
    trades: tuple[SimulatedTrade, ...]
    start_time: datetime | None
    end_time: datetime | None
    source_start_index: int
    source_end_index: int
    purged_trade_count: int = 0
    overlap_removed_count: int = 0

    def __post_init__(self) -> None:
        if self.source_start_index < 0 or self.source_end_index < self.source_start_index:
            raise ValueError("historical edge split source indexes are invalid")
        if self.purged_trade_count < 0 or self.overlap_removed_count < 0:
            raise ValueError("historical edge split removal counts cannot be negative")
        if not self.trades:
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("empty historical edge split cannot have time bounds")
            return
        expected = tuple(
            sorted(
                self.trades,
                key=lambda trade: (
                    trade.signal.generated_at,
                    trade.exit_time,
                    trade.signal.symbol,
                ),
            )
        )
        if expected != self.trades:
            raise ValueError("historical edge split trades must be chronological")
        if self.start_time != self.trades[0].signal.generated_at:
            raise ValueError("historical edge split start time must match first trade")
        if self.end_time != max(trade.exit_time for trade in self.trades):
            raise ValueError("historical edge split end time must match final exit")


@dataclass(frozen=True, slots=True)
class HistoricalEdgeSplitSet:
    """Complete chronological train, validation, and test partition set."""

    train: HistoricalEdgeSplit
    validation: HistoricalEdgeSplit
    test: HistoricalEdgeSplit
    source_trade_count: int

    def __post_init__(self) -> None:
        if self.source_trade_count < 0:
            raise ValueError("historical edge source trade count cannot be negative")
        if self.train.role is not HistoricalEdgeSplitRole.TRAIN:
            raise ValueError("train split must use the train role")
        if self.validation.role is not HistoricalEdgeSplitRole.VALIDATION:
            raise ValueError("validation split must use the validation role")
        if self.test.role is not HistoricalEdgeSplitRole.TEST:
            raise ValueError("test split must use the test role")
        _assert_non_overlapping(self.train, self.validation)
        _assert_non_overlapping(self.train, self.test)
        _assert_non_overlapping(self.validation, self.test)


def split_historical_edge_trades(
    trades: tuple[SimulatedTrade, ...],
    *,
    config: HistoricalEdgeSplitConfig | None = None,
) -> HistoricalEdgeSplitSet:
    """Chronologically split completed trades and remove boundary leakage."""

    resolved_config = config or HistoricalEdgeSplitConfig()
    ordered = tuple(
        sorted(
            trades,
            key=lambda trade: (
                trade.signal.generated_at,
                trade.exit_time,
                trade.signal.symbol,
            ),
        )
    )
    total = len(ordered)
    train_end = int(total * resolved_config.train_ratio)
    validation_end = train_end + int(total * resolved_config.validation_ratio)

    raw_train = ordered[:train_end]
    raw_validation = ordered[train_end:validation_end]
    raw_test = ordered[validation_end:]

    train = _make_split(HistoricalEdgeSplitRole.TRAIN, raw_train, 0, train_end)
    validation = _guard_later_split(
        HistoricalEdgeSplitRole.VALIDATION,
        raw_validation,
        prior_end=train.end_time,
        source_start=train_end,
        source_end=validation_end,
        purge_trades=resolved_config.purge_trades,
    )
    test_prior_end = validation.end_time or train.end_time
    test = _guard_later_split(
        HistoricalEdgeSplitRole.TEST,
        raw_test,
        prior_end=test_prior_end,
        source_start=validation_end,
        source_end=total,
        purge_trades=resolved_config.purge_trades,
    )
    return HistoricalEdgeSplitSet(
        train=train,
        validation=validation,
        test=test,
        source_trade_count=total,
    )


def _guard_later_split(
    role: HistoricalEdgeSplitRole,
    trades: tuple[SimulatedTrade, ...],
    *,
    prior_end: datetime | None,
    source_start: int,
    source_end: int,
    purge_trades: int,
) -> HistoricalEdgeSplit:
    purged = trades[min(purge_trades, len(trades)) :]
    if prior_end is None:
        filtered = purged
    else:
        filtered = tuple(
            trade for trade in purged if trade.signal.generated_at > prior_end
        )
    return _make_split(
        role,
        filtered,
        source_start,
        source_end,
        purged_trade_count=len(trades) - len(purged),
        overlap_removed_count=len(purged) - len(filtered),
    )


def _make_split(
    role: HistoricalEdgeSplitRole,
    trades: tuple[SimulatedTrade, ...],
    source_start: int,
    source_end: int,
    *,
    purged_trade_count: int = 0,
    overlap_removed_count: int = 0,
) -> HistoricalEdgeSplit:
    start_time = trades[0].signal.generated_at if trades else None
    end_time = max((trade.exit_time for trade in trades), default=None)
    return HistoricalEdgeSplit(
        role=role,
        trades=trades,
        start_time=start_time,
        end_time=end_time,
        source_start_index=source_start,
        source_end_index=source_end,
        purged_trade_count=purged_trade_count,
        overlap_removed_count=overlap_removed_count,
    )


def _assert_non_overlapping(
    earlier: HistoricalEdgeSplit,
    later: HistoricalEdgeSplit,
) -> None:
    if earlier.end_time is None or later.start_time is None:
        return
    if later.start_time <= earlier.end_time:
        raise ValueError("historical edge splits overlap chronologically")
