from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application.decision_analysis import _best_rank_record, _scan_sort_key
from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    SequenceRole,
    SymbolOpportunityPortfolio,
    TradeOpportunity,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    executable: bool,
    symbol: str = "BTCUSDT",
) -> DiscoverySetup:
    current_price = 100.0 if executable else 98.0
    return DiscoverySetup(
        symbol=symbol,
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=(EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED),
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=70.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=current_price,
            maximum_chase_price=102.0,
            current_price_inside_zone=99.0 <= current_price <= 101.0,
        ),
        stop_loss=StopLoss(97.0, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",)),),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=executable,
    )


def _record(candidate_id: str, *, rank: int, score: float) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id=candidate_id,
        rank=rank,
        final_rank_score=score,
    )


def _analysis(
    *,
    symbol: str,
    portfolio: SymbolOpportunityPortfolio,
    primary: SimpleNamespace | None,
    alternatives: tuple[SimpleNamespace, ...] = (),
    rejected: tuple[SimpleNamespace, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        opportunity_portfolio=portfolio,
        candidate_ranking=SimpleNamespace(
            primary=primary,
            alternatives=alternatives,
            rejected=rejected,
        ),
    )


def test_best_rank_record_matches_canonical_portfolio_opportunity() -> None:
    setup = _setup("nearby-retained", executable=False)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
        nearby_long=TradeOpportunity(
            setup.candidate_id,
            setup,
            SequenceRole.NEARBY,
        ),
    )
    rejected_global_best = _record("rejected", rank=1, score=99.0)
    retained = _record("nearby-retained", rank=3, score=72.0)
    analysis = _analysis(
        symbol="BTCUSDT",
        portfolio=portfolio,
        primary=None,
        alternatives=(retained,),
        rejected=(rejected_global_best,),
    )

    assert _best_rank_record(analysis) is retained


def test_best_rank_record_does_not_fall_back_to_rejected_candidate() -> None:
    setup = _setup("retained-without-record", executable=False)
    portfolio = SymbolOpportunityPortfolio(
        symbol="BTCUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
        nearby_long=TradeOpportunity(
            setup.candidate_id,
            setup,
            SequenceRole.NEARBY,
        ),
    )
    rejected = _record("rejected", rank=1, score=99.0)
    analysis = _analysis(
        symbol="BTCUSDT",
        portfolio=portfolio,
        primary=None,
        rejected=(rejected,),
    )

    assert _best_rank_record(analysis) is None


def test_scan_sort_uses_retained_portfolio_score_not_rejected_global_rank() -> None:
    first_setup = _setup(
        "first-retained",
        executable=False,
        symbol="AAAUSDT",
    )
    second_setup = _setup(
        "second-retained",
        executable=False,
        symbol="BBBUSDT",
    )
    first_portfolio = SymbolOpportunityPortfolio(
        symbol="AAAUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
        nearby_long=TradeOpportunity(
            first_setup.candidate_id,
            first_setup,
            SequenceRole.NEARBY,
        ),
    )
    second_portfolio = SymbolOpportunityPortfolio(
        symbol="BBBUSDT",
        cmp=98.0,
        analysis_timestamp=NOW,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
        nearby_long=TradeOpportunity(
            second_setup.candidate_id,
            second_setup,
            SequenceRole.NEARBY,
        ),
    )
    first = _analysis(
        symbol="AAAUSDT",
        portfolio=first_portfolio,
        primary=None,
        alternatives=(_record("first-retained", rank=4, score=68.0),),
        rejected=(_record("rejected-high", rank=1, score=99.0),),
    )
    second = _analysis(
        symbol="BBBUSDT",
        portfolio=second_portfolio,
        primary=None,
        alternatives=(_record("second-retained", rank=2, score=76.0),),
    )

    assert _scan_sort_key(second) < _scan_sort_key(first)
