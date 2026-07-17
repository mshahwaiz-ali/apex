"""Tests for explicit candidate opportunity quality labels."""

from __future__ import annotations

from apex.application.candidate_ranking import (
    CandidateQualityLabel,
    CandidateRankingRole,
    candidate_quality_label,
)


def test_rejected_role_always_uses_rejected_label() -> None:
    assert (
        candidate_quality_label(
            final_rank_score=99.0,
            role=CandidateRankingRole.REJECTED,
        )
        is CandidateQualityLabel.REJECTED
    )


def test_viable_labels_reuse_canonical_score_band_boundaries() -> None:
    cases = (
        (54.999, CandidateQualityLabel.SPECULATIVE),
        (55.0, CandidateQualityLabel.SPECULATIVE),
        (64.999, CandidateQualityLabel.SPECULATIVE),
        (65.0, CandidateQualityLabel.USABLE),
        (74.999, CandidateQualityLabel.USABLE),
        (75.0, CandidateQualityLabel.STRONG),
        (100.0, CandidateQualityLabel.STRONG),
    )

    for score, expected in cases:
        assert (
            candidate_quality_label(
                final_rank_score=score,
                role=CandidateRankingRole.ALTERNATIVE,
            )
            is expected
        )
