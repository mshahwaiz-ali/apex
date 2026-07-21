from apex.strategies.continuation_freshness import (
    ContinuationFreshness,
    ContinuationState,
)
from apex.strategies.continuation_routing import (
    ContinuationRoute,
    route_continuation,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.reversal_watch import ReversalWatch, ReversalWatchState


def _freshness(state: ContinuationState) -> ContinuationFreshness:
    return ContinuationFreshness(
        state=state,
        impulse_travel_atr=2.0,
        objective_consumption=0.7,
        remaining_target_room_atr=1.0,
        ema_extension_atr=1.2,
        vwap_extension_atr=1.4,
        momentum_decelerating=state is ContinuationState.EXHAUSTED,
        reasons=("measured continuation freshness",),
    )


def _watch(state: ReversalWatchState) -> ReversalWatch:
    return ReversalWatch(
        state=state,
        reversal_direction=TradeDirection.LONG,
        swing_failure=state is not ReversalWatchState.NONE,
        wick_rejection=state is not ReversalWatchState.NONE,
        recovery_present=state is not ReversalWatchState.NONE,
        reclaim_level=100.0,
        reclaim_complete=state is ReversalWatchState.TRIGGERED,
        trigger_required=state is not ReversalWatchState.TRIGGERED,
        reasons=("measured reversal evidence",),
    )


def test_fresh_break_allows_current_continuation() -> None:
    decision = route_continuation(
        freshness=_freshness(ContinuationState.FRESH_BREAK),
    )

    assert decision.route is ContinuationRoute.CONTINUATION_ALLOWED
    assert decision.continuation_allowed is True
    assert decision.current_execution_allowed is True
    assert decision.reversal_candidate_allowed is False


def test_mature_continuation_is_conditional_only() -> None:
    decision = route_continuation(
        freshness=_freshness(ContinuationState.MATURE_CONTINUATION),
    )

    assert decision.route is ContinuationRoute.CONDITIONAL_CONTINUATION
    assert decision.continuation_allowed is True
    assert decision.current_execution_allowed is False


def test_exhausted_move_blocks_new_continuation_without_reversal_evidence() -> None:
    decision = route_continuation(
        freshness=_freshness(ContinuationState.EXHAUSTED),
    )

    assert decision.route is ContinuationRoute.NO_NEW_CONTINUATION
    assert decision.continuation_allowed is False
    assert decision.reversal_candidate_allowed is False


def test_reversal_watch_does_not_create_automatic_opposite_trade() -> None:
    decision = route_continuation(
        freshness=_freshness(ContinuationState.EXHAUSTED),
        reversal_watch=_watch(ReversalWatchState.WATCH),
    )

    assert decision.route is ContinuationRoute.REVERSAL_WATCH
    assert decision.continuation_allowed is False
    assert decision.current_execution_allowed is False
    assert decision.reversal_candidate_allowed is False


def test_triggered_reversal_only_permits_later_strategy_evaluation() -> None:
    decision = route_continuation(
        freshness=_freshness(ContinuationState.EXHAUSTED),
        reversal_watch=_watch(ReversalWatchState.TRIGGERED),
    )

    assert decision.route is ContinuationRoute.REVERSAL_TRIGGERED
    assert decision.continuation_allowed is False
    assert decision.current_execution_allowed is False
    assert decision.reversal_candidate_allowed is True
