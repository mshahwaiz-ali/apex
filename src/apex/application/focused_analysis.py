"""Focused single-symbol thesis summary built from shared discovery output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apex.scoring.config import DEFAULT_SCORING_CONFIG

_DIRECTIONS = ("long", "short")
_VIABLE_OUTCOMES = {"accepted", "accepted_with_conflict_warning", "downgraded"}
_EXECUTABLE_STATUSES = {"READY_NOW", "AGGRESSIVE_NOW"}


def focused_analysis_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return additive long/short thesis diagnostics for selected-symbol output."""

    records = _ranking_records(payload.get("candidate_ranking"))
    setup = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    selected_id = _candidate_id(setup)
    developing_id = _candidate_id(developing)
    theses = {
        direction: _directional_thesis(
            direction=direction,
            records=records,
            selected_id=selected_id,
            developing_id=developing_id,
        )
        for direction in _DIRECTIONS
    }
    outlook = _market_outlook(payload)
    comparison = _directional_comparison(payload, theses)
    return {
        "market_outlook": outlook,
        "directional_assessment": comparison,
        "long_thesis": theses["long"],
        "short_thesis": theses["short"],
        "watch_plan": _watch_plan(theses, comparison, outlook),
    }


def _directional_thesis(
    *,
    direction: str,
    records: tuple[Mapping[str, Any], ...],
    selected_id: str | None,
    developing_id: str | None,
) -> dict[str, Any]:
    record = next((item for item in records if item.get("direction") == direction), None)
    if record is None:
        return {
            "direction": direction,
            "state": "no_generated_thesis",
            "status": "No generated thesis",
            "summary": f"No {direction} candidate passed strategy generation.",
            "executable_now": False,
            "structurally_valid": False,
            "blockers": (f"no {direction} strategy candidate was generated",),
            "activation_conditions": (),
            "invalidation_conditions": (),
            "watch_levels": (),
        }

    outcome = str(record.get("outcome") or "")
    entry_status = str(record.get("entry_status") or "")
    candidate_id = str(record.get("candidate_id") or "")
    executable = candidate_id == selected_id and entry_status in _EXECUTABLE_STATUSES
    developing = candidate_id == developing_id or (
        outcome in _VIABLE_OUTCOMES and entry_status not in _EXECUTABLE_STATUSES
    )
    rejected = outcome.startswith("rejected")
    state = (
        "actionable"
        if executable
        else "developing"
        if developing
        else "rejected"
        if rejected
        else "conditional"
    )
    status = {
        "actionable": "Actionable",
        "developing": "Developing",
        "rejected": "Rejected",
        "conditional": "Conditional",
    }[state]
    reasons = _strings(record.get("reasons"))
    evidence = _mapping(record.get("evidence"))
    entry = _mapping(record.get("entry"))
    invalidation = _mapping(record.get("invalidation"))
    targets = _mappings(record.get("targets"))
    blockers = _blockers(record, reasons)
    return {
        "direction": direction,
        "state": state,
        "status": status,
        "primary_strategy": record.get("strategy"),
        "canonical_family": record.get("strategy_family"),
        "canonical_subtype": record.get("strategy_subtype"),
        "candidate_id": candidate_id,
        "candidate_outcome": outcome,
        "entry_status": entry_status,
        "score": record.get("final_score"),
        "approval_threshold": record.get(
            "approval_threshold",
            DEFAULT_SCORING_CONFIG.minimum_accept_score,
        ),
        "score_shortfall": record.get("score_shortfall"),
        "setup_quality": _score_dimension(record, "setup_score"),
        "execution_quality": _score_dimension(record, "timing_score"),
        "target_quality": _score_dimension(record, "opportunity_score"),
        "risk_quality": _score_dimension(record, "trade_quality_score"),
        "entry": entry,
        "invalidation": invalidation,
        "targets": targets,
        "supporting_evidence": tuple(_strings(evidence.get("supporting"))[:5]),
        "contradictions": tuple(_strings(evidence.get("contradictions"))[:5]),
        "warnings": tuple(_strings(evidence.get("warnings"))[:5]),
        "blockers": blockers,
        "activation_conditions": _activation_conditions(record),
        "invalidation_conditions": _invalidation_conditions(record),
        "watch_levels": _watch_levels(record),
        "executable_now": executable,
        "structurally_valid": outcome != "rejected_due_to_contradiction",
        "summary": _thesis_summary(direction, state, record, blockers),
    }


