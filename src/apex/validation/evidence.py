"""Generate deterministic P1 evidence from persisted paper trades."""

from __future__ import annotations

from dataclasses import dataclass

from apex.paper_trading import PaperTrade, build_paper_replay_report


@dataclass(frozen=True, slots=True)
class GeneratedPaperEvidence:
    """Forward metrics derived only from auditable stored paper trades."""

    closed_trades: int
    win_rate: float
    paper_expectancy: float
    paper_maximum_drawdown: float
    critical_lifecycle_failures: int


def generate_paper_evidence(trades: tuple[PaperTrade, ...]) -> GeneratedPaperEvidence:
    """Derive P1 metrics without inventing unavailable operational evidence."""

    closed = tuple(
        sorted(
            (trade for trade in trades if not trade.is_open),
            key=lambda trade: (trade.exit_time or trade.updated_at, trade.trade_id),
        )
    )
    wins = sum(1 for trade in closed if trade.net_pnl > 0.0)
    expectancy = sum(trade.realized_r_multiple for trade in closed) / len(closed) if closed else 0.0

    cumulative = 0.0
    peak = 0.0
    maximum_drawdown = 0.0
    for trade in closed:
        cumulative += trade.net_pnl
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)

    replay = build_paper_replay_report(trades)
    return GeneratedPaperEvidence(
        closed_trades=len(closed),
        win_rate=wins / len(closed) if closed else 0.0,
        paper_expectancy=expectancy,
        paper_maximum_drawdown=maximum_drawdown,
        critical_lifecycle_failures=int(replay["failure_count"]),
    )
