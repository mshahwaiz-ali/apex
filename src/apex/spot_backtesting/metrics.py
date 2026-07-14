"""Portfolio-level metrics for deterministic spot backtests."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from apex.spot_backtesting.contracts import (
    SpotEquityPoint,
    SpotPortfolioMetrics,
    SpotTradeRecord,
)


def compute_spot_portfolio_metrics(
    trades: Sequence[SpotTradeRecord],
    equity_curve: Sequence[SpotEquityPoint],
    *,
    starting_cash: float,
) -> SpotPortfolioMetrics:
    """Compute expectancy-focused portfolio statistics."""
    returns = [trade.return_pct for trade in trades]
    wins = [trade.net_pnl for trade in trades if trade.net_pnl > 0.0]
    losses = [trade.net_pnl for trade in trades if trade.net_pnl < 0.0]
    ending_equity = equity_curve[-1].equity if equity_curve else starting_cash
    profit_factor = None
    if losses:
        profit_factor = sum(wins) / abs(sum(losses))
    elif wins:
        profit_factor = float("inf")

    return SpotPortfolioMetrics(
        trade_count=len(trades),
        win_rate=_ratio(sum(value > 0.0 for value in returns), len(returns)),
        average_return_pct=_average(returns),
        expectancy_pct=_average(returns),
        profit_factor=profit_factor,
        maximum_drawdown_pct=_maximum_drawdown(equity_curve),
        ending_equity=ending_equity,
        total_return_pct=((ending_equity / starting_cash) - 1.0) * 100.0,
        average_exposure_pct=_average([point.exposure_pct for point in equity_curve]),
        maximum_exposure_pct=max((point.exposure_pct for point in equity_curve), default=0.0),
        average_concurrent_positions=_average(
            [float(point.concurrent_positions) for point in equity_curve]
        ),
        maximum_concurrent_positions=max(
            (point.concurrent_positions for point in equity_curve), default=0
        ),
        average_holding_duration_seconds=_average(
            [trade.holding_duration_seconds for trade in trades]
        ),
        strategy_breakdown=_breakdown(trades, lambda trade: trade.strategy),
        symbol_breakdown=_breakdown(trades, lambda trade: trade.symbol),
        regime_breakdown=_breakdown(trades, lambda trade: trade.market_regime),
        score_band_breakdown=_breakdown(trades, lambda trade: trade.score_band),
        exit_reason_breakdown=_count_breakdown(
            trades, lambda trade: trade.exit_reason.value
        ),
    )


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _maximum_drawdown(equity_curve: Sequence[SpotEquityPoint]) -> float:
    peak = 0.0
    maximum = 0.0
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak > 0.0:
            maximum = max(maximum, (peak - point.equity) / peak * 100.0)
    return maximum


def _breakdown(
    trades: Sequence[SpotTradeRecord],
    key: Callable[[SpotTradeRecord], str],
) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        grouped[key(trade)].append(trade.return_pct)
    return {name: _average(grouped[name]) for name in sorted(grouped)}


def _count_breakdown(
    trades: Sequence[SpotTradeRecord],
    key: Callable[[SpotTradeRecord], str],
) -> dict[str, int]:
    grouped: dict[str, int] = defaultdict(int)
    for trade in trades:
        grouped[key(trade)] += 1
    return {name: grouped[name] for name in sorted(grouped)}
