"""Fail-soft construction of timestamped Binance futures evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast

from apex.data.providers.base import FuturesEvidenceProvider
from apex.domain.futures_evidence import (
    FundingRateSnapshot,
    MarketEvidenceBundle,
    OpenInterestSnapshot,
    PremiumIndexSnapshot,
    TakerFlowSnapshot,
)
from apex.domain.models import ExchangeFilterSnapshot, OrderBookSnapshot, TickerSnapshot

T = TypeVar("T")


def build_market_evidence_bundle(
    provider: object,
    symbol: str,
    *,
    as_of: datetime | None = None,
    period: str = "5m",
    limit: int = 100,
    max_age: timedelta = timedelta(minutes=30),
) -> MarketEvidenceBundle:
    """Fetch independent evidence streams without fabricating unavailable observations."""

    timestamp = as_of or datetime.now(UTC)
    evidence_provider = cast(FuturesEvidenceProvider, provider)
    missing: list[tuple[str, str]] = []

    funding: tuple[FundingRateSnapshot, ...] = _safe_fetch(
        "funding",
        lambda: evidence_provider.fetch_funding_rates(symbol, limit),
        missing,
        default=cast(tuple[FundingRateSnapshot, ...], ()),
    )
    open_interest: tuple[OpenInterestSnapshot, ...] = _safe_fetch(
        "open_interest",
        lambda: evidence_provider.fetch_open_interest_history(symbol, period, limit),
        missing,
        default=cast(tuple[OpenInterestSnapshot, ...], ()),
    )
    taker_flow: tuple[TakerFlowSnapshot, ...] = _safe_fetch(
        "taker_flow",
        lambda: evidence_provider.fetch_taker_flow_history(symbol, period, limit),
        missing,
        default=cast(tuple[TakerFlowSnapshot, ...], ()),
    )
    premium = _safe_fetch(
        "premium_index",
        lambda: evidence_provider.fetch_premium_index(symbol),
        missing,
        default=None,
    )
    ticker: TickerSnapshot | None = _safe_fetch(
        "ticker",
        lambda: cast(Any, provider).fetch_ticker(symbol),
        missing,
        default=None,
    )
    order_book: OrderBookSnapshot | None = _safe_fetch(
        "order_book",
        lambda: cast(Any, provider).fetch_order_book(symbol, 20),
        missing,
        default=None,
    )
    exchange_filters: ExchangeFilterSnapshot | None = _safe_fetch(
        "exchange_filters",
        lambda: cast(Any, provider).fetch_exchange_filters(symbol),
        missing,
        default=None,
    )

    funding = _fresh_series(
        "funding", funding, timestamp, max_age=timedelta(hours=12), missing=missing
    )
    open_interest = _fresh_series(
        "open_interest", open_interest, timestamp, max_age=max_age, missing=missing
    )
    taker_flow = _fresh_series(
        "taker_flow", taker_flow, timestamp, max_age=max_age, missing=missing
    )
    if premium is not None and timestamp - premium.captured_at > max_age:
        missing.append(("premium_index", "stale"))
        premium = None
    ticker = _fresh_snapshot("ticker", ticker, timestamp, max_age, missing)
    order_book = _fresh_snapshot("order_book", order_book, timestamp, max_age, missing)

    return MarketEvidenceBundle(
        symbol=symbol.upper(),
        as_of=timestamp,
        funding=tuple(funding),
        open_interest=tuple(open_interest),
        taker_flow=tuple(taker_flow),
        premium_index=premium,
        ticker=ticker,
        order_book=order_book,
        exchange_filters=exchange_filters,
        missing_reasons=tuple(sorted(set(missing))),
        source=getattr(provider, "name", "unknown"),
    )


def _safe_fetch(
    name: str,
    operation: Callable[[], T],
    missing: list[tuple[str, str]],
    *,
    default: T,
) -> T:
    try:
        return operation()
    except Exception as exc:
        missing.append((name, f"unavailable:{type(exc).__name__}"))
        return default


def _fresh_series(
    name: str,
    values: tuple[T, ...],
    as_of: datetime,
    *,
    max_age: timedelta,
    missing: list[tuple[str, str]],
) -> tuple[T, ...]:
    if not values:
        if not any(item == name for item, _ in missing):
            missing.append((name, "empty"))
        return ()
    latest = values[-1]
    observed_at = getattr(latest, "funding_time", getattr(latest, "captured_at", None))
    if not isinstance(observed_at, datetime) or as_of - observed_at > max_age:
        missing.append((name, "stale"))
        return ()
    return values


def _fresh_snapshot(
    name: str,
    value: T | None,
    as_of: datetime,
    max_age: timedelta,
    missing: list[tuple[str, str]],
) -> T | None:
    if value is None:
        return None
    captured_at = getattr(value, "captured_at", None)
    if not isinstance(captured_at, datetime) or as_of - captured_at > max_age:
        missing.append((name, "stale"))
        return None
    return value


__all__ = [
    "FundingRateSnapshot",
    "MarketEvidenceBundle",
    "OpenInterestSnapshot",
    "PremiumIndexSnapshot",
    "TakerFlowSnapshot",
    "build_market_evidence_bundle",
]
