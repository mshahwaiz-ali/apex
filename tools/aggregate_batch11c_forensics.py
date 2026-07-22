#!/usr/bin/env python3
"""Aggregate Apex Batch 11C forensic reports.

Usage:
    python3 tools/aggregate_batch11c_forensics.py \
      backtest-samples/batch11c-forensics-54

Outputs are written inside the campaign directory:
    forensic_summary.json
    forensic_shadow_trades.csv
    forensic_decisions.csv
    forensic_report.md
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def report_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.glob("*.json")
        if path.name not in {
            "campaign_summary.json",
            "forensic_summary.json",
        }
    )


def profile_from_filename(path: Path) -> str:
    name = path.stem
    for profile in ("micro", "standard", "environment"):
        if f"_{profile}_" in name:
            return profile
    return "unknown"


def symbol_from_filename(path: Path) -> str:
    return path.name.split("_", 1)[0]


def outcome_name(trade: Mapping[str, Any]) -> str:
    value = trade.get("outcome")
    if isinstance(value, Mapping):
        value = value.get("value")
    return str(value) if value is not None else "unknown"


def shadow_trades(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    shadow = as_mapping(payload.get("shadow_replay"))
    trades = shadow.get("trades")
    return [as_mapping(item) for item in as_list(trades)]


def canonical_trades(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("trades", "production_trades"):
        values = payload.get(key)
        if isinstance(values, list):
            return [as_mapping(item) for item in values]
    production = as_mapping(payload.get("production_replay"))
    values = production.get("trades")
    return [as_mapping(item) for item in as_list(values)]


def conditional_trades(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    conditional = as_mapping(payload.get("conditional_replay"))
    values = conditional.get("trades")
    return [as_mapping(item) for item in as_list(values)]


def opportunity_trades(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    opportunity = as_mapping(payload.get("opportunity_replay"))
    values = opportunity.get("trades")
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


def classify_loss(row: Mapping[str, Any]) -> str:
    mfe = finite_number(row.get("mfe_r"))
    progress = finite_number(row.get("tp1_progress_ratio"))
    htf_conflict = row.get("higher_timeframe_conflict")
    if mfe is None:
        return "UNRESOLVED_EVIDENCE"
    if mfe < 0.5:
        return "WEAK_FOLLOW_THROUGH"
    if progress is not None and progress >= 0.8:
        return "NEAR_TARGET_REVERSAL"
    if mfe >= 2.0:
        return "MEANINGFUL_MFE_THEN_STOP"
    if mfe >= 1.0:
        return "MODERATE_MFE_THEN_STOP"
    if htf_conflict is True:
        return "HTF_CONFLICT_LOW_MFE"
    return "LOW_MFE_THEN_STOP"


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
    all_section_outcomes: dict[str, Counter[str]] = {
        "production": Counter(),
        "conditional": Counter(),
        "opportunity": Counter(),
        "shadow": Counter(),
    }

    for path in files:
        payload = as_mapping(json.loads(path.read_text()))
        profile = profile_from_filename(path)
        symbol = symbol_from_filename(path)
        report_counts[profile] += 1
        candidates = candidate_map(payload)

        for section, trades in (
            ("production", canonical_trades(payload)),
            ("conditional", conditional_trades(payload)),
            ("opportunity", opportunity_trades(payload)),
            ("shadow", shadow_trades(payload)),
        ):
            for trade in trades:
                all_section_outcomes[section][outcome_name(trade)] += 1

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
                    "entry_confirmation_complete": confirmation.get(
                        "entry_confirmation_complete"
                    ),
                    "higher_timeframe_conflict": confirmation.get(
                        "higher_timeframe_conflict"
                    ),
                    "continuation_state": confirmation.get("continuation_state"),
                }
            )

        for trade in shadow_trades(payload):
            diagnostics = as_mapping(trade.get("diagnostics"))
            confirmation = as_mapping(diagnostics.get("confirmation"))
            progress = as_mapping(trade.get("r_progress"))
            decision_time = str(trade.get("decision_time") or "")
            candidate_id = str(
                trade.get("opportunity_id")
                or trade.get("candidate_id")
                or diagnostics.get("candidate_id")
                or ""
            )
            candidate = candidates.get((decision_time, candidate_id), {})
            candidate_confirmation = as_mapping(candidate.get("confirmation"))

            htf_conflict = confirmation.get("higher_timeframe_conflict")
            if htf_conflict is None:
                htf_conflict = candidate_confirmation.get("higher_timeframe_conflict")

            row: dict[str, Any] = {
                "file": path.name,
                "symbol": symbol,
                "profile": profile,
                "decision_time": decision_time,
                "candidate_id": candidate_id,
                "outcome": outcome_name(trade),
                "strategy": diagnostics.get("strategy") or candidate.get("strategy"),
                "strategy_family": diagnostics.get("strategy_family")
                or candidate.get("strategy_family"),
                "strategy_subtype": diagnostics.get("strategy_subtype")
                or candidate.get("strategy_subtype"),
                "direction": diagnostics.get("direction") or candidate.get("direction"),
                "ranking_role": diagnostics.get("ranking_role")
                or candidate.get("ranking_role"),
                "ranking_outcome": diagnostics.get("ranking_outcome")
                or candidate.get("ranking_outcome"),
                "entry_status": diagnostics.get("entry_status")
                or candidate.get("entry_status"),
                "entry_mode": diagnostics.get("entry_mode")
                or candidate.get("entry_mode"),
                "higher_timeframe_conflict": htf_conflict,
                "higher_timeframe_relationship": diagnostics.get(
                    "higher_timeframe_relationship"
                )
                or candidate.get("higher_timeframe_relationship"),
                "higher_timeframe_severity": diagnostics.get(
                    "higher_timeframe_severity"
                )
                or candidate.get("higher_timeframe_severity"),
                "final_score": diagnostics.get("final_score")
                or candidate.get("final_score"),
                "final_rank_score": diagnostics.get("final_rank_score")
                or candidate.get("final_rank_score"),
                "target_quality": diagnostics.get("target_quality")
                or candidate.get("target_quality"),
                "gross_tp1_r": diagnostics.get("gross_tp1_r")
                or candidate.get("gross_tp1_r"),
                "net_tp1_r": diagnostics.get("net_tp1_r")
                or candidate.get("net_tp1_r"),
                "mfe_r": trade.get("maximum_favorable_excursion_r"),
                "mae_r": trade.get("maximum_adverse_excursion_r"),
                "realized_r": trade.get("realized_r_multiple"),
                "reached_0_5r": progress.get("reached_0_5r"),
                "reached_1r": progress.get("reached_1r"),
                "reached_1_5r": progress.get("reached_1_5r"),
                "reached_2r": progress.get("reached_2r"),
                "reached_3r": progress.get("reached_3r"),
                "tp1_progress_ratio": progress.get("tp1_progress_ratio"),
                "reason_codes": "|".join(
                    str(value)
                    for value in as_list(
                        diagnostics.get("reason_codes")
                        or candidate.get("reason_codes")
                    )
                ),
            }
            row["loss_family"] = (
                classify_loss(row) if row["outcome"] == "stop" else ""
            )
            shadow_rows.append(row)

    stopped = [row for row in shadow_rows if row["outcome"] == "stop"]
    target = [row for row in shadow_rows if row["outcome"] == "target"]

    def average(rows: Iterable[Mapping[str, Any]], key: str) -> float | None:
        values = [
            value
            for row in rows
            if (value := finite_number(row.get(key))) is not None
        ]
        return mean(values) if values else None

    by_profile: dict[str, Any] = {}
    for profile in sorted(report_counts):
        rows = [row for row in shadow_rows if row["profile"] == profile]
        losses = [row for row in rows if row["outcome"] == "stop"]
        by_profile[profile] = {
            "reports": report_counts[profile],
            "shadow_trades": len(rows),
            "outcomes": dict(Counter(row["outcome"] for row in rows)),
            "loss_families": dict(Counter(row["loss_family"] for row in losses)),
            "average_mfe_r": average(rows, "mfe_r"),
            "average_mae_r": average(rows, "mae_r"),
            "average_tp1_progress_ratio": average(rows, "tp1_progress_ratio"),
        }

    by_strategy: dict[str, Any] = {}
    strategy_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        strategy_groups[str(row.get("strategy") or "unknown")].append(row)
    for strategy, rows in sorted(strategy_groups.items()):
        losses = [row for row in rows if row["outcome"] == "stop"]
        by_strategy[strategy] = {
            "count": len(rows),
            "outcomes": dict(Counter(row["outcome"] for row in rows)),
            "loss_families": dict(Counter(row["loss_family"] for row in losses)),
            "average_mfe_r": average(rows, "mfe_r"),
            "average_mae_r": average(rows, "mae_r"),
            "average_tp1_progress_ratio": average(rows, "tp1_progress_ratio"),
        }

    summary = {
        "campaign_directory": str(directory),
        "report_count": len(files),
        "reports_by_profile": dict(report_counts),
        "section_outcomes": {
            section: dict(counts)
            for section, counts in all_section_outcomes.items()
        },
        "shadow": {
            "trade_count": len(shadow_rows),
            "outcomes": dict(Counter(row["outcome"] for row in shadow_rows)),
            "stop_count": len(stopped),
            "target_count": len(target),
            "loss_families": dict(
                Counter(row["loss_family"] for row in stopped)
            ),
            "average_mfe_r": average(shadow_rows, "mfe_r"),
            "average_mae_r": average(shadow_rows, "mae_r"),
            "average_tp1_progress_ratio": average(
                shadow_rows, "tp1_progress_ratio"
            ),
            "stops_reaching_1r": sum(
                row.get("reached_1r") is True for row in stopped
            ),
            "stops_reaching_2r": sum(
                row.get("reached_2r") is True for row in stopped
            ),
            "stops_reaching_3r": sum(
                row.get("reached_3r") is True for row in stopped
            ),
            "stops_with_htf_conflict": sum(
                row.get("higher_timeframe_conflict") is True for row in stopped
            ),
        },
        "by_profile": by_profile,
        "by_strategy": by_strategy,
    }

    summary_path = directory / "forensic_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            path.write_text("")
            return
        fieldnames = list(rows[0])
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(directory / "forensic_shadow_trades.csv", shadow_rows)
    write_csv(directory / "forensic_decisions.csv", decision_rows)

    markdown = [
        "# Apex Batch 11C Forensic Summary",
        "",
        f"- Reports: **{len(files)}**",
        f"- Shadow trades: **{len(shadow_rows)}**",
        f"- Shadow stops: **{len(stopped)}**",
        f"- Shadow targets: **{len(target)}**",
        f"- Stops reaching 1R: **{summary['shadow']['stops_reaching_1r']}**",
        f"- Stops reaching 2R: **{summary['shadow']['stops_reaching_2r']}**",
        f"- Stops reaching 3R: **{summary['shadow']['stops_reaching_3r']}**",
        f"- Stops with HTF conflict: **{summary['shadow']['stops_with_htf_conflict']}**",
        "",
        "## Shadow outcomes",
        "",
    ]
    for outcome, count in sorted(summary["shadow"]["outcomes"].items()):
        markdown.append(f"- `{outcome}`: {count}")

    markdown.extend(["", "## Loss families", ""])
    for family, count in sorted(summary["shadow"]["loss_families"].items()):
        markdown.append(f"- `{family}`: {count}")

    markdown.extend(["", "## Profile breakdown", ""])
    for profile, values in by_profile.items():
        markdown.append(
            f"- **{profile}**: {values['shadow_trades']} shadow trades; "
            f"{values['outcomes']}"
        )

    markdown.extend(["", "## Strategy breakdown", ""])
    for strategy, values in by_strategy.items():
        markdown.append(
            f"- **{strategy}**: {values['count']} trades; "
            f"{values['outcomes']}; losses {values['loss_families']}"
        )

    (directory / "forensic_report.md").write_text("\n".join(markdown) + "\n")

    print(f"Reports processed: {len(files)}")
    print(f"Shadow trades: {len(shadow_rows)}")
    print(f"Shadow outcomes: {dict(Counter(row['outcome'] for row in shadow_rows))}")
    print(f"Loss families: {dict(Counter(row['loss_family'] for row in stopped))}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
