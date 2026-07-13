"""Deterministic metadata for chronological backtest reproducibility."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from apex.backtesting import BacktestConfig
from apex.domain.models import Candle
from apex.risk import RiskConfig


@dataclass(frozen=True, slots=True)
class ChronologicalBacktestMetadata:
    """Dataset identity, configuration identity, and replay coverage."""

    dataset_hash: str
    config_hash: str
    generated_at: datetime
    symbol: str
    analysis_timeframes: tuple[str, ...]
    replay_timeframe: str
    first_candle_at: datetime | None
    last_candle_at: datetime | None
    closed_candle_counts: Mapping[str, int]
    decision_interval_candles: int
    candidate_cooldown_candles: int

    def __post_init__(self) -> None:
        for name in ("dataset_hash", "config_hash"):
            value = getattr(self, name)
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name.replace('_', ' ')} must be a SHA-256 hex digest")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("metadata generation time must be timezone-aware")
        object.__setattr__(
            self,
            "closed_candle_counts",
            MappingProxyType(dict(self.closed_candle_counts)),
        )


def build_chronological_metadata(
    *,
    symbol: str,
    candles_by_timeframe: Mapping[str, Sequence[Candle]],
    analysis_timeframes: tuple[str, ...],
    replay_timeframe: str,
    candle_limit: int,
    decision_interval_candles: int,
    candidate_cooldown_candles: int,
    risk_config: RiskConfig,
    backtest_config: BacktestConfig,
    generated_at: datetime | None = None,
) -> ChronologicalBacktestMetadata:
    """Build deterministic hashes and descriptive replay metadata."""

    closed = {
        timeframe: tuple(candle for candle in candles if candle.is_closed)
        for timeframe, candles in sorted(candles_by_timeframe.items())
    }
    all_closed = tuple(candle for candles in closed.values() for candle in candles)
    dataset_payload = {
        timeframe: [_candle_payload(candle) for candle in candles]
        for timeframe, candles in closed.items()
    }
    config_payload = {
        "symbol": symbol,
        "analysis_timeframes": analysis_timeframes,
        "replay_timeframe": replay_timeframe,
        "candle_limit": candle_limit,
        "decision_interval_candles": decision_interval_candles,
        "candidate_cooldown_candles": candidate_cooldown_candles,
        "risk_config": asdict(risk_config),
        "backtest_config": asdict(backtest_config),
    }
    return ChronologicalBacktestMetadata(
        dataset_hash=_sha256(dataset_payload),
        config_hash=_sha256(config_payload),
        generated_at=generated_at or datetime.now(UTC),
        symbol=symbol,
        analysis_timeframes=analysis_timeframes,
        replay_timeframe=replay_timeframe,
        first_candle_at=min((candle.open_time for candle in all_closed), default=None),
        last_candle_at=max((candle.close_time for candle in all_closed), default=None),
        closed_candle_counts={timeframe: len(candles) for timeframe, candles in closed.items()},
        decision_interval_candles=decision_interval_candles,
        candidate_cooldown_candles=candidate_cooldown_candles,
    )


def _candle_payload(candle: Candle) -> dict[str, Any]:
    return {
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


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
