"""Fail-soft promoted historical-edge profiles and expected-R candidate ranking."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from apex.research.edge import PromotionMetrics, evaluate_promotion
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.scoring.contracts import CandidateSelectionResult, RankedCandidate
from apex.scoring.selection import no_trade_reason, select_candidate


@dataclass(frozen=True, slots=True)
class RuntimeEdgeProfile:
    segment_key: str
    expected_r: float
    fill_probability: float
    probability_interval: tuple[float, float]
    sample_size: int


@dataclass(frozen=True, slots=True)
class RuntimeEdgeArtifact:
    profiles: tuple[RuntimeEdgeProfile, ...]
    dataset_hash: str
    model_version: str

    def profile(
        self, strategy: str, direction: str, regime: str, archetype: str
    ) -> RuntimeEdgeProfile | None:
        exact = f"{strategy}|{direction}|{regime}|{archetype}"
        fallback = f"{strategy}|{direction}|*|*"
        return next(
            (
                item
                for key in (exact, fallback)
                for item in self.profiles
                if item.segment_key == key
            ),
            None,
        )


def load_runtime_edge_artifact(path: Path) -> tuple[RuntimeEdgeArtifact | None, str]:
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not path.exists() or not manifest_path.exists():
        return None, "historical edge unavailable: artifact missing"
    try:
        raw = path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
        payload = json.loads(raw)
        expected_hash = str(manifest["artifact_sha256"])
        metrics = PromotionMetrics(**manifest["promotion_metrics"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, "historical edge unavailable: artifact manifest invalid"
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        return None, "historical edge unavailable: artifact integrity failed"
    promotion = evaluate_promotion(
        metrics,
        separately_published_segment=bool(manifest.get("separately_published_segment", False)),
    )
    if not promotion.promoted:
        return None, "historical edge withheld: " + "; ".join(promotion.failed_gates)
    try:
        artifact = RuntimeEdgeArtifact(
            profiles=tuple(RuntimeEdgeProfile(**item) for item in payload["profiles"]),
            dataset_hash=str(payload["dataset_hash"]),
            model_version=str(payload["model_version"]),
        )
    except (KeyError, TypeError, ValueError):
        return None, "historical edge unavailable: profile schema incompatible"
    return artifact, "historical edge available"


def apply_runtime_edge_ranking(
    selection: CandidateSelectionResult,
    artifact: RuntimeEdgeArtifact | None,
    *,
    regime: str,
    archetype: str,
) -> tuple[CandidateSelectionResult, dict[str, Any]]:
    if artifact is None:
        return selection, {
            "available": False,
            "expected_r": None,
            "calibrated_probability_interval": None,
            "sample_size": 0,
        }
    profiles = {
        item.scored.candidate_id: artifact.profile(
            item.candidate.strategy.value,
            item.candidate.direction.value,
            regime,
            archetype,
        )
        for item in selection.ranked_candidates
    }

    def edge_sort_key(item: RankedCandidate) -> tuple[bool, float, int, str]:
        profile = profiles[item.scored.candidate_id]
        expected_r = profile.expected_r if profile is not None else 0.0
        return expected_r <= 0, -expected_r, item.rank, item.scored.candidate_id

    ordered = sorted(selection.ranked_candidates, key=edge_sort_key)
    reranked = tuple(replace(item, rank=index) for index, item in enumerate(ordered, start=1))
    selected = select_candidate(reranked, config=DEFAULT_SCORING_CONFIG)
    updated = replace(
        selection,
        ranked_candidates=reranked,
        rejected_candidates=tuple(
            item for item in reranked if item.outcome.value.startswith("rejected")
        ),
        selected_candidate=selected,
        no_trade_reason=None if selected is not None else no_trade_reason(reranked),
        metadata={**selection.metadata, "historical_edge_ranking": True},
    )
    selected_profile = profiles[selected.scored.candidate_id] if selected is not None else None
    return updated, {
        "available": True,
        "expected_r": selected_profile.expected_r if selected_profile else None,
        "fill_probability": selected_profile.fill_probability if selected_profile else None,
        "calibrated_probability_interval": (
            list(selected_profile.probability_interval) if selected_profile else None
        ),
        "sample_size": selected_profile.sample_size if selected_profile else 0,
        "dataset_hash": artifact.dataset_hash,
        "model_version": artifact.model_version,
        "reason": "promoted expected-R ranking active",
    }


__all__ = [
    "RuntimeEdgeArtifact",
    "RuntimeEdgeProfile",
    "apply_runtime_edge_ranking",
    "load_runtime_edge_artifact",
]
