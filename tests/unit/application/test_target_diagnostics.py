from __future__ import annotations

import pytest
from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.discovery_contracts import TakeProfit, TargetRole
from apex.application.discovery_setup import (
    _target_basis,
    _target_role,
    _target_timeframe,
)
from apex.strategies.contracts import TargetType


def test_target_basis_preserves_original_source_type() -> None:
    assert _target_basis(TargetType.STRUCTURAL) == "strategy_supplied_structural_level"
    assert _target_basis(TargetType.LIQUIDITY) == "strategy_supplied_liquidity_level"
    assert _target_basis(TargetType.RANGE) == "strategy_supplied_range_boundary"
    assert _target_basis(TargetType.EXPANSION) == "strategy_supplied_expansion_projection"


def test_target_roles_do_not_prematurely_qualify_runner() -> None:
    assert _target_role(TargetType.STRUCTURAL, "TP1") is TargetRole.PRIMARY
    assert _target_role(TargetType.LIQUIDITY, "TP2") is TargetRole.CONTINUATION
    assert _target_role(TargetType.EXPANSION, "TP3") is TargetRole.EXTENSION_CANDIDATE


def test_target_timeframe_uses_existing_candidate_metadata() -> None:
    candidate = _candidate()
    candidate = candidate.__class__(
        **{
            name: getattr(candidate, name)
            for name in candidate.__dataclass_fields__
            if name != "metadata"
        },
        metadata={**candidate.metadata, "setup_timeframe": "15m"},
    )
    assert _target_timeframe(candidate) == "15m"


def test_missing_target_timeframe_is_not_fabricated() -> None:
    candidate = _candidate()
    candidate = candidate.__class__(
        **{
            name: getattr(candidate, name)
            for name in candidate.__dataclass_fields__
            if name != "metadata"
        },
        metadata={},
    )
    assert _target_timeframe(candidate) is None


def test_take_profit_rejects_synthetic_target_flag() -> None:
    with pytest.raises(ValueError, match="strategy supplied"):
        TakeProfit(
            label="TP1",
            price=103.0,
            reward=3.0,
            risk_reward=1.5,
            rationale=("strategy target",),
            synthetic=True,
        )


def test_runner_qualification_requires_extension_role() -> None:
    with pytest.raises(ValueError, match="extension target role"):
        TakeProfit(
            label="TP1",
            price=103.0,
            reward=3.0,
            risk_reward=1.5,
            rationale=("strategy target",),
            runner_qualified=True,
        )
