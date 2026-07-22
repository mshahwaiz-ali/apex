#!/usr/bin/env python3
"""Aggregate Apex replay campaigns with first-touch forensic integrity.

Usage:
    python3 tools/aggregate_batch11c_forensics.py CAMPAIGN_DIR
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from statistics import mean
from typing import Any


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def report_files(directory: Path) -> list[Path]:
    excluded = {"campaign_summary.json", "forensic_summary.json"}
    return sorted(path for path in directory.glob("*.json") if path.name not in excluded)


def profile_from_filename(path: Path) -> str:
    for profile in ("micro", "standard", "environment"):
        if f"_{profile}_" in path.stem:
            return profile
    return "unknown"


def symbol_from_filename(path: Path) -> str:
    return path.name.split("_", 1)[0]


def outcome_name(trade: Mapping[str, Any]) -> str:
    value = trade.get("outcome")
    if isinstance(value, Mapping):
        value = value.get("value")
    return str(value) if value is not None else "unknown"


def replay_trades(payload: Mapping[str, Any], section: str) -> list[Mapping[str, Any]]:
    if section == "production":
        for key in ("trades", "production_trades"):
            values = payload.get(key)
            if isinstance(values, list):
                return [as_mapping(item) for item in values]
        values = as_mapping(payload.get("production_replay")).get("trades")
        return [as_mapping(item) for item in as_list(values)]
    values = as_mapping(payload.get(f"{section}_replay")).get("trades")
    return [as_mapping(item) for item in as_list(values)]


def candidate_map(payload: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for decision in as_list(payload.get("calibration_records")):
        decision_map = as_mapping(decision)
        decision_time = str(decision_map.get("decision_time") or "")
        for candidate in as_list(decision_map.get("candidate_diagnostics")):
            candidate_map_ = as_mapping(candidate)
            candidate_id = str(candidate_map_.get("candidate_id") or "")
            if decision_time and candidate_id:
                result[(decision_time, candidate_id)] = candidate_map_
    return result


def strategy_from_candidate_id(candidate_id: str) -> str | None:
    strategy, separator, _ = candidate_id.partition(":")
    return strategy if separator and strategy else None


def direction_from_candidate_id(candidate_id: str) -> str | None:
    parts = candidate_id.split(":")
    if len(parts) >= 2 and parts[1] in {"long", "short"}:
        return parts[1]
    return None


def geometry_state(
    *,
    replay_source: str,
    gross_tp1_r: object,
    net_tp1_r: object,
    candidate: Mapping[str, Any],
) -> str:
    audit = as_mapping(candidate.get("geometry_audit"))
    net = finite_number(net_tp1_r)
    gross = finite_number(gross_tp1_r)
    if replay_source == "geometry_rejected" or candidate.get("geometry_complete") is False:
        if net is not None and net <= 0.0:
            return "COST_INVALID_GEOMETRY"
        if audit:
            stop_atr = finite_number(audit.get("stop_distance_atr"))
            minimum_stop_atr = finite_number(audit.get("minimum_stop_distance_atr"))
            tp1_atr = finite_number(audit.get("tp1_distance_atr"))
            maximum_tp1_atr = finite_number(audit.get("maximum_tp1_distance_atr"))
            required_net = finite_number(audit.get("required_tp1_reward_to_risk"))
            if (
                stop_atr is not None
                and minimum_stop_atr is not None
                and stop_atr < minimum_stop_atr
            ):
                return "STOP_TOO_TIGHT"
            if tp1_atr is not None and maximum_tp1_atr is not None and tp1_atr > maximum_tp1_atr:
                return "TARGET_TOO_DISTANT"
            if net is not None and required_net is not None and net < required_net:
                return "TARGET_BELOW_MINIMUM_NET_R"
        if gross is None or net is None:
            return "INCOMPLETE_GEOMETRY"
        return "GEOMETRY_REJECTED"
    if net is not None and net <= 0.0:
        return "COST_INVALID_GEOMETRY"
    return "VALID_GEOMETRY"


def classify_stop(row: Mapping[str, Any]) -> str:
    event = str(row.get("first_exit_event") or "")
    geometry = str(row.get("geometry_state") or "")
    mfe = finite_number(row.get("pre_exit_mfe_r"))
    full_path = finite_number(row.get("counterfactual_path_mfe_r"))
    progress = finite_number(row.get("tp1_progress_ratio"))

    if event == "same_candle_ambiguous_stop_first":
        return "AMBIGUOUS_SAME_CANDLE"
    if geometry != "VALID_GEOMETRY":
        return "INVALID_GEOMETRY"
    if mfe is None:
        return "UNRESOLVED_EVIDENCE"
    if mfe < 0.5:
        if full_path is not None and full_path - mfe >= 1.0:
            return "POST_STOP_RECOVERY_ONLY"
        return "WEAK_FOLLOW_THROUGH"
    if progress is not None and progress >= 0.8:
        return "NEAR_TARGET_REVERSAL"
    if mfe >= 2.0:
        return "GENUINE_PROFIT_AVAILABLE_THEN_STOP"
    if mfe >= 1.0:
        return "MODERATE_PROFIT_AVAILABLE_THEN_STOP"
    if full_path is not None and full_path - mfe >= 1.0:
        return "POST_STOP_RECOVERY_ONLY"
    return "LOW_MFE_THEN_STOP"


def average(rows: Iterable[Mapping[str, Any]], key: str) -> float | None:
    values = [value for row in rows if (value := finite_number(row.get(key))) is not None]
    return mean(values) if values else None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: aggregate_batch11c_forensics.py CAMPAIGN_DIR")

    directory = Path(sys.argv[1]).resolve()
    if not directory.is_dir():
        raise SystemExit(f"campaign directory does not exist: {directory}")

    files = report_files(directory)
    if not files:
        raise SystemExit(f"no report JSON files found in {directory}")

    shadow_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    report_counts: Counter[str] = Counter()
    section_outcomes: dict[str, Counter[str]] = {
        section: Counter() for section in ("production", "conditional", "opportunity", "shadow")
    }

    for path in files:
        payload = as_mapping(json.loads(path.read_text()))
        profile = profile_from_filename(path)
        symbol = symbol_from_filename(path)
        report_counts[profile] += 1
        candidates = candidate_map(payload)

        for section in section_outcomes:
            for trade in replay_trades(payload, section):
                section_outcomes[section][outcome_name(trade)] += 1

        for decision in as_list(payload.get("calibration_records")):
            item = as_mapping(decision)
            confirmation = as_mapping(item.get("confirmation_diagnostics"))
            decision_rows.append(
                {
                    "file": path.name,
                    "symbol": symbol,
                    "profile": profile,
                    "decision_time": item.get("decision_time"),
                    "strategy": item.get("strategy"),
                    "direction": item.get("direction"),
                    "actionability_state": item.get("actionability_state"),
                    "replay_reason_code": item.get("replay_reason_code"),
                    "execution_authorized": item.get("execution_authorized"),
                    "replay_class": item.get("replay_class"),
                    "candidate_count": len(as_list(item.get("candidate_diagnostics"))),
                    "confirmation_source": confirmation.get("source"),
                    "entry_confirmation_complete": confirmation.get("entry_confirmation_complete"),
                    "higher_timeframe_conflict": confirmation.get("higher_timeframe_conflict"),
                    "continuation_state": confirmation.get("continuation_state"),
                }
            )

        for trade in replay_trades(payload, "shadow"):
            diagnostics = as_mapping(trade.get("diagnostics"))
            confirmation = as_mapping(diagnostics.get("confirmation"))
            progress = as_mapping(trade.get("r_progress"))
            metadata = as_mapping(trade.get("metadata"))
            decision_time = str(trade.get("decision_time") or "")
            candidate_id = str(
                trade.get("opportunity_id")
                or trade.get("candidate_id")
                or diagnostics.get("candidate_id")
                or metadata.get("candidate_id")
                or ""
            )
            candidate = candidates.get((decision_time, candidate_id), {})
            candidate_confirmation = as_mapping(candidate.get("confirmation"))

            strategy = (
                diagnostics.get("strategy")
                or candidate.get("strategy")
                or strategy_from_candidate_id(candidate_id)
                or "unknown"
            )
            direction = (
                diagnostics.get("direction")
                or candidate.get("direction")
                or direction_from_candidate_id(candidate_id)
                or "unknown"
            )
            replay_source = str(
                metadata.get("replay_source")
                or trade.get("replay_source")
                or diagnostics.get("replay_source")
                or candidate.get("replay_source")
                or ""
            )
            htf_conflict = confirmation.get("higher_timeframe_conflict")
            if htf_conflict is None:
                htf_conflict = candidate_confirmation.get("higher_timeframe_conflict")

            audit = as_mapping(candidate.get("geometry_audit"))
            gross_tp1_r = diagnostics.get("gross_tp1_r")
            if gross_tp1_r is None:
                gross_tp1_r = candidate.get("gross_tp1_r")
            if gross_tp1_r is None:
                gross_tp1_r = audit.get("gross_tp1_reward_to_risk")

            net_tp1_r = diagnostics.get("net_tp1_r")
            if net_tp1_r is None:
                net_tp1_r = candidate.get("net_tp1_r")
            if net_tp1_r is None:
                net_tp1_r = audit.get("net_tp1_reward_to_risk")

            geometry = geometry_state(
                replay_source=replay_source,
                gross_tp1_r=gross_tp1_r,
                net_tp1_r=net_tp1_r,
                candidate=candidate,
            )
            pre_exit_mfe = metadata.get(
                "pre_exit_mfe_r", trade.get("maximum_favorable_excursion_r")
            )
            pre_exit_mae = metadata.get("pre_exit_mae_r", trade.get("maximum_adverse_excursion_r"))
            full_path_mfe = metadata.get("counterfactual_path_mfe_r")
            full_path_mae = metadata.get("counterfactual_path_mae_r")
            post_exit_additional_mfe = None
            pre_value = finite_number(pre_exit_mfe)
            full_value = finite_number(full_path_mfe)
            if pre_value is not None and full_value is not None:
                post_exit_additional_mfe = max(0.0, full_value - pre_value)

            row: dict[str, Any] = {
                "file": path.name,
                "symbol": symbol,
                "profile": profile,
                "decision_time": decision_time,
                "candidate_id": candidate_id,
                "outcome": outcome_name(trade),
                "strategy": strategy,
                "strategy_family": diagnostics.get("strategy_family")
                or candidate.get("strategy_family"),
                "strategy_subtype": diagnostics.get("strategy_subtype")
                or candidate.get("strategy_subtype"),
                "direction": direction,
                "replay_source": replay_source,
                "geometry_state": geometry,
                "ranking_role": diagnostics.get("ranking_role") or candidate.get("ranking_role"),
                "ranking_outcome": diagnostics.get("ranking_outcome")
                or candidate.get("ranking_outcome"),
                "entry_status": diagnostics.get("entry_status") or candidate.get("entry_status"),
                "entry_mode": diagnostics.get("entry_mode") or candidate.get("entry_mode"),
                "higher_timeframe_conflict": htf_conflict,
                "higher_timeframe_relationship": diagnostics.get("higher_timeframe_relationship")
                or candidate.get("higher_timeframe_relationship"),
                "higher_timeframe_severity": diagnostics.get("higher_timeframe_severity")
                or candidate.get("higher_timeframe_severity"),
                "final_score": diagnostics.get("final_score") or candidate.get("final_score"),
                "final_rank_score": diagnostics.get("final_rank_score")
                or candidate.get("final_rank_score"),
                "target_quality": diagnostics.get("target_quality")
                or candidate.get("target_quality"),
                "gross_tp1_r": gross_tp1_r,
                "net_tp1_r": net_tp1_r,
                "pre_exit_mfe_r": pre_exit_mfe,
                "pre_exit_mae_r": pre_exit_mae,
                "counterfactual_path_mfe_r": full_path_mfe,
                "counterfactual_path_mae_r": full_path_mae,
                "post_exit_additional_mfe_r": post_exit_additional_mfe,
                "realized_r": trade.get("realized_r_multiple"),
                "first_exit_event": metadata.get("first_exit_event"),
                "first_stop_touch_candle": metadata.get("first_stop_touch_candle"),
                "first_stop_touch_time": metadata.get("first_stop_touch_time"),
                "first_tp1_touch_candle": metadata.get("first_tp1_touch_candle"),
                "first_tp1_touch_time": metadata.get("first_tp1_touch_time"),
                "same_candle_stop_target_ambiguous": metadata.get(
                    "same_candle_stop_target_ambiguous"
                ),
                "reached_0_5r": progress.get("reached_0_5r"),
                "reached_1r": progress.get("reached_1r"),
                "reached_1_5r": progress.get("reached_1_5r"),
                "reached_2r": progress.get("reached_2r"),
                "reached_3r": progress.get("reached_3r"),
                "tp1_progress_ratio": progress.get("tp1_progress_ratio"),
                "reason_codes": "|".join(
                    str(value)
                    for value in as_list(
                        diagnostics.get("reason_codes") or candidate.get("reason_codes")
                    )
                ),
            }
            row["forensic_family"] = classify_stop(row) if row["outcome"] == "stop" else ""
            shadow_rows.append(row)

    stopped = [row for row in shadow_rows if row["outcome"] == "stop"]
    targets = [row for row in shadow_rows if row["outcome"] == "target"]
    valid_geometry = [row for row in shadow_rows if row["geometry_state"] == "VALID_GEOMETRY"]
    valid_stops = [row for row in stopped if row["geometry_state"] == "VALID_GEOMETRY"]

    def grouped_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        stops = [row for row in rows if row["outcome"] == "stop"]
        return {
            "count": len(rows),
            "outcomes": dict(Counter(row["outcome"] for row in rows)),
            "forensic_families": dict(Counter(row["forensic_family"] for row in stops)),
            "geometry_states": dict(Counter(row["geometry_state"] for row in rows)),
            "first_exit_events": dict(
                Counter(str(row.get("first_exit_event") or "missing") for row in rows)
            ),
            "average_pre_exit_mfe_r": average(rows, "pre_exit_mfe_r"),
            "average_pre_exit_mae_r": average(rows, "pre_exit_mae_r"),
            "average_counterfactual_path_mfe_r": average(rows, "counterfactual_path_mfe_r"),
            "average_post_exit_additional_mfe_r": average(rows, "post_exit_additional_mfe_r"),
            "average_tp1_progress_ratio": average(rows, "tp1_progress_ratio"),
        }

    by_profile = {
        profile: {
            "reports": report_counts[profile],
            **grouped_summary([row for row in shadow_rows if row["profile"] == profile]),
        }
        for profile in sorted(report_counts)
    }

    strategy_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        strategy_groups[str(row["strategy"])].append(row)
    by_strategy = {
        strategy: grouped_summary(rows) for strategy, rows in sorted(strategy_groups.items())
    }

    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        source_groups[str(row["replay_source"] or "unknown")].append(row)
    by_replay_source = {
        source: grouped_summary(rows) for source, rows in sorted(source_groups.items())
    }

    relationship_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        relationship_groups[str(row["higher_timeframe_relationship"] or "unknown")].append(row)
    by_htf_relationship = {
        relationship: grouped_summary(rows)
        for relationship, rows in sorted(relationship_groups.items())
    }

    shadow_summary: dict[str, Any] = {
        **grouped_summary(shadow_rows),
        "stop_count": len(stopped),
        "target_count": len(targets),
        "valid_geometry_count": len(valid_geometry),
        "valid_geometry_stop_count": len(valid_stops),
        "ambiguous_same_candle_count": sum(
            row["first_exit_event"] == "same_candle_ambiguous_stop_first" for row in shadow_rows
        ),
        "post_stop_recovery_ge_1r_count": sum(
            (finite_number(row.get("post_exit_additional_mfe_r")) or 0.0) >= 1.0 for row in stopped
        ),
        "valid_stops_reaching_1r": sum(row.get("reached_1r") is True for row in valid_stops),
        "valid_stops_reaching_2r": sum(row.get("reached_2r") is True for row in valid_stops),
        "valid_stops_reaching_3r": sum(row.get("reached_3r") is True for row in valid_stops),
    }

    summary: dict[str, Any] = {
        "campaign_directory": str(directory),
        "report_count": len(files),
        "reports_by_profile": dict(report_counts),
        "section_outcomes": {section: dict(counts) for section, counts in section_outcomes.items()},
        "shadow": shadow_summary,
        "by_profile": by_profile,
        "by_strategy": by_strategy,
        "by_replay_source": by_replay_source,
        "by_htf_relationship": by_htf_relationship,
    }

    (directory / "forensic_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    write_csv(directory / "forensic_shadow_trades.csv", shadow_rows)
    write_csv(directory / "forensic_decisions.csv", decision_rows)

    markdown = [
        "# Apex First-Touch Forensic Summary",
        "",
        f"- Reports: **{len(files)}**",
        f"- Shadow trades: **{len(shadow_rows)}**",
        f"- Stops: **{len(stopped)}**",
        f"- Targets: **{len(targets)}**",
        f"- Valid geometry: **{len(valid_geometry)}**",
        f"- Same-candle ambiguity: **{shadow_summary['ambiguous_same_candle_count']}**",
        (
            "- Stops with >=1R post-exit recovery: "
            f"**{shadow_summary['post_stop_recovery_ge_1r_count']}**"
        ),
        "",
        "## Forensic families",
        "",
    ]
    for family, count in sorted(as_mapping(shadow_summary["forensic_families"]).items()):
        markdown.append(f"- `{family}`: {count}")
    markdown.extend(["", "## Geometry states", ""])
    for state, count in sorted(as_mapping(shadow_summary["geometry_states"]).items()):
        markdown.append(f"- `{state}`: {count}")
    markdown.extend(["", "## First-exit events", ""])
    for event, count in sorted(as_mapping(shadow_summary["first_exit_events"]).items()):
        markdown.append(f"- `{event}`: {count}")
    (directory / "forensic_report.md").write_text("\n".join(markdown) + "\n")

    print(f"Reports processed: {len(files)}")
    print(f"Shadow trades: {len(shadow_rows)}")
    print(f"First-exit events: {shadow_summary['first_exit_events']}")
    print(f"Geometry states: {shadow_summary['geometry_states']}")
    print(f"Forensic families: {shadow_summary['forensic_families']}")
    print(f"Summary: {directory / 'forensic_summary.json'}")


if __name__ == "__main__":
    main()
