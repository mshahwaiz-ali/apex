"""Point-in-time precision research contracts and validation-only selection."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from apex.application.quality_contracts import CanonicalMarketSnapshot, MarketBehaviorProfile
from apex.scoring.contracts import RankedCandidate

FEATURE_SCHEMA_VERSION = "candidate-features-v1"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateFeatureSnapshot:
    """Immutable facts available when a canonical or shadow candidate was decided."""

    symbol: str
    decision_time: datetime
    candidate_id: str
    candidate_geometry_id: str
    group_id: str
    strategy: str
    direction: str
    entry_state: str
    configuration_hash: str
    dataset_fingerprint: str
    code_hash: str
    snapshot_identity: str | None
    behavioral_cohort: str
    population: str
    features: tuple[tuple[str, float], ...]
    missing_value_mask: tuple[str, ...]
    authority: str = "decision_time_only"
    feature_schema_version: str = FEATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("candidate feature decision time must be timezone-aware")
        required = (
            self.symbol,
            self.candidate_id,
            self.candidate_geometry_id,
            self.group_id,
            self.strategy,
            self.direction,
            self.entry_state,
            self.configuration_hash,
            self.dataset_fingerprint,
            self.code_hash,
            self.behavioral_cohort,
            self.population,
        )
        if any(not value.strip() for value in required):
            raise ValueError("candidate feature identity fields cannot be blank")
        names = tuple(name for name, _ in self.features)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("candidate features must have unique sorted names")
        if any(not name or not math.isfinite(value) for name, value in self.features):
            raise ValueError("candidate features must be named finite values")
        if len(set(self.missing_value_mask)) != len(self.missing_value_mask):
            raise ValueError("missing-value mask cannot contain duplicates")

    @property
    def feature_snapshot_id(self) -> str:
        return _stable_hash(candidate_feature_snapshot_payload(self, include_id=False))


@dataclass(frozen=True, slots=True)
class CandidateOutcomeLabel:
    """Future-dependent label stored separately from decision-time features."""

    feature_snapshot_id: str
    resolved_at: datetime
    filled: bool
    net_r: float | None
    outcome: str
    funding_source: str

    def __post_init__(self) -> None:
        if not self.feature_snapshot_id.strip() or not self.outcome.strip():
            raise ValueError("candidate outcome identity and outcome cannot be blank")
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("candidate outcome resolution time must be timezone-aware")
        if self.net_r is not None and not math.isfinite(self.net_r):
            raise ValueError("candidate net R must be finite")
        if not self.filled and self.net_r is not None:
            raise ValueError("unfilled candidates cannot have realized net R")

    @property
    def positive_net(self) -> bool | None:
        return None if not self.filled or self.net_r is None else self.net_r > 0.0


def build_candidate_feature_snapshot(
    candidate: RankedCandidate,
    *,
    configuration_hash: str,
    dataset_fingerprint: str,
    code_hash: str,
    market_snapshot: CanonicalMarketSnapshot | None = None,
    market_profile: MarketBehaviorProfile | None = None,
    extra_features: Mapping[str, float | None] | None = None,
    population: str = "canonical",
) -> CandidateFeatureSnapshot:
    """Freeze one candidate without accepting outcome or future-candle inputs."""

    trade = candidate.candidate
    entry = trade.entry
    risk = abs(entry.preferred - trade.invalidation.price)
    target = trade.targets.levels[0].price
    reward = abs(target - entry.preferred)
    features: dict[str, float | None] = {
        "atr_distance": entry.atr_distance,
        "base_score": candidate.scored.breakdown.base_score / 100.0,
        "conflict_penalty": candidate.scored.breakdown.total_penalty / 100.0,
        "estimated_move_missed": entry.estimated_move_missed,
        "entry_distance_fraction": (
            entry.distance_from_current / entry.current_price if entry.current_price else None
        ),
        "entry_location_quality": entry.location_quality,
        "entry_width_fraction": (entry.upper - entry.lower) / entry.preferred,
        "final_rule_score": candidate.final_score / 100.0,
        "is_extended": float(entry.is_extended),
        "provisional": float(trade.provisional),
        "reward_to_risk_tp1": reward / risk if risk > 0.0 else None,
        "stop_distance_fraction": risk / entry.preferred,
    }
    features.update(
        (field.name, float(getattr(trade.quality, field.name))) for field in fields(trade.quality)
    )
    features.update(
        (str(key), float(value)) for key, value in candidate.scored.normalized_metrics.items()
    )
    if market_profile is not None:
        for name in (
            "liquidity_quote_volume_median",
            "volatility_percentile",
            "directional_efficiency",
            "chop_score",
            "wick_noise_score",
            "false_break_frequency",
            "execution_friction_score",
            "listing_maturity_days",
        ):
            features[f"market_{name}"] = getattr(market_profile, name)
    if market_snapshot is not None:
        features["snapshot_precision_valid"] = float(market_snapshot.precision_valid)
        features["snapshot_quality_valid"] = float(market_snapshot.quality_status == "valid")
        features["snapshot_listing_age_days"] = market_snapshot.listing_age_days
        features["snapshot_missing_evidence_count"] = float(len(market_snapshot.missing_evidence))
    if extra_features:
        features.update((str(key), value) for key, value in extra_features.items())
    missing = tuple(sorted(name for name, value in features.items() if value is None))
    numeric = tuple(sorted((name, float(value or 0.0)) for name, value in features.items()))
    geometry = {
        "symbol": trade.symbol.upper(),
        "decision_time": trade.decision_time.isoformat(),
        "strategy": trade.strategy.value,
        "direction": trade.direction.value,
        "entry": [entry.lower, entry.upper, entry.preferred, entry.mode.value],
        "stop": trade.invalidation.price,
        "targets": [level.price for level in trade.targets.levels],
    }
    return CandidateFeatureSnapshot(
        symbol=trade.symbol.upper(),
        decision_time=trade.decision_time,
        candidate_id=candidate.scored.candidate_id,
        candidate_geometry_id=_stable_hash(geometry),
        group_id=_stable_hash(
            {"symbol": trade.symbol.upper(), "decision_time": trade.decision_time.isoformat()}
        ),
        strategy=trade.strategy.value,
        direction=trade.direction.value,
        entry_state=entry.horizon.value,
        configuration_hash=configuration_hash,
        dataset_fingerprint=dataset_fingerprint,
        code_hash=code_hash,
        snapshot_identity=None if market_snapshot is None else market_snapshot.snapshot_id,
        behavioral_cohort="unavailable" if market_profile is None else market_profile.cohort,
        population=population,
        features=numeric,
        missing_value_mask=missing,
    )


def candidate_feature_snapshot_payload(
    snapshot: CandidateFeatureSnapshot, *, include_id: bool = True
) -> dict[str, Any]:
    payload = asdict(snapshot)
    payload["decision_time"] = snapshot.decision_time.isoformat()
    payload["features"] = dict(snapshot.features)
    payload["missing_value_mask"] = list(snapshot.missing_value_mask)
    if include_id:
        payload["feature_snapshot_id"] = snapshot.feature_snapshot_id
    return payload


def candidate_outcome_payload(outcome: CandidateOutcomeLabel) -> dict[str, Any]:
    payload = asdict(outcome)
    payload["resolved_at"] = outcome.resolved_at.isoformat()
    payload["positive_net"] = outcome.positive_net
    return payload


def deduplicate_feature_snapshots(
    snapshots: Iterable[CandidateFeatureSnapshot],
) -> tuple[CandidateFeatureSnapshot, ...]:
    """Keep one point-in-time row per candidate geometry and decision group."""

    unique: dict[tuple[str, str, str], CandidateFeatureSnapshot] = {}
    for snapshot in snapshots:
        key = (snapshot.group_id, snapshot.candidate_geometry_id, snapshot.population)
        incumbent = unique.get(key)
        if incumbent is None or snapshot.feature_snapshot_id < incumbent.feature_snapshot_id:
            unique[key] = snapshot
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.decision_time, item.symbol, item.candidate_id),
        )
    )


def training_rows(
    snapshots: Sequence[CandidateFeatureSnapshot],
    outcomes: Mapping[str, CandidateOutcomeLabel],
) -> tuple[dict[str, Any], ...]:
    """Create fill and post-fill rows while retaining a common chronological group."""

    rows: list[dict[str, Any]] = []
    for snapshot in deduplicate_feature_snapshots(snapshots):
        outcome = outcomes.get(snapshot.feature_snapshot_id)
        if outcome is None:
            continue
        base = {
            "timestamp": snapshot.decision_time.isoformat(),
            "group_id": snapshot.group_id,
            "feature_snapshot_id": snapshot.feature_snapshot_id,
            "feature_schema_version": snapshot.feature_schema_version,
            "features": dict(snapshot.features),
            "missing_value_mask": list(snapshot.missing_value_mask),
            "config_hash": snapshot.configuration_hash,
            "dataset_fingerprint": snapshot.dataset_fingerprint,
            "code_hash": snapshot.code_hash,
            "symbol": snapshot.symbol,
            "cohort": snapshot.behavioral_cohort,
        }
        rows.append({**base, "family": "entry_fill", "label": int(outcome.filled)})
        if outcome.positive_net is not None:
            rows.append(
                {
                    **base,
                    "family": "post_fill_outcome",
                    "label": int(outcome.positive_net),
                    "net_r": outcome.net_r,
                }
            )
    return tuple(rows)


def export_training_rows(
    feature_snapshots_file: Path,
    outcomes_file: Path,
    destination: Path,
) -> dict[str, Any]:
    """Join separately stored JSONL contracts and atomically write model rows."""

    snapshots = tuple(
        _feature_snapshot_from_payload(json.loads(line))
        for line in feature_snapshots_file.read_text().splitlines()
        if line.strip()
    )
    outcomes = tuple(
        _outcome_from_payload(json.loads(line))
        for line in outcomes_file.read_text().splitlines()
        if line.strip()
    )
    by_snapshot = {outcome.feature_snapshot_id: outcome for outcome in outcomes}
    rows = training_rows(snapshots, by_snapshot)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    )
    temporary.replace(destination)
    return {
        "feature_snapshots": len(snapshots),
        "deduplicated_snapshots": len(deduplicate_feature_snapshots(snapshots)),
        "outcomes": len(outcomes),
        "training_rows": len(rows),
        "destination": str(destination),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def _feature_snapshot_from_payload(payload: Mapping[str, Any]) -> CandidateFeatureSnapshot:
    return CandidateFeatureSnapshot(
        symbol=str(payload["symbol"]),
        decision_time=datetime.fromisoformat(str(payload["decision_time"])),
        candidate_id=str(payload["candidate_id"]),
        candidate_geometry_id=str(payload["candidate_geometry_id"]),
        group_id=str(payload["group_id"]),
        strategy=str(payload["strategy"]),
        direction=str(payload["direction"]),
        entry_state=str(payload["entry_state"]),
        configuration_hash=str(payload["configuration_hash"]),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        code_hash=str(payload["code_hash"]),
        snapshot_identity=(
            None if payload.get("snapshot_identity") is None else str(payload["snapshot_identity"])
        ),
        behavioral_cohort=str(payload["behavioral_cohort"]),
        population=str(payload.get("population", "canonical")),
        features=tuple(
            sorted((str(key), float(value)) for key, value in payload["features"].items())
        ),
        missing_value_mask=tuple(str(value) for value in payload["missing_value_mask"]),
        authority=str(payload.get("authority", "decision_time_only")),
        feature_schema_version=str(payload.get("feature_schema_version", FEATURE_SCHEMA_VERSION)),
    )


def _outcome_from_payload(payload: Mapping[str, Any]) -> CandidateOutcomeLabel:
    return CandidateOutcomeLabel(
        feature_snapshot_id=str(payload["feature_snapshot_id"]),
        resolved_at=datetime.fromisoformat(str(payload["resolved_at"])),
        filled=bool(payload["filled"]),
        net_r=None if payload.get("net_r") is None else float(payload["net_r"]),
        outcome=str(payload["outcome"]),
        funding_source=str(payload.get("funding_source", "unavailable")),
    )


@dataclass(frozen=True, slots=True)
class PrecisionFrontierPoint:
    threshold: float
    outcomes: int
    wins: int
    win_rate: float
    expectancy_r: float
    profit_factor: float
    average_win_r: float
    average_loss_r: float
    break_even_win_rate: float
    eligible: bool


def precision_frontier(
    probabilities: Sequence[float],
    net_returns_r: Sequence[float],
    *,
    thresholds: Sequence[float] | None = None,
    minimum_outcomes: int = 50,
    minimum_profit_factor: float = 1.20,
) -> tuple[PrecisionFrontierPoint, ...]:
    """Report validation-only precision/coverage/payoff trade-offs."""

    if len(probabilities) != len(net_returns_r):
        raise ValueError("probabilities and returns must have equal length")
    levels = thresholds or tuple(index / 100.0 for index in range(50, 96))
    points: list[PrecisionFrontierPoint] = []
    for threshold in levels:
        selected = [
            value
            for probability, value in zip(probabilities, net_returns_r, strict=True)
            if probability >= threshold
        ]
        wins = [value for value in selected if value > 0.0]
        losses = [value for value in selected if value <= 0.0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        average_win = fmean(wins) if wins else 0.0
        average_loss = abs(fmean(losses)) if losses else 0.0
        break_even = (
            average_loss / (average_win + average_loss) if average_win + average_loss > 0.0 else 1.0
        )
        expectancy = fmean(selected) if selected else 0.0
        profit_factor = gross_win / gross_loss if gross_loss > 0.0 else math.inf if wins else 0.0
        win_rate = len(wins) / len(selected) if selected else 0.0
        points.append(
            PrecisionFrontierPoint(
                threshold=float(threshold),
                outcomes=len(selected),
                wins=len(wins),
                win_rate=win_rate,
                expectancy_r=expectancy,
                profit_factor=profit_factor,
                average_win_r=average_win,
                average_loss_r=average_loss,
                break_even_win_rate=break_even,
                eligible=(
                    len(selected) >= minimum_outcomes
                    and expectancy > 0.0
                    and profit_factor >= minimum_profit_factor
                ),
            )
        )
    return tuple(points)


def select_validation_threshold(
    frontier: Sequence[PrecisionFrontierPoint],
) -> PrecisionFrontierPoint | None:
    """Choose maximum eligible precision without consulting final-test results."""

    eligible = (point for point in frontier if point.eligible)
    return max(
        eligible,
        key=lambda point: (point.win_rate, point.expectancy_r, point.outcomes, point.threshold),
        default=None,
    )


@dataclass(frozen=True, slots=True)
class PrecisionPromotionResult:
    promoted: bool
    failed_gates: tuple[str, ...]
    wilson_lower_bound: float
    bootstrap_expectancy_lower_bound: float


@dataclass(frozen=True, slots=True)
class PaperPrecisionPromotionResult:
    promoted: bool
    failed_gates: tuple[str, ...]
    outcomes: int
    weeks: float
    symbols: int
    cohorts: int
    maximum_symbol_share: float
    win_rate: float
    wilson_lower_bound: float
    profit_factor: float
    bootstrap_expectancy_lower_bound: float


def evaluate_paper_precision_promotion(
    outcomes: Sequence[tuple[datetime, str, str, float]],
) -> PaperPrecisionPromotionResult:
    """Evaluate fresh resolved filled paper outcomes without a frequency quota."""

    ordered = sorted(outcomes, key=lambda item: item[0])
    values = tuple(float(item[3]) for item in ordered)
    wins = sum(value > 0.0 for value in values)
    weeks = (
        (ordered[-1][0] - ordered[0][0]).total_seconds() / (7.0 * 86_400.0)
        if len(ordered) > 1
        else 0.0
    )
    symbols = Counter(item[1].upper() for item in ordered)
    cohorts = {item[2] for item in ordered}
    maximum_share = max(symbols.values(), default=0) / len(values) if values else 0.0
    win_rate = wins / len(values) if values else 0.0
    wilson = _wilson_lower(wins, len(values))
    gross_win = sum(value for value in values if value > 0.0)
    gross_loss = abs(sum(value for value in values if value <= 0.0))
    profit_factor = gross_win / gross_loss if gross_loss else math.inf if gross_win else 0.0
    bootstrap = _bootstrap_mean_lower(values)
    checks = (
        (len(values) >= 50, "fewer than 50 resolved filled paper outcomes"),
        (weeks >= 8.0, "paper observation period is shorter than eight weeks"),
        (len(symbols) >= 8, "fewer than eight paper symbols"),
        (len(cohorts) >= 4, "fewer than four paper cohorts"),
        (maximum_share <= 0.20, "one symbol exceeds 20% of the paper sample"),
        (win_rate >= 0.65, "paper win rate is below 65%"),
        (wilson >= 0.50, "paper Wilson lower bound is below 50%"),
        (bootstrap > 0.0, "paper bootstrap expectancy lower bound is not positive"),
        (profit_factor >= 1.20, "paper profit factor is below 1.20"),
    )
    failed = tuple(reason for passed, reason in checks if not passed)
    return PaperPrecisionPromotionResult(
        promoted=not failed,
        failed_gates=failed,
        outcomes=len(values),
        weeks=weeks,
        symbols=len(symbols),
        cohorts=len(cohorts),
        maximum_symbol_share=maximum_share,
        win_rate=win_rate,
        wilson_lower_bound=wilson,
        profit_factor=profit_factor,
        bootstrap_expectancy_lower_bound=bootstrap,
    )


def evaluate_precision_promotion(
    net_returns_r: Sequence[float],
    *,
    folds_positive: bool,
    exclusions_positive: bool,
    stable_cohorts: int,
    drawdown_within_budget: bool,
    brier_skill: float,
    calibration_error: float,
    dsr_probability: float,
    pbo_probability: float | None,
) -> PrecisionPromotionResult:
    """Apply the locked historical promotion gates to untouched outcomes."""

    values = tuple(float(value) for value in net_returns_r)
    wins = sum(value > 0.0 for value in values)
    win_rate = wins / len(values) if values else 0.0
    gross_win = sum(value for value in values if value > 0.0)
    gross_loss = abs(sum(value for value in values if value <= 0.0))
    profit_factor = gross_win / gross_loss if gross_loss else math.inf if gross_win else 0.0
    wilson = _wilson_lower(wins, len(values))
    bootstrap = _bootstrap_mean_lower(values)
    checks = (
        (len(values) >= 200, "fewer than 200 untouched filled outcomes"),
        (win_rate >= 0.65, "net-positive win rate is below 65%"),
        (wilson >= 0.55, "Wilson 95% lower bound is below 55%"),
        (bootstrap > 0.0, "bootstrap 95% expectancy lower bound is not positive"),
        (profit_factor >= 1.20, "profit factor is below 1.20"),
        (drawdown_within_budget, "drawdown exceeds experiment budget"),
        (folds_positive, "one or more adequately sampled folds are non-positive"),
        (exclusions_positive, "best-symbol or best-month exclusion is non-positive"),
        (stable_cohorts >= 4, "fewer than four stable cohorts"),
        (brier_skill > 0.0, "Brier skill is not positive"),
        (calibration_error <= 0.05, "calibration error exceeds 0.05"),
        (dsr_probability >= 0.95, "DSR probability is below 0.95"),
        (pbo_probability is not None, "PBO is unavailable"),
        (pbo_probability is not None and pbo_probability <= 0.20, "PBO exceeds 0.20"),
    )
    failed = tuple(reason for passed, reason in checks if not passed)
    return PrecisionPromotionResult(not failed, failed, wilson, bootstrap)


def _wilson_lower(wins: int, outcomes: int, z: float = 1.959963984540054) -> float:
    if outcomes == 0:
        return 0.0
    observed = wins / outcomes
    denominator = 1.0 + z * z / outcomes
    centre = observed + z * z / (2.0 * outcomes)
    margin = z * math.sqrt(
        observed * (1.0 - observed) / outcomes + z * z / (4.0 * outcomes * outcomes)
    )
    return max(0.0, (centre - margin) / denominator)


def _bootstrap_mean_lower(values: Sequence[float], *, samples: int = 2_000) -> float:
    if not values:
        return 0.0
    generator = random.Random(1729)
    means = sorted(fmean(generator.choice(values) for _ in values) for _ in range(samples))
    return means[max(0, int(samples * 0.025) - 1)]


def cohort_counts(snapshots: Sequence[CandidateFeatureSnapshot]) -> Mapping[str, int]:
    return dict(Counter(snapshot.behavioral_cohort for snapshot in snapshots))


__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "CandidateFeatureSnapshot",
    "CandidateOutcomeLabel",
    "PaperPrecisionPromotionResult",
    "PrecisionFrontierPoint",
    "PrecisionPromotionResult",
    "build_candidate_feature_snapshot",
    "candidate_feature_snapshot_payload",
    "candidate_outcome_payload",
    "cohort_counts",
    "deduplicate_feature_snapshots",
    "evaluate_paper_precision_promotion",
    "evaluate_precision_promotion",
    "export_training_rows",
    "precision_frontier",
    "select_validation_threshold",
    "training_rows",
]
