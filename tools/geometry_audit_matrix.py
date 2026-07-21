#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FILES = ("clo.json", "era.json", "vanry.json", "hei.json")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing report: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"expected object in {path}")
    return data


def rr(entry: dict[str, Any], invalidation: dict[str, Any], targets: list[Any]) -> float | None:
    target = as_dict(targets[0]).get("price") if targets else None
    values = (entry.get("preferred"), invalidation.get("price"), target)
    if not all(isinstance(value, (int, float)) for value in values):
        return None
    risk = abs(float(values[0]) - float(values[1]))
    if risk <= 0:
        return None
    return abs(float(values[2]) - float(values[0])) / risk


def methodology(report: dict[str, Any], candidate_id: str) -> tuple[Any, Any]:
    decisions = as_dict(as_dict(report.get("methodology_gate")).get("opportunity_decisions"))
    item = as_dict(decisions.get(candidate_id))
    reasons = as_list(item.get("reasons"))
    return item.get("action"), reasons[0] if reasons else None


def thesis_rows(report: dict[str, Any], source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    focused = as_dict(report.get("focused_analysis"))
    for side in ("long", "short"):
        thesis = as_dict(focused.get(f"{side}_thesis"))
        candidate_id = thesis.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        entry = as_dict(thesis.get("entry"))
        invalidation = as_dict(thesis.get("invalidation"))
        targets = as_list(thesis.get("targets"))
        warnings = [str(x) for x in as_list(thesis.get("warnings"))]
        blockers = [str(x) for x in as_list(thesis.get("blockers"))]
        action, method_reason = methodology(report, candidate_id)
        rows.append(
            {
                "source": source,
                "symbol": report.get("symbol"),
                "candidate_id": candidate_id,
                "strategy": thesis.get("primary_strategy"),
                "direction": thesis.get("direction", side),
                "candidate_outcome": thesis.get("candidate_outcome"),
                "entry_status": thesis.get("entry_status"),
                "entry_mode": entry.get("mode"),
                "cmp_inside_zone": entry.get("distance_from_current") == 0,
                "tp1_rr": rr(entry, invalidation, targets),
                "score": thesis.get("score"),
                "approval_threshold": thesis.get("approval_threshold"),
                "setup_quality": thesis.get("setup_quality"),
                "execution_quality": thesis.get("execution_quality"),
                "target_quality": thesis.get("target_quality"),
                "risk_quality": thesis.get("risk_quality"),
                "provisional": any("provisional" in x.lower() for x in warnings),
                "confirmation_incomplete": any(
                    "confirmation is incomplete" in x.lower() for x in warnings + blockers
                ),
                "htf_conflict": any("higher-timeframe" in x.lower() for x in warnings + blockers),
                "extended": entry.get("is_extended"),
                "executable_now": thesis.get("executable_now"),
                "methodology_action": action,
                "methodology_reason": method_reason,
                "primary_blocker": blockers[0] if blockers else None,
            }
        )
    return rows


def setup_rows(report: dict[str, Any], source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in ("setup", "developing_setup"):
        setup = as_dict(report.get(name))
        candidate_id = setup.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        entry = as_dict(setup.get("entry"))
        target = (
            as_dict(as_list(setup.get("take_profits"))[0])
            if as_list(setup.get("take_profits"))
            else {}
        )
        quality = as_dict(setup.get("quality_dimensions"))
        warnings = [str(x) for x in as_list(setup.get("warnings"))]
        rows.append(
            {
                "source": source,
                "symbol": report.get("symbol"),
                "candidate_id": candidate_id,
                "strategy": setup.get("strategy"),
                "direction": setup.get("direction"),
                "candidate_outcome": name,
                "entry_status": setup.get("entry_status"),
                "entry_mode": setup.get("entry_mode"),
                "cmp_inside_zone": entry.get("current_price_inside_zone"),
                "tp1_rr": target.get("risk_reward"),
                "score": setup.get("confidence_score"),
                "approval_threshold": None,
                "setup_quality": quality.get("setup_quality"),
                "execution_quality": quality.get("execution_quality"),
                "target_quality": quality.get("target_quality"),
                "risk_quality": quality.get("risk_quality"),
                "provisional": setup.get("provisional"),
                "confirmation_incomplete": bool(
                    setup.get("confirmation_required") and not setup.get("confirmation_complete")
                ),
                "htf_conflict": any("higher-timeframe" in x.lower() for x in warnings),
                "extended": None,
                "executable_now": setup.get("execution_allowed_now"),
                "methodology_action": None,
                "methodology_reason": None,
                "primary_blocker": None,
            }
        )
    return rows


def flag_row(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if row.get("executable_now") and row.get("confirmation_incomplete"):
        flags.append("execution allowed with incomplete confirmation")
    if row.get("executable_now") and row.get("provisional"):
        flags.append("execution allowed with provisional evidence")
    if row.get("execution_quality") == 100 and (
        row.get("confirmation_incomplete") or row.get("provisional")
    ):
        flags.append("100 execution quality despite incomplete/provisional trigger")
    if row.get("cmp_inside_zone") is False and row.get("executable_now"):
        flags.append("execution allowed while CMP is outside entry zone")
    value = row.get("tp1_rr")
    if isinstance(value, (int, float)) and value < 1.0:
        flags.append(f"TP1 below 1R ({value:.3f}R)")
    return flags


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value).replace("|", r"\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=Path("data/reports/geometry_audit"))
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for filename in FILES:
        report = load(args.report_dir / filename)
        rows.extend(thesis_rows(report, filename))
        rows.extend(setup_rows(report, filename))

    rows.sort(
        key=lambda row: (
            str(row.get("symbol")),
            str(row.get("candidate_id")),
            str(row.get("candidate_outcome")),
        )
    )

    json_path = args.report_dir / "defect_origin_matrix.json"
    md_path = args.report_dir / "defect_origin_matrix.md"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    columns = (
        "symbol",
        "candidate_id",
        "candidate_outcome",
        "entry_status",
        "entry_mode",
        "cmp_inside_zone",
        "tp1_rr",
        "score",
        "execution_quality",
        "provisional",
        "confirmation_incomplete",
        "htf_conflict",
        "extended",
        "executable_now",
        "methodology_action",
        "primary_blocker",
    )
    lines = [
        "# Apex Batch 0 — Defect-Origin Matrix",
        "",
        "Generated from committed baseline JSON. Runtime decisions are unchanged.",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(column)) for column in columns) + " |")

    lines.extend(["", "## Automatic contradiction flags", ""])
    found = False
    for row in rows:
        flags = flag_row(row)
        if not flags:
            continue
        found = True
        lines.append(
            f"- **{fmt(row.get('symbol'))} · {fmt(row.get('candidate_id'))}:** "
            + "; ".join(flags)
            + "."
        )
    if not found:
        lines.append("- None detected by the initial Batch 0 rules.")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    print(f"rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