def _market_outlook(payload: Mapping[str, Any]) -> dict[str, Any]:
    frames = _mapping(payload.get("data_quality_by_timeframe"))
    regimes = _mapping(payload.get("regime_by_timeframe"))
    by_role: dict[str, Mapping[str, Any]] = {}
    for timeframe, frame in frames.items():
        if isinstance(frame, Mapping):
            role = str(frame.get("role") or timeframe)
            by_role[role] = frame
    setup_frame = by_role.get("setup") or next(iter(frames.values()), {})
    entry_frame = by_role.get("entry") or setup_frame
    structure = _mapping(setup_frame.get("structure") if isinstance(setup_frame, Mapping) else None)
    features = _mapping(entry_frame.get("features") if isinstance(entry_frame, Mapping) else None)
    regime_text = _primary_regime(regimes)
    return {
        "regime": regime_text,
        "market_condition": _market_condition(regime_text, structure, features),
        "primary_structure": structure.get("trend_state") or "unavailable",
        "setup_structure": structure.get("break_state") or "unavailable",
        "entry_timeframe": (
            entry_frame.get("timeframe", "unavailable")
            if isinstance(entry_frame, Mapping)
            else "unavailable"
        ),
        "volatility": structure.get("volatility_state") or "unavailable",
        "participation": _participation(features),
        "current_location": _current_location(structure),
    }


