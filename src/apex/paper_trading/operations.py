"""Deterministic provider-independent P1 paper operations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from apex.domain.models import Candle
from apex.paper_trading.contracts import PaperTrade, PaperTradeConfig
from apex.paper_trading.forward_validation import (
    ForwardPaperDailyReport,
    build_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.paper_trading.management import advance_paper_trade
from apex.paper_trading.store import PaperTradeStore

_SUPPORTED_MARKET_TYPES = frozenset({"spot", "futures"})


@dataclass(frozen=True, slots=True)
class PaperOperationCycleResult:
    """Immutable outcome of one spot or futures paper-operation cycle."""

    market_type: str
    started_at: datetime
    completed_at: datetime
    loaded_trade_count: int
    eligible_trade_count: int
    advanced_trade_count: int
    unchanged_trade_count: int
    missing_candle_trade_ids: tuple[str, ...]
    trade_ids: tuple[str, ...]
    daily_report: ForwardPaperDailyReport | None = None

    def __post_init__(self) -> None:
        if self.market_type not in _SUPPORTED_MARKET_TYPES:
            raise ValueError("paper operation market type must be spot or futures")
        for name in ("started_at", "completed_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name.replace('_', ' ')} must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("paper operation completion cannot precede its start")
        counts = (
            self.loaded_trade_count,
            self.eligible_trade_count,
            self.advanced_trade_count,
            self.unchanged_trade_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("paper operation counts cannot be negative")
        if self.advanced_trade_count + self.unchanged_trade_count != self.eligible_trade_count:
            raise ValueError("advanced and unchanged counts must equal eligible trades")


def run_paper_operation_cycle(
    *,
    store: PaperTradeStore,
    candles_by_symbol: Mapping[str, Sequence[Candle]],
    market_type: str,
    config: PaperTradeConfig | None = None,
    started_at: datetime,
    completed_at: datetime | None = None,
    daily_report_date: date | None = None,
    daily_report_path: Path | None = None,
    force_report: bool = False,
) -> PaperOperationCycleResult:
    """Advance one deterministic cycle and optionally persist its daily report.

    Market data collection and scheduling remain outside this function. Callers must
    provide closed normalized candles and may invoke this cycle repeatedly.
    """

    normalized_market = market_type.strip().lower()
    if normalized_market not in _SUPPORTED_MARKET_TYPES:
        raise ValueError("paper operation market type must be spot or futures")
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("paper operation start time must be timezone-aware")
    finished = completed_at or started_at
    if finished.tzinfo is None or finished.utcoffset() is None:
        raise ValueError("paper operation completion time must be timezone-aware")

    loaded = store.load()
    active_config = config or PaperTradeConfig()
    advanced_count = 0
    unchanged_count = 0
    missing: list[str] = []
    updated: list[PaperTrade] = []
    eligible_ids: list[str] = []

    normalized_candles = {
        symbol: tuple(sorted(candles, key=lambda candle: (candle.close_time, candle.open_time)))
        for symbol, candles in candles_by_symbol.items()
    }
    for trade in loaded:
        trade_market = str(trade.analysis_payload.get("market_type", "futures")).lower()
        if trade_market != normalized_market:
            updated.append(trade)
            continue
        eligible_ids.append(trade.trade_id)
        candles = tuple(
            candle
            for candle in normalized_candles.get(trade.signal.symbol, ())
            if candle.is_closed and candle.close_time > trade.updated_at
        )
        if not candles:
            missing.append(trade.trade_id)
            unchanged_count += 1
            updated.append(trade)
            continue
        next_trade = advance_paper_trade(trade, candles, config=active_config)
        if next_trade == trade:
            unchanged_count += 1
        else:
            advanced_count += 1
        updated.append(next_trade)

    ordered = tuple(sorted(updated, key=lambda trade: (trade.created_at, trade.trade_id)))
    store.save(ordered)

    daily_report: ForwardPaperDailyReport | None = None
    if daily_report_date is not None:
        daily_report = build_forward_paper_daily_report(
            report_date=daily_report_date,
            trades=ordered,
            generated_at=finished,
        )
        if daily_report_path is not None:
            write_forward_paper_daily_report(
                daily_report,
                daily_report_path,
                force=force_report,
            )

    return PaperOperationCycleResult(
        market_type=normalized_market,
        started_at=started_at.astimezone(timezone.utc),
        completed_at=finished.astimezone(timezone.utc),
        loaded_trade_count=len(loaded),
        eligible_trade_count=len(eligible_ids),
        advanced_trade_count=advanced_count,
        unchanged_trade_count=unchanged_count,
        missing_candle_trade_ids=tuple(sorted(missing)),
        trade_ids=tuple(sorted(eligible_ids)),
        daily_report=daily_report,
    )


def write_paper_operation_cycle_result(
    result: PaperOperationCycleResult,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist an operational cycle summary atomically without silent overwrite."""

    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite paper operation result: {path}")
    payload = _jsonable(asdict(result))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
