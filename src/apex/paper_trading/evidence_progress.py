"""Forward-paper evidence progress by canonical setup segment."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from apex.paper_trading.contracts import PaperTrade, TERMINAL_STATES


@dataclass(frozen=True, slots=True)
class EvidenceProgressSegment:
    """Forward evidence accumulated for one canonical segment."""

    dimensions: dict[str, str]
    closed_trade_count: int
    minimum_closed_trades: int
    remaining_closed_trades: int
    sample_sufficient: bool
    win_rate: float
    expectancy_r: float
    profit_factor: float | None
    maximum_drawdown_r: float


@dataclass(frozen=True, slots=True)
class ForwardEvidenceProgress:
    """Complete sample-progress snapshot across persisted paper trades."""

    total_closed_trades: int
    minimum_closed_trades: int
    segments: tuple[EvidenceProgressSegment, ...]

    @property
    def all_segments_sufficient(self) -> bool:
        return bool(self.segments) and all(item.sample_sufficient for item in self.segments)


def build_forward_evidence_progress(
    trades: tuple[PaperTrade, ...],
    *,
    minimum_closed_trades: int,
) -> ForwardEvidenceProgress:
    """Aggregate terminal paper outcomes by deterministic setup dimensions."""

    if minimum_closed_trades < 1:
        raise ValueError("minimum closed trades must be positive")

    closed = tuple(trade for trade in trades if trade.state in TERMINAL_STATES)
    grouped: dict[tuple[tuple[str, str], ...], list[PaperTrade]] = {}
    dimensions_by_key: dict[tuple[tuple[str, str], ...], dict[str, str]] = {}
    for trade in closed:
        dimensions = _segment_dimensions(trade)
        key = tuple(sorted(dimensions.items()))
        grouped.setdefault(key, []).append(trade)
        dimensions_by_key[key] = dimensions

    segments = tuple(
        _build_segment(
            dimensions=dimensions_by_key[key],
            trades=tuple(grouped[key]),
            minimum_closed_trades=minimum_closed_trades,
        )
        for key in sorted(grouped)
    )
    return ForwardEvidenceProgress(
        total_closed_trades=len(closed),
        minimum_closed_trades=minimum_closed_trades,
        segments=segments,
    )


def _segment_dimensions(trade: PaperTrade) -> dict[str, str]:
    payload = trade.analysis_payload
    raw = payload.get("setup_segment")
    if isinstance(raw, dict):
        dimensions = {str(key): str(value) for key, value in raw.items() if value is not None}
        if dimensions:
            return dimensions
    return {
        "market_type": str(payload.get("market_type", "futures")),
        "strategy": str(payload.get("strategy", trade.signal.strategy.value)),
        "direction": str(payload.get("direction", trade.signal.direction.value)),
        "symbol": trade.signal.symbol,
    }


def _build_segment(
    *,
    dimensions: dict[str, str],
    trades: tuple[PaperTrade, ...],
    minimum_closed_trades: int,
) -> EvidenceProgressSegment:
    outcomes = tuple(trade.realized_r_multiple for trade in trades)
    wins = tuple(value for value in outcomes if value > 0.0)
    losses = tuple(value for value in outcomes if value < 0.0)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    remaining = max(0, minimum_closed_trades - len(trades))
    return EvidenceProgressSegment(
        dimensions=dict(sorted(dimensions.items())),
        closed_trade_count=len(trades),
        minimum_closed_trades=minimum_closed_trades,
        remaining_closed_trades=remaining,
        sample_sufficient=remaining == 0,
        win_rate=(len(wins) / len(trades)) if trades else 0.0,
        expectancy_r=fmean(outcomes) if outcomes else 0.0,
        profit_factor=(gross_profit / gross_loss) if gross_loss > 0.0 else None,
        maximum_drawdown_r=_maximum_drawdown(outcomes),
    )


def _maximum_drawdown(outcomes: tuple[float, ...]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in outcomes:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown
