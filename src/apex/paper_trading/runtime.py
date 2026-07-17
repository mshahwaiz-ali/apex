"""Application boundary for repeatable paper-operation cycles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from apex.data.providers.errors import MarketDataProviderError
from apex.domain.models import Candle
from apex.paper_trading.contracts import PaperTradeConfig
from apex.paper_trading.operations import PaperOperationCycleResult, run_paper_operation_cycle
from apex.paper_trading.store import PaperTradeStore


class CandleProvider(Protocol):
    """Minimal closed-candle provider required by the paper runtime."""

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int,
    ) -> Sequence[Candle]: ...


@dataclass(frozen=True, slots=True)
class PaperRuntimeResult:
    """Outcome of one provider-backed paper-operation invocation."""

    cycle: PaperOperationCycleResult
    requested_symbols: tuple[str, ...]
    successful_symbols: tuple[str, ...]
    provider_failures: tuple[tuple[str, str], ...]

    @property
    def fully_collected(self) -> bool:
        return not self.provider_failures


def run_provider_backed_paper_cycle(
    *,
    store: PaperTradeStore,
    provider: CandleProvider,
    market_type: str,
    timeframe: str,
    candle_limit: int,
    started_at: datetime,
    completed_at: datetime | None = None,
    config: PaperTradeConfig | None = None,
    daily_report_date: date | None = None,
    daily_report_path: Path | None = None,
    force_report: bool = False,
    initial_wallet_balance: float | None = None,
    maximum_wallet_exposure_pct: float = 100.0,
    maximum_open_risk_pct: float = 100.0,
) -> PaperRuntimeResult:
    """Fetch each active symbol once and execute one deterministic paper cycle.

    Provider failures are isolated per symbol. Failed symbols receive no fabricated
    candles and remain unchanged in the canonical store.
    """

    if not timeframe.strip():
        raise ValueError("paper runtime timeframe cannot be empty")
    if candle_limit < 1:
        raise ValueError("paper runtime candle limit must be positive")

    normalized_market = market_type.strip().lower()
    trades = store.load()
    symbols = tuple(
        sorted(
            {
                trade.signal.symbol
                for trade in trades
                if trade.is_open
                and str(trade.analysis_payload.get("market_type", "futures")).lower()
                == normalized_market
            }
        )
    )

    candles_by_symbol: dict[str, tuple[Candle, ...]] = {}
    failures: list[tuple[str, str]] = []
    for symbol in symbols:
        try:
            candles_by_symbol[symbol] = tuple(
                provider.fetch_candles(symbol, timeframe, limit=candle_limit)
            )
        except (MarketDataProviderError, ValueError) as exc:
            failures.append((symbol, str(exc)))

    cycle = run_paper_operation_cycle(
        store=store,
        candles_by_symbol=candles_by_symbol,
        market_type=normalized_market,
        config=config,
        started_at=started_at,
        completed_at=completed_at,
        daily_report_date=daily_report_date,
        daily_report_path=daily_report_path,
        force_report=force_report,
        initial_wallet_balance=initial_wallet_balance,
        maximum_wallet_exposure_pct=maximum_wallet_exposure_pct,
        maximum_open_risk_pct=maximum_open_risk_pct,
    )
    return PaperRuntimeResult(
        cycle=cycle,
        requested_symbols=symbols,
        successful_symbols=tuple(sorted(candles_by_symbol)),
        provider_failures=tuple(sorted(failures)),
    )