def _directional_comparison(
    payload: Mapping[str, Any],
    theses: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    setup = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    if setup:
        preferred = str(setup.get("direction") or "none")
        reason = "one side passed all configured selection and executable-entry gates"
    elif developing:
        preferred = str(developing.get("direction") or "none")
        reason = "one side is structurally valid but still requires entry confirmation"
    else:
        preferred = _stronger_non_executable_side(theses)
        reason = (
            "neither side is executable; comparison is based on preserved rule scores and blockers"
        )
    return {
        "preferred_side": preferred,
        "long_state": theses["long"]["state"],
        "short_state": theses["short"]["state"],
        "confidence_label": _confidence_label(theses, preferred),
        "reason": reason,
    }


def _watch_plan(
    theses: Mapping[str, Mapping[str, Any]],
    comparison: Mapping[str, Any],
    outlook: Mapping[str, Any],
) -> tuple[str, ...]:
    lines: list[str] = []
    preferred = str(comparison.get("preferred_side") or "none")
    for direction in _DIRECTIONS:
        thesis = theses[direction]
        state = thesis.get("state")
        if state in {"actionable", "developing", "conditional", "rejected"}:
            for condition in _strings(thesis.get("activation_conditions"))[:2]:
                lines.append(f"{direction}: {condition}")
    if not lines:
        condition = outlook["market_condition"]
        lines.append(f"wait for a cleaner structure; current condition is {condition}")
    if preferred == "none":
        lines.append("avoid forcing direction until one side closes through a defined level")
    else:
        lines.append(f"do not treat {preferred} as executable unless its activation gates complete")
    return tuple(dict.fromkeys(lines))[:5]


def _blockers(record: Mapping[str, Any], reasons: tuple[str, ...]) -> tuple[str, ...]:
    blockers = list(reasons)
    if float(record.get("score_shortfall") or 0.0) > 0.0:
        blockers.append("rule-based quality is below the configured approval threshold")
    entry = _mapping(record.get("entry"))
    if entry.get("is_extended") is True:
        blockers.append("entry is extended relative to the generated zone")
    evidence = _mapping(record.get("evidence"))
    blockers.extend(_strings(evidence.get("contradictions")))
    blockers.extend(_strings(evidence.get("warnings")))
    return tuple(dict.fromkeys(item for item in blockers if item))[:6]


def _activation_conditions(record: Mapping[str, Any]) -> tuple[str, ...]:
    entry = _mapping(record.get("entry"))
    direction = str(record.get("direction") or "direction")
    mode = str(entry.get("mode") or "entry")
    zone = _zone_text(entry)
    conditions = [f"{direction} {mode.replace('_', ' ')} confirms around {zone}"]
    if entry.get("is_extended") is True:
        conditions.append(
            f"price returns to the preferred zone near {_display_price(entry.get('preferred'))}"
        )
    for reason in _strings(entry.get("rationale")):
        conditions.append(reason)
    if record.get("provisional") is True:
        conditions.append("active-candle evidence must confirm on a closed candle")
    return tuple(dict.fromkeys(item for item in conditions if item))[:5]


def _invalidation_conditions(record: Mapping[str, Any]) -> tuple[str, ...]:
    invalidation = _mapping(record.get("invalidation"))
    price = invalidation.get("price")
    direction = str(record.get("direction") or "")
    if price is None:
        return tuple(_strings(invalidation.get("rationale"))[:4])
    verb = "breaks below" if direction == "long" else "reclaims above"
    lines = [f"setup invalidates if price {verb} {_display_price(price)}"]
    lines.extend(_strings(invalidation.get("rationale")))
    return tuple(dict.fromkeys(lines))[:5]


def _watch_levels(record: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    entry = _mapping(record.get("entry"))
    invalidation = _mapping(record.get("invalidation"))
    targets = _mappings(record.get("targets"))
    levels: list[dict[str, Any]] = []
    if entry:
        levels.append({"label": "preferred_entry", "price": entry.get("preferred")})
        levels.append({"label": "entry_zone_low", "price": entry.get("lower")})
        levels.append({"label": "entry_zone_high", "price": entry.get("upper")})
    if invalidation:
        levels.append({"label": "invalidation", "price": invalidation.get("price")})
    for target in targets[:3]:
        levels.append({"label": target.get("label") or "target", "price": target.get("price")})
    return tuple(item for item in levels if item.get("price") is not None)


def _thesis_summary(
    direction: str,
    state: str,
    record: Mapping[str, Any],
    blockers: tuple[str, ...],
) -> str:
    strategy = str(record.get("strategy") or "generated strategy").replace("_", " ")
    if state == "actionable":
        return f"{direction} is actionable through {strategy}."
    if state == "developing":
        return f"{direction} is developing through {strategy}; entry confirmation is incomplete."
    if blockers:
        return f"{direction} {strategy} is not approved: {blockers[0]}."
    return f"{direction} {strategy} is conditional, not executable."


def _stronger_non_executable_side(theses: Mapping[str, Mapping[str, Any]]) -> str:
    scored = []
    for direction in _DIRECTIONS:
        thesis = theses[direction]
        if thesis.get("state") == "no_generated_thesis":
            continue
        score = thesis.get("score")
        scored.append((direction, float(score) if isinstance(score, int | float) else 0.0))
    if not scored:
        return "none"
    scored.sort(key=lambda item: item[1], reverse=True)
    if len(scored) > 1 and scored[0][1] - scored[1][1] < 4.0:
        return "none"
    return scored[0][0]


def _confidence_label(theses: Mapping[str, Mapping[str, Any]], preferred: str) -> str:
    if preferred not in theses:
        return "Low"
    score = theses[preferred].get("score")
    value = float(score) if isinstance(score, int | float) else 0.0
    if value >= 75.0:
        return "High rule-based thesis quality"
    if value >= 65.0:
        return "Moderate rule-based thesis quality"
    if value >= 58.0:
        return "Low-moderate rule-based thesis quality"
    return "Low"


def _market_condition(
    regime: str,
    structure: Mapping[str, Any],
    features: Mapping[str, Any],
) -> str:
    text = " ".join(
        str(value).lower()
        for value in (
            regime,
            structure.get("trend_state"),
            structure.get("break_state"),
            structure.get("compression_or_expansion_state"),
            structure.get("volatility_state"),
        )
    )
    if "compressed" in text or "compression" in text:
        return "compressed"
    if "range" in text:
        return "range-bound"
    if "failed" in text:
        return "transitional after failed break"
    if "expansion" in text or features.get("volatility_expansion"):
        return "expanding"
    if "chaotic" in text or "uncertain" in text:
        return "chaotic"
    return "directional" if "trend" in text else "mixed"


def _primary_regime(regimes: Mapping[str, Any]) -> str:
    if not regimes:
        return "unavailable"
    return str(next(iter(regimes.values())))


def _participation(features: Mapping[str, Any]) -> str:
    value = features.get("relative_volume")
    if not isinstance(value, int | float):
        return "unavailable"
    if value >= 1.5:
        return "above normal"
    if value >= 0.8:
        return "normal"
    return "thin"


def _current_location(structure: Mapping[str, Any]) -> str:
    support = structure.get("nearest_downside_obstacle")
    resistance = structure.get("nearest_upside_obstacle")
    if support is None and resistance is None:
        return "unavailable"
    return f"support {_display_price(support)}, resistance {_display_price(resistance)}"


def _score_dimension(record: Mapping[str, Any], key: str) -> object:
    dimensions = _mapping(record.get("score_dimensions"))
    return dimensions.get(key)


def _zone_text(entry: Mapping[str, Any]) -> str:
    low = entry.get("lower")
    high = entry.get("upper")
    if low == high:
        return str(low)
    return f"{_display_price(low)}-{_display_price(high)}"


def _candidate_id(setup: Mapping[str, Any]) -> str | None:
    value = setup.get("candidate_id")
    return None if value is None else str(value)


def _ranking_records(value: object) -> tuple[Mapping[str, Any], ...]:
    ranking = _mapping(value)
    records: list[Mapping[str, Any]] = []
    primary = _mapping(ranking.get("primary"))
    if primary:
        records.append(primary)
    records.extend(_mappings(ranking.get("alternatives")))
    records.extend(_mappings(ranking.get("rejected")))
    return tuple(sorted(records, key=lambda item: int(item.get("rank") or 9999)))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value if str(item))


def _display_price(value: object) -> str:
    if isinstance(value, int | float):
        return f"{value:.10g}"
    return str(value)
