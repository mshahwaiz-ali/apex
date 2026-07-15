from types import SimpleNamespace
from typing import cast

from apex.paper_trading.contracts import PaperTrade, PaperTradeState
from apex.paper_trading.evidence_progress import build_forward_evidence_progress


def _trade(*, strategy: str, realized_r: float) -> PaperTrade:
    signal = SimpleNamespace(
        strategy=SimpleNamespace(value=strategy),
        direction=SimpleNamespace(value="long"),
        symbol="BTCUSDT",
    )
    return cast(
        PaperTrade,
        SimpleNamespace(
            state=PaperTradeState.TARGET_HIT if realized_r > 0 else PaperTradeState.STOPPED,
            analysis_payload={
                "setup_segment": {
                    "market_type": "futures",
                    "strategy": strategy,
                    "risk_mode": "STANDARD",
                }
            },
            signal=signal,
            realized_r_multiple=realized_r,
        ),
    )


def test_build_forward_evidence_progress_groups_segments() -> None:
    progress = build_forward_evidence_progress(
        (
            _trade(strategy="trend_pullback", realized_r=2.0),
            _trade(strategy="trend_pullback", realized_r=-1.0),
            _trade(strategy="breakout_retest", realized_r=1.5),
        ),
        minimum_closed_trades=2,
    )

    assert progress.total_closed_trades == 3
    assert len(progress.segments) == 2
    breakout, trend = progress.segments
    assert breakout.closed_trade_count == 1
    assert breakout.remaining_closed_trades == 1
    assert not breakout.sample_sufficient
    assert trend.closed_trade_count == 2
    assert trend.sample_sufficient
    assert trend.win_rate == 0.5
    assert trend.expectancy_r == 0.5
    assert trend.profit_factor == 2.0
    assert trend.maximum_drawdown_r == 1.0
    assert not progress.all_segments_sufficient


def test_build_forward_evidence_progress_rejects_invalid_threshold() -> None:
    try:
        build_forward_evidence_progress((), minimum_closed_trades=0)
    except ValueError as exc:
        assert str(exc) == "minimum closed trades must be positive"
    else:
        raise AssertionError("expected ValueError")
