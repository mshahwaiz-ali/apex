from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import apex.strategies.geometry_audit as geometry_audit
from apex.strategies.contracts import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.geometry_audit import (
    ExecutionBufferPolicy,
    TargetQualityPolicy,
    TargetQualityTier,
    audit_targets_against_executable_stop,
    classify_target_quality,
    derive_execution_buffer,
    derive_execution_stop_geometry,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)

FORBIDDEN_IMPORT_PREFIXES = (
    "apex.application",
    "apex.cli",
    "apex.presentation",
)

FORBIDDEN_CALL_PREFIXES = (
    "generate_",
    "rank_",
    "select_",
    "score_",
    "filter_",
    "reject_",
    "deduplicate_",
    "resolve_collision",
    "classify_actionability",
)


def _module_path() -> Path:
    source = inspect.getsourcefile(geometry_audit)
    assert source is not None
    return Path(source)


def _module_tree() -> ast.Module:
    return ast.parse(_module_path().read_text(encoding="utf-8"))


def _candidate(direction: TradeDirection) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation = 95.0
        targets = (
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=105.0,
                label="tp1",
                rationale=("first structure",),
            ),
            TargetLevel(
                kind=TargetType.LIQUIDITY,
                price=110.0,
                label="tp2",
                rationale=("next liquidity",),
            ),
        )
    else:
        invalidation = 105.0
        targets = (
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=95.0,
                label="tp1",
                rationale=("first structure",),
            ),
            TargetLevel(
                kind=TargetType.LIQUIDITY,
                price=90.0,
                label="tp2",
                rationale=("next liquidity",),
            ),
        )

    entry = EntryZone(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.0,
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=1.0,
        mode=EntryMode.MARKET_NEAR,
        rationale=("fixture entry",),
    )
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=direction,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("fixture invalidation",),
        ),
        targets=TargetConcept(levels=targets),
        quality=RawQualityMetrics(
            trend_alignment=1.0,
            structure_quality=1.0,
            entry_quality=1.0,
            momentum_quality=1.0,
            volume_quality=1.0,
            liquidity_quality=1.0,
            target_space_quality=1.0,
        ),
        evidence=StrategyEvidence(supporting=("fixture evidence",)),
        metadata={},
    )


def _run_chain(direction: TradeDirection) -> tuple[float, tuple[TargetQualityTier, ...]]:
    candidate = _candidate(direction)
    buffer = derive_execution_buffer(
        atr=2.0,
        spread=0.2,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
            minimum_buffer=0.25,
            maximum_buffer=2.0,
        ),
    )
    stop = derive_execution_stop_geometry(
        direction=direction,
        preferred_entry=candidate.entry.preferred,
        structural_invalidation=candidate.invalidation.price,
        execution_buffer=buffer.execution_buffer,
    )
    target_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )
    quality = classify_target_quality(
        target_audit=target_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=1.0,
            strong_reward_to_risk=1.5,
        ),
    )
    return (
        stop.executable_stop,
        tuple(item.tier for item in quality.assessments),
    )


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def test_full_geometry_chain_is_deterministic_for_long_and_short() -> None:
    assert _run_chain(TradeDirection.LONG) == _run_chain(TradeDirection.LONG)
    assert _run_chain(TradeDirection.SHORT) == _run_chain(TradeDirection.SHORT)


def test_full_geometry_chain_is_directionally_symmetric() -> None:
    long_stop, long_tiers = _run_chain(TradeDirection.LONG)
    short_stop, short_tiers = _run_chain(TradeDirection.SHORT)

    assert long_stop == 94.0
    assert short_stop == 106.0
    assert long_tiers == short_tiers
    assert long_tiers == (
        TargetQualityTier.BELOW_MINIMUM,
        TargetQualityTier.STRONG,
    )


def test_full_geometry_chain_preserves_candidate_objects() -> None:
    candidate = _candidate(TradeDirection.LONG)
    original_entry = candidate.entry
    original_invalidation = candidate.invalidation
    original_targets = candidate.targets
    original_metadata = candidate.metadata

    buffer = derive_execution_buffer(
        atr=2.0,
        spread=0.2,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
        ),
    )
    stop = derive_execution_stop_geometry(
        direction=candidate.direction,
        preferred_entry=candidate.entry.preferred,
        structural_invalidation=candidate.invalidation.price,
        execution_buffer=buffer.execution_buffer,
    )
    target_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )
    classify_target_quality(
        target_audit=target_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=1.0,
            strong_reward_to_risk=2.0,
        ),
    )

    assert candidate.entry is original_entry
    assert candidate.invalidation is original_invalidation
    assert candidate.targets is original_targets
    assert candidate.metadata is original_metadata


def test_geometry_module_has_no_application_cli_or_presentation_dependency() -> None:
    imported_modules: set[str] = set()

    for node in _module_tree().body:
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden = {
        module for module in imported_modules if module.startswith(FORBIDDEN_IMPORT_PREFIXES)
    }
    assert forbidden == set()


def test_geometry_module_does_not_call_live_pipeline_decision_services() -> None:
    calls = {_call_name(node) for node in ast.walk(_module_tree()) if isinstance(node, ast.Call)}

    forbidden = {call_name for call_name in calls if call_name.startswith(FORBIDDEN_CALL_PREFIXES)}
    assert forbidden == set()


def test_geometry_module_exports_the_complete_batch7_surface() -> None:
    expected = {
        "CandidateGeometryAudit",
        "ExecutableRiskTargetAudit",
        "ExecutableTargetAudit",
        "ExecutionBufferDecision",
        "ExecutionBufferPolicy",
        "ExecutionStopGeometry",
        "GeometryIssueCode",
        "TargetGeometryAudit",
        "TargetQualityAssessment",
        "TargetQualityAudit",
        "TargetQualityPolicy",
        "TargetQualityTier",
        "audit_candidate_geometry",
        "audit_targets_against_executable_stop",
        "classify_target_quality",
        "derive_execution_buffer",
        "derive_execution_stop_geometry",
    }

    assert expected <= set(geometry_audit.__all__)
