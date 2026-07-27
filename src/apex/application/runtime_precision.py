"""Precision-first abstention that can only suppress deterministic candidates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from apex.config.settings import PrecisionGateSettings
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.scoring.contracts import CandidateOutcome, CandidateSelectionResult, RankedCandidate
from apex.scoring.selection import select_candidate


class RuntimePrecisionState(StrEnum):
    PASS = "pass"
    ABSTAIN = "abstain"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RuntimePrecisionProfile:
    segment_key: str
    calibrated_fill_probability: float
    calibrated_positive_net_probability: float
    expected_r: float
    expected_r_interval: tuple[float, float]
    sample_size: int

    def __post_init__(self) -> None:
        for value in (
            self.calibrated_fill_probability,
            self.calibrated_positive_net_probability,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("calibrated probabilities must be in the unit interval")
        if len(self.expected_r_interval) != 2:
            raise ValueError("expected-R interval requires lower and upper bounds")
        if self.expected_r_interval[0] > self.expected_r_interval[1] or self.sample_size < 0:
            raise ValueError("runtime precision profile bounds are invalid")


@dataclass(frozen=True, slots=True)
class RuntimePrecisionArtifact:
    artifact_version: str
    feature_schema_version: str
    dataset_fingerprint: str
    configuration_hash: str
    code_hash: str
    attempted_configurations: int
    historical_promoted: bool
    paper_promoted: bool
    frozen_before: str
    profiles: tuple[RuntimePrecisionProfile, ...]
    artifact_sha256: str

    @property
    def enforcement_authorized(self) -> bool:
        return self.historical_promoted and self.paper_promoted

    def profile(
        self, *, strategy: str, direction: str, regime: str, cohort: str
    ) -> RuntimePrecisionProfile | None:
        keys = (
            f"{strategy}|{direction}|{regime}|{cohort}",
            f"{strategy}|{direction}|*|{cohort}",
            f"{strategy}|{direction}|*|*",
        )
        return next(
            (profile for key in keys for profile in self.profiles if profile.segment_key == key),
            None,
        )


@dataclass(frozen=True, slots=True)
class RuntimePrecisionDecision:
    candidate_id: str | None
    state: RuntimePrecisionState
    mode: str
    calibrated_fill_probability: float | None
    calibrated_positive_net_probability: float | None
    expected_r: float | None
    expected_r_interval: tuple[float, float] | None
    sample_size: int
    reason_codes: tuple[str, ...]
    artifact_version: str | None
    artifact_sha256: str | None

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["expected_r_interval"] = (
            None if self.expected_r_interval is None else list(self.expected_r_interval)
        )
        payload["reason_codes"] = list(self.reason_codes)
        return payload


def load_runtime_precision_artifact(
    path: Path,
) -> tuple[RuntimePrecisionArtifact | None, tuple[str, ...]]:
    """Load JSON only after its detached manifest and payload hash agree."""

    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not path.exists() or not manifest_path.exists():
        return None, ("artifact_missing",)
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
        manifest = json.loads(manifest_path.read_text())
        expected = str(manifest["artifact_sha256"])
        profiles = tuple(
            RuntimePrecisionProfile(
                **{
                    **item,
                    "expected_r_interval": tuple(item["expected_r_interval"]),
                }
            )
            for item in payload["profiles"]
        )
        artifact = RuntimePrecisionArtifact(
            artifact_version=str(payload["artifact_version"]),
            feature_schema_version=str(payload["feature_schema_version"]),
            dataset_fingerprint=str(payload["dataset_fingerprint"]),
            configuration_hash=str(payload["configuration_hash"]),
            code_hash=str(payload["code_hash"]),
            attempted_configurations=int(payload["attempted_configurations"]),
            historical_promoted=bool(payload["historical_promoted"]),
            paper_promoted=bool(payload["paper_promoted"]),
            frozen_before=str(payload["frozen_before"]),
            profiles=profiles,
            artifact_sha256=expected,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, ("artifact_schema_incompatible",)
    if hashlib.sha256(raw).hexdigest() != expected:
        return None, ("artifact_integrity_failed",)
    reasons: list[str] = []
    if not artifact.historical_promoted:
        reasons.append("historical_promotion_incomplete")
    if not artifact.paper_promoted:
        reasons.append("paper_promotion_incomplete")
    return artifact, tuple(reasons)


def apply_runtime_precision_gate(
    selection: CandidateSelectionResult,
    artifact: RuntimePrecisionArtifact | None,
    settings: PrecisionGateSettings,
    *,
    regime: str,
    cohort: str,
    artifact_reasons: tuple[str, ...] = (),
) -> tuple[CandidateSelectionResult, dict[str, Any]]:
    """Observe, paper-test, or suppress; never turn a rejection into an approval."""

    decisions: dict[str, RuntimePrecisionDecision] = {}
    unavailable = artifact is None
    enforce_authorized = artifact is not None and artifact.enforcement_authorized
    effective_enforce = settings.mode == "enforce" and enforce_authorized
    fail_closed = (
        settings.mode == "enforce" and settings.fail_closed_in_enforce and not enforce_authorized
    )
    for ranked in selection.ranked_candidates:
        candidate_id = ranked.scored.candidate_id
        if ranked.outcome not in {
            CandidateOutcome.ACCEPTED,
            CandidateOutcome.ACCEPTED_WITH_WARNING,
        }:
            decisions[candidate_id] = RuntimePrecisionDecision(
                candidate_id,
                RuntimePrecisionState.UNAVAILABLE,
                settings.mode,
                None,
                None,
                None,
                None,
                0,
                ("deterministic_candidate_rejected",),
                None if artifact is None else artifact.artifact_version,
                None if artifact is None else artifact.artifact_sha256,
            )
            continue
        profile = (
            None
            if artifact is None
            else artifact.profile(
                strategy=ranked.candidate.strategy.value,
                direction=ranked.candidate.direction.value,
                regime=regime,
                cohort=cohort,
            )
        )
        reasons = list(artifact_reasons)
        if profile is None:
            reasons.append("segment_unavailable")
            state = RuntimePrecisionState.UNAVAILABLE
        else:
            if profile.sample_size < settings.minimum_segment_support:
                reasons.append("segment_support_below_minimum")
            if (
                profile.calibrated_positive_net_probability
                < settings.required_positive_net_probability
            ):
                reasons.append("positive_net_probability_below_minimum")
            if profile.expected_r_interval[0] <= settings.required_expected_r_lower_bound:
                reasons.append("expected_r_lower_bound_not_positive")
            state = RuntimePrecisionState.ABSTAIN if reasons else RuntimePrecisionState.PASS
        decisions[candidate_id] = RuntimePrecisionDecision(
            candidate_id,
            state,
            settings.mode,
            None if profile is None else profile.calibrated_fill_probability,
            None if profile is None else profile.calibrated_positive_net_probability,
            None if profile is None else profile.expected_r,
            None if profile is None else profile.expected_r_interval,
            0 if profile is None else profile.sample_size,
            tuple(dict.fromkeys(reasons)),
            None if artifact is None else artifact.artifact_version,
            None if artifact is None else artifact.artifact_sha256,
        )

    changed = effective_enforce or fail_closed
    if not changed:
        updated = selection
    else:
        reranked: list[RankedCandidate] = []
        for ranked in selection.ranked_candidates:
            decision = decisions[ranked.scored.candidate_id]
            suppress = ranked.outcome in {
                CandidateOutcome.ACCEPTED,
                CandidateOutcome.ACCEPTED_WITH_WARNING,
            } and (fail_closed or decision.state is not RuntimePrecisionState.PASS)
            reranked.append(
                replace(
                    ranked,
                    rank=len(reranked) + 1,
                    outcome=(
                        CandidateOutcome.REJECTED_BELOW_THRESHOLD if suppress else ranked.outcome
                    ),
                    reasons=(
                        (*ranked.reasons, "precision gate abstained after deterministic validation")
                        if suppress
                        else ranked.reasons
                    ),
                )
            )
        ranked_tuple = tuple(reranked)
        selected = select_candidate(ranked_tuple, config=DEFAULT_SCORING_CONFIG)
        future = selection.selected_future_candidate
        if future is not None:
            future_decision = decisions[future.scored.candidate_id]
            if fail_closed or future_decision.state is not RuntimePrecisionState.PASS:
                future = None
        updated = replace(
            selection,
            ranked_candidates=ranked_tuple,
            rejected_candidates=tuple(
                item for item in ranked_tuple if item.outcome.value.startswith("rejected")
            ),
            selected_candidate=selected,
            selected_future_candidate=future,
            no_trade_reason=(
                None
                if selected is not None or future is not None
                else "precision gate abstained: "
                + ", ".join(dict.fromkeys((*artifact_reasons, "no candidate passed precision")))
            ),
            metadata={**selection.metadata, "runtime_precision_gate": True},
        )
    selected_id = (
        selection.selected_setup_candidate.scored.candidate_id
        if selection.selected_setup_candidate is not None
        else None
    )
    authority_reasons = list(artifact_reasons)
    if settings.mode == "enforce" and not enforce_authorized:
        authority_reasons.append("enforcement_not_authorized")
    return updated, {
        "mode": settings.mode,
        "production_changed": updated is not selection,
        "artifact_available": not unavailable,
        "enforcement_authorized": enforce_authorized,
        "reason_codes": list(dict.fromkeys(authority_reasons)),
        "selected_candidate_decision": (
            None if selected_id is None else decisions[selected_id].as_payload()
        ),
        "candidate_decisions": [
            decisions[item.scored.candidate_id].as_payload() for item in selection.ranked_candidates
        ],
    }


__all__ = [
    "RuntimePrecisionArtifact",
    "RuntimePrecisionDecision",
    "RuntimePrecisionProfile",
    "RuntimePrecisionState",
    "apply_runtime_precision_gate",
    "load_runtime_precision_artifact",
]
