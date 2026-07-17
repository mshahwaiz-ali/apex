"""Tests for typed candidate-evidence normalization."""

from apex.strategies import (
    StrategyEvidence,
    StrategyEvidenceKind,
    normalize_strategy_evidence,
    strategy_evidence_payload,
    strategy_evidence_summary,
)


def _evidence() -> StrategyEvidence:
    return StrategyEvidence(
        supporting=("volume expansion confirmed", "breakout held"),
        contradictions=("higher timeframe disagrees",),
        warnings=("entry is moderately extended",),
        feature_references=("rvol_15m",),
        structure_references=("prior_session_high",),
        liquidity_references=("buy_side_cluster",),
    )


def test_normalization_preserves_canonical_category_and_source_order() -> None:
    normalized = normalize_strategy_evidence(_evidence())

    assert tuple(item.kind for item in normalized) == (
        StrategyEvidenceKind.SUPPORTING,
        StrategyEvidenceKind.SUPPORTING,
        StrategyEvidenceKind.CONTRADICTION,
        StrategyEvidenceKind.WARNING,
        StrategyEvidenceKind.FEATURE_REFERENCE,
        StrategyEvidenceKind.STRUCTURE_REFERENCE,
        StrategyEvidenceKind.LIQUIDITY_REFERENCE,
    )
    assert tuple(item.code for item in normalized) == (
        "SUPPORTING_001",
        "SUPPORTING_002",
        "CONTRADICTION_001",
        "WARNING_001",
        "FEATURE_REFERENCE_001",
        "STRUCTURE_REFERENCE_001",
        "LIQUIDITY_REFERENCE_001",
    )


def test_payload_is_typed_and_transparent() -> None:
    payload = strategy_evidence_payload(_evidence())

    assert payload[0] == {
        "kind": "supporting",
        "code": "SUPPORTING_001",
        "detail": "volume expansion confirmed",
    }
    assert payload[-1] == {
        "kind": "liquidity_reference",
        "code": "LIQUIDITY_REFERENCE_001",
        "detail": "buy_side_cluster",
    }


def test_summary_includes_zero_count_categories() -> None:
    summary = strategy_evidence_summary(StrategyEvidence(supporting=("trend aligned",)))

    assert summary == {
        "supporting": 1,
        "contradiction": 0,
        "warning": 0,
        "feature_reference": 0,
        "structure_reference": 0,
        "liquidity_reference": 0,
    }
