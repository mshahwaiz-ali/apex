"""Local JSON storage for Phase 9 paper trading."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting import BacktestSignal
from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.strategies import StrategyType, TradeDirection


class PaperTradeStore:
    """Append-friendly local JSON paper-trade store."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[PaperTrade, ...]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ()
        if not isinstance(payload, list):
            raise ValueError("paper trade store must contain a list")
        return tuple(_trade_from_payload(item) for item in payload)

    def save(self, trades: tuple[PaperTrade, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([_jsonable(asdict(trade)) for trade in trades], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def upsert(self, trade: PaperTrade) -> tuple[PaperTrade, ...]:
        trades = tuple(existing for existing in self.load() if existing.trade_id != trade.trade_id)
        updated = (*trades, trade)
        self.save(updated)
        return updated


def _trade_from_payload(payload: Any) -> PaperTrade:
    if not isinstance(payload, dict):
        raise ValueError("paper trade payloads must be mappings")
    signal_payload = payload["signal"]
    signal = BacktestSignal(
        symbol=signal_payload["symbol"],
        strategy=StrategyType(signal_payload["strategy"]),
        direction=TradeDirection(signal_payload["direction"]),
        generated_at=datetime.fromisoformat(signal_payload["generated_at"]),
        entry_price=signal_payload["entry_price"],
        stop_price=signal_payload["stop_price"],
        target_price=signal_payload["target_price"],
        quantity=signal_payload["quantity"],
        risk_amount=signal_payload["risk_amount"],
        confidence_score=signal_payload["confidence_score"],
    )
    return PaperTrade(
        trade_id=payload["trade_id"],
        signal=signal,
        state=PaperTradeState(payload["state"]),
        created_at=datetime.fromisoformat(payload["created_at"]),
        updated_at=datetime.fromisoformat(payload["updated_at"]),
        analysis_payload=payload["analysis_payload"],
        entry_time=_datetime_or_none(payload.get("entry_time")),
        entry_price=payload.get("entry_price"),
        exit_time=_datetime_or_none(payload.get("exit_time")),
        exit_price=payload.get("exit_price"),
        net_pnl=payload["net_pnl"],
        realized_r_multiple=payload["realized_r_multiple"],
        candles_waited=payload["candles_waited"],
        candles_held=payload["candles_held"],
        notes=tuple(payload["notes"]),
    )


def _datetime_or_none(value: Any) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value
