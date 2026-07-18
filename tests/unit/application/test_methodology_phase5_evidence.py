from __future__ import annotations

from apex.application.methodology_contracts import EvidenceEffect, EvidenceFamily
from apex.application.methodology_phase5_evidence import (
    selected_candidate_methodology_evidence,
)


def _diagnostics() -> dict[str, object]:
    return {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "evidence": [
                    {
                        "kind": "supporting",
                        "code": "SUPPORTING_001",
                        "detail": "volume expansion confirms breakout participation",
                    },
                    {
                        "kind": "feature_reference",
                        "code": "FEATURE_REFERENCE_001",
                        "detail": "RSI and stochastic momentum remain constructive",
                    },
                    {
                        "kind": "liquidity_reference",
                        "code": "LIQUIDITY_REFERENCE_001",
                        "detail": "liquidity sweep recovered above support",
                    },
                    {
                        "kind": "contradiction",
                        "code": "CONTRADICTION_001",
                        "detail": "higher timeframe resistance remains nearby",
                    },
                ],
            },
            {
                "candidate_id": "candidate-2",
                "evidence": [
                    {
                        "kind": "supporting",
                        "code": "SUPPORTING_001",
                        "detail": "unrelated candidate volume evidence",
                    }
                ],
            },
        ]
    }


def test_selected_candidate_evidence_maps_to_canonical_families() -> None:
    evidence, contradictions = selected_candidate_methodology_evidence(
        _diagnostics(), candidate_id="candidate-1"
    )

    assert [item.family for item in evidence] == [
        EvidenceFamily.PARTICIPATION,
        EvidenceFamily.MOMENTUM,
        EvidenceFamily.LIQUIDITY,
        EvidenceFamily.BROAD_CONTEXT,
    ]
    assert evidence[0].effect is EvidenceEffect.SUPPORTS
    assert evidence[1].independence_group == "momentum_oscillators"
    assert evidence[2].independence_group == "liquidity"
    assert len(contradictions) == 1
    assert contradictions[0].family is EvidenceFamily.BROAD_CONTEXT
    assert contradictions[0].code == "CONTRADICTION_001"


def test_selected_candidate_projection_excludes_other_candidates() -> None:
    evidence, _contradictions = selected_candidate_methodology_evidence(
        _diagnostics(), candidate_id="candidate-1"
    )

    assert all("unrelated candidate" not in item.reason for item in evidence)


def test_missing_candidate_or_diagnostics_returns_empty_evidence() -> None:
    assert selected_candidate_methodology_evidence(None, candidate_id="candidate-1") == (
        (),
        (),
    )
    assert selected_candidate_methodology_evidence(_diagnostics(), candidate_id="missing") == (
        (),
        (),
    )


def test_warning_is_data_quality_neutral_evidence() -> None:
    diagnostics = {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "evidence": [
                    {
                        "kind": "warning",
                        "code": "WARNING_001",
                        "detail": "ticker metadata is incomplete",
                    }
                ],
            }
        ]
    }

    evidence, contradictions = selected_candidate_methodology_evidence(
        diagnostics, candidate_id="candidate-1"
    )

    assert len(evidence) == 1
    assert evidence[0].family is EvidenceFamily.DATA_QUALITY
    assert evidence[0].effect is EvidenceEffect.NEUTRAL
    assert contradictions == ()


def test_duplicate_phase5_records_are_deduplicated_in_source_order() -> None:
    duplicate = {
        "kind": "supporting",
        "code": "SUPPORTING_001",
        "detail": "volume expansion confirms breakout participation",
    }
    diagnostics = {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "evidence": [
                    duplicate,
                    dict(duplicate),
                    {
                        "kind": "feature_reference",
                        "code": "FEATURE_REFERENCE_001",
                        "detail": "RSI momentum remains constructive",
                    },
                ],
            }
        ]
    }

    evidence, contradictions = selected_candidate_methodology_evidence(
        diagnostics, candidate_id="candidate-1"
    )

    assert [item.source for item in evidence] == [
        "phase5:candidate-1:supporting_001",
        "phase5:candidate-1:feature_reference_001",
    ]
    assert len(evidence) == len(set(evidence))
    assert contradictions == ()


def test_duplicate_contradictions_are_deduplicated() -> None:
    duplicate = {
        "kind": "contradiction",
        "code": "CONTRADICTION_001",
        "detail": "higher timeframe resistance remains nearby",
    }
    diagnostics = {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "evidence": [duplicate, dict(duplicate)],
            }
        ]
    }

    evidence, contradictions = selected_candidate_methodology_evidence(
        diagnostics, candidate_id="candidate-1"
    )

    assert len(evidence) == 1
    assert len(contradictions) == 1
    assert len(evidence) == len(set(evidence))
    assert len(contradictions) == len(set(contradictions))


def test_same_family_distinct_evidence_is_preserved() -> None:
    diagnostics = {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "evidence": [
                    {
                        "kind": "supporting",
                        "code": "SUPPORTING_001",
                        "detail": "volume expansion confirms breakout participation",
                    },
                    {
                        "kind": "supporting",
                        "code": "SUPPORTING_002",
                        "detail": "relative volume remains above its recent baseline",
                    },
                ],
            }
        ]
    }

    evidence, contradictions = selected_candidate_methodology_evidence(
        diagnostics, candidate_id="candidate-1"
    )

    assert len(evidence) == 2
    assert evidence[0] != evidence[1]
    assert all(item.family is EvidenceFamily.PARTICIPATION for item in evidence)
    assert contradictions == ()
