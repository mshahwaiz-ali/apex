"""Leak-proof replay primitives for historical Apex signal generation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain.models import Candle, TickerSnapshot


class HistoricalSignalSplit(StrEnum):
    """Frozen campaign split assigned from a historical decision timestamp."""

    TRAIN = "train"
    VALIDATION = "validation"
    FINAL_TEST = "final_test"


@dataclass(frozen=True, slots=True)
class HistoricalReplayBoundaries:
    """Strict timestamp boundaries inherited from an aligned dataset campaign."""

    analysis_start: datetime
    train_end: datetime
    validation_end: datetime
    analysis_end: datetime

    def __post_init__(self) -> None:
        for name in (
            "analysis_start",
            "train_end",
            "validation_end",
            "analysis_end",
        ):
            _require_aware(getattr(self, name), name)

        if not (self.analysis_start < self.train_end < self.validation_end < self.analysis_end):
            raise ValueError("historical replay boundaries must be strictly increasing")

    def split_for(self, decision_time: datetime) -> HistoricalSignalSplit:
        """Return the campaign split containing ``decision_time``."""

        _require_aware(decision_time, "decision time")
        if not self.analysis_start <= decision_time < self.analysis_end:
            raise ValueError("decision time must fall inside the campaign analysis range")
        if decision_time < self.train_end:
            return HistoricalSignalSplit.TRAIN
        if decision_time < self.validation_end:
            return HistoricalSignalSplit.VALIDATION
        return HistoricalSignalSplit.FINAL_TEST


@dataclass(frozen=True, slots=True)
class HistoricalReplayPoint:
    """One deterministic signal-generation timestamp and its frozen split."""

    decision_time: datetime
    split: HistoricalSignalSplit


@dataclass(frozen=True, slots=True)
class HistoricalCandleSeries:
    """Immutable candles for one symbol/timeframe dataset."""

    symbol: str
    timeframe: str
    candles: tuple[Candle, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.timeframe.strip():
            raise ValueError("historical candle series identity cannot be empty")
        if not self.candles:
            raise ValueError("historical candle series cannot be empty")

        previous_open_time: datetime | None = None
        for candle in self.candles:
            if candle.symbol != self.symbol:
                raise ValueError("historical candle symbol does not match its series")
            if candle.timeframe != self.timeframe:
                raise ValueError("historical candle timeframe does not match its series")
            if not candle.is_closed:
                raise ValueError("historical signal replay requires closed source candles")
            if previous_open_time is not None and candle.open_time <= previous_open_time:
                raise ValueError("historical candles must be strictly ordered by open time")
            previous_open_time = candle.open_time


class HistoricalCandleStore:
    """Immutable symbol/timeframe lookup for aligned historical candles."""

    def __init__(self, series: Iterable[HistoricalCandleSeries]) -> None:
        values = tuple(series)
        if not values:
            raise ValueError("historical candle store requires at least one series")

        indexed: dict[tuple[str, str], HistoricalCandleSeries] = {}
        for item in values:
            key = (item.symbol, item.timeframe)
            if key in indexed:
                raise ValueError("historical candle store contains a duplicate series")
            indexed[key] = item

        self._series: Mapping[
            tuple[str, str],
            HistoricalCandleSeries,
        ] = indexed

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return symbols in deterministic lexical order."""

        return tuple(sorted({symbol for symbol, _ in self._series}))

    def timeframes_for(self, symbol: str) -> tuple[str, ...]:
        """Return available timeframes for a symbol in lexical order."""

        return tuple(
            sorted(
                timeframe for stored_symbol, timeframe in self._series if stored_symbol == symbol
            )
        )

    def candles_for(self, symbol: str, timeframe: str) -> tuple[Candle, ...]:
        """Return the complete immutable source series."""

        try:
            return self._series[(symbol, timeframe)].candles
        except KeyError as exc:
            raise ValueError(
                f"historical candle series is unavailable: {symbol} {timeframe}"
            ) from exc


class HistoricalReplayProvider:
    """Expose only historical candles closed by one replay decision time.

    This adapter intentionally provides no ticker or optional live-market
    snapshots. Existing analysis code therefore falls back to the latest
    historically closed candle and records optional data as unavailable.
    """

    def __init__(
        self,
        *,
        store: HistoricalCandleStore,
        decision_time: datetime,
        source_name: str = "historical_replay",
    ) -> None:
        _require_aware(decision_time, "decision time")
        if not source_name.strip():
            raise ValueError("historical replay source name cannot be empty")

        self._store = store
        self._decision_time = decision_time
        self._source_name = source_name

    @property
    def name(self) -> str:
        """Return the replay-provider identifier."""

        return self._source_name

    @property
    def decision_time(self) -> datetime:
        """Return the frozen timestamp visible to this provider."""

        return self._decision_time

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        """Return at most ``limit`` candles closed by the decision time."""

        if limit < 1:
            raise ValueError("historical replay candle limit must be positive")

        available = tuple(
            candle
            for candle in self._store.candles_for(symbol, timeframe)
            if candle.close_time <= self._decision_time
        )
        return list(available[-limit:])

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Reject unavailable historical ticker data instead of fabricating it."""

        del symbol
        raise LookupError("historical ticker snapshot is unavailable for candle-only replay")


def build_replay_points(
    *,
    decision_times: Sequence[datetime],
    boundaries: HistoricalReplayBoundaries,
) -> tuple[HistoricalReplayPoint, ...]:
    """Validate and classify a deterministic chronological replay schedule."""

    if not decision_times:
        raise ValueError("historical replay requires decision timestamps")

    points: list[HistoricalReplayPoint] = []
    previous: datetime | None = None
    for decision_time in decision_times:
        _require_aware(decision_time, "decision time")
        if previous is not None and decision_time <= previous:
            raise ValueError("historical replay decision times must be strictly increasing")
        points.append(
            HistoricalReplayPoint(
                decision_time=decision_time,
                split=boundaries.split_for(decision_time),
            )
        )
        previous = decision_time

    return tuple(points)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
