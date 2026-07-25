from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import apex.strategies.registry as registry
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate


def test_registered_generators_apply_target_ladder_after_routing(monkeypatch) -> None:
    generated = cast(tuple[TradeCandidate, ...], (object(),))
    routed = cast(tuple[TradeCandidate, ...], (object(),))
    laddered = cast(tuple[TradeCandidate, ...], (object(),))
    context = cast(StrategyContext, object())
    calls: list[str] = []

    def generator(
        supplied_context: StrategyContext,
        *,
        decision_time: datetime,
    ) -> tuple[TradeCandidate, ...]:
        assert supplied_context is context
        assert decision_time == datetime(2026, 7, 25, tzinfo=UTC)
        calls.append("generate")
        return generated

    def route(
        supplied_context: StrategyContext,
        candidates: tuple[TradeCandidate, ...],
    ) -> tuple[TradeCandidate, ...]:
        assert supplied_context is context
        assert candidates is generated
        calls.append("route")
        return routed

    def apply_ladder(
        supplied_context: StrategyContext,
        candidates: tuple[TradeCandidate, ...],
    ) -> tuple[TradeCandidate, ...]:
        assert supplied_context is context
        assert candidates is routed
        calls.append("ladder")
        return laddered

    monkeypatch.setattr(registry, "route_breakout_candidates", route)
    monkeypatch.setattr(registry, "apply_target_ladder_to_candidates", apply_ladder)

    result = registry.run_strategy_generator(
        generator,
        context,
        decision_time=datetime(2026, 7, 25, tzinfo=UTC),
    )

    assert result is laddered
    assert calls == ["generate", "route", "ladder"]
