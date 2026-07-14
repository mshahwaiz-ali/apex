from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from apex.paper_trading import PaperTrade
from apex.validation import evidence as evidence_module
from apex.validation.evidence import generate_paper_evidence


def _trade(*, trade_id: str, pnl: float, r_multiple: float, hour: int) -> PaperTrade:
    return cast(
        PaperTrade,
        SimpleNamespace(
            trade_id=trade_id,
            is_open=False,
            exit_time=datetime(2026, 7, 14, hour, tzinfo=UTC),
            updated_at=datetime(2026, 7, 14, hour, tzinfo=UTC),
            net_pnl=pnl,
            realized_r_multiple=r_multiple,
        ),
    )


def test_generate_paper_evidence_derives_expectancy_and_drawdown(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        evidence_module,
        "build_paper_replay_report",
        lambda trades: {"failure_count": 1},
    )

    result = generate_paper_evidence(
        (
            _trade(trade_id="a", pnl=10.0, r_multiple=1.0, hour=10),
            _trade(trade_id="b", pnl=-15.0, r_multiple=-1.5, hour=11),
            _trade(trade_id="c", pnl=5.0, r_multiple=0.5, hour=12),
        )
    )

    assert result.closed_trades == 3
    assert result.win_rate == 2 / 3
    assert result.paper_expectancy == 0.0
    assert result.paper_maximum_drawdown == 15.0
    assert result.critical_lifecycle_failures == 1


def test_generate_paper_evidence_handles_empty_store(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        evidence_module,
        "build_paper_replay_report",
        lambda trades: {"failure_count": 0},
    )

    result = generate_paper_evidence(())

    assert result.closed_trades == 0
    assert result.win_rate == 0.0
    assert result.paper_expectancy == 0.0
    assert result.paper_maximum_drawdown == 0.0
