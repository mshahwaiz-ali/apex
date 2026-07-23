"""Run the focused Apex Batch 11D.6D Part 2E campaign.

Produces 30 jobs:
- 10 symbols
- 3 replay profiles/timeframes
- 1 shared UTC anchor

This script is diagnostic-only and does not change Apex production behavior.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "SUIUSDT",
    "EPICUSDT",
    "ESPORTSUSDT",
    "AKEUSDT",
    "PYTHUSDT",
    "HEMIUSDT",
)


@dataclass(frozen=True, slots=True)
class ReplayProfile:
    name: str
    timeframe: str
    replay_candles: int
    decision_points: int


PROFILES = (
    ReplayProfile("micro", "1m", 20, 3),
    ReplayProfile("standard", "5m", 24, 5),
    ReplayProfile("environment", "15m", 20, 3),
)

EXPECTED_BACKTEST_SCHEMA_VERSION = 5


@dataclass(frozen=True, slots=True)
class CampaignJob:
    symbol: str
    profile: ReplayProfile
    anchor: datetime
    report_path: Path
    log_path: Path


@dataclass(frozen=True, slots=True)
class JobResult:
    symbol: str
    profile: str
    timeframe: str
    anchor: str
    report_file: str
    log_file: str
    return_code: int
    report_valid: bool
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0 and self.report_valid


def default_anchor(now: datetime | None = None) -> datetime:
    """Return the latest completed shared 15-minute UTC boundary."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    boundary = current.replace(
        minute=(current.minute // 15) * 15,
        second=0,
        microsecond=0,
    )
    # Step back one full boundary so every requested timeframe is safely closed.
    return boundary - timedelta(minutes=15)


def parse_anchor(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("anchor must include a timezone")
    return parsed.astimezone(UTC)


def default_output_dir(anchor: datetime) -> Path:
    anchor_label = anchor.strftime("%Y%m%dT%H%M%SZ")
    return (
        Path("backtest-samples")
        / f"11d6d-part2e-robustness-{anchor_label}"
    )


def build_jobs(
    *,
    anchor: datetime,
    output_dir: Path,
) -> tuple[CampaignJob, ...]:
    jobs: list[CampaignJob] = []
    log_dir = output_dir / "logs"
    anchor_label = anchor.strftime("%Y%m%dT%H%M%SZ")

    for symbol in SYMBOLS:
        for profile in PROFILES:
            stem = f"{symbol}_{profile.timeframe}_{anchor_label}"
            jobs.append(
                CampaignJob(
                    symbol=symbol,
                    profile=profile,
                    anchor=anchor,
                    report_path=output_dir / f"{stem}.json",
                    log_path=log_dir / f"{stem}.log",
                )
            )

    return tuple(jobs)


def run_job(
    job: CampaignJob,
    *,
    apex_command: str,
    candle_limit: int,
) -> JobResult:
    job.report_path.parent.mkdir(parents=True, exist_ok=True)
    job.log_path.parent.mkdir(parents=True, exist_ok=True)

    command = (
        apex_command,
        "backtest",
        job.symbol,
        "--candles",
        str(candle_limit),
        "--replay-timeframe",
        job.profile.timeframe,
        "--replay-candles",
        str(job.profile.replay_candles),
        "--decision-points",
        str(job.profile.decision_points),
        "--as-of",
        job.anchor.isoformat(),
        "--report-file",
        str(job.report_path),
    )

    with job.log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )

    report_valid = False
    error: str | None = None

    if completed.returncode == 0:
        try:
            payload = json.loads(
                job.report_path.read_text(encoding="utf-8")
            )
            actual_schema = (
                payload.get("schema_version")
                if isinstance(payload, dict)
                else None
            )
            report_valid = (
                actual_schema == EXPECTED_BACKTEST_SCHEMA_VERSION
            )
            if not report_valid:
                error = (
                    "unexpected report schema: "
                    f"expected {EXPECTED_BACKTEST_SCHEMA_VERSION}, "
                    f"got {actual_schema!r}"
                )
        except (OSError, json.JSONDecodeError) as exc:
            error = f"report validation failed: {exc}"
    else:
        error = f"apex exited with code {completed.returncode}"

    return JobResult(
        symbol=job.symbol,
        profile=job.profile.name,
        timeframe=job.profile.timeframe,
        anchor=job.anchor.isoformat(),
        report_file=str(job.report_path),
        log_file=str(job.log_path),
        return_code=completed.returncode,
        report_valid=report_valid,
        error=error,
    )


def run_campaign(args: argparse.Namespace) -> int:
    anchor = args.anchor or default_anchor()
    output_dir = args.output_dir or default_output_dir(anchor)
    jobs = build_jobs(anchor=anchor, output_dir=output_dir)

    results: list[JobResult] = []

    print(f"Campaign directory: {output_dir}")
    print(f"Shared UTC anchor : {anchor.isoformat()}")
    print(f"Jobs              : {len(jobs)}")
    print()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_by_job = {
            executor.submit(
                run_job,
                job,
                apex_command=args.apex_command,
                candle_limit=args.candles,
            ): job
            for job in jobs
        }

        for completed_count, future in enumerate(
            as_completed(future_by_job),
            start=1,
        ):
            result = future.result()
            results.append(result)
            status = "OK" if result.succeeded else "FAILED"
            print(
                f"[{completed_count:02d}/{len(jobs):02d}] "
                f"{status} {result.symbol} {result.timeframe}",
                flush=True,
            )

    ordered = sorted(
        results,
        key=lambda item: (item.symbol, item.timeframe),
    )
    successful_count = sum(item.succeeded for item in ordered)
    failed_count = len(ordered) - successful_count

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "campaign": "11D.6D Part 2E robustness",
        "job_count": len(jobs),
        "successful_count": successful_count,
        "failed_count": failed_count,
        "workers": args.workers,
        "anchor": anchor.isoformat(),
        "profiles": [asdict(profile) for profile in PROFILES],
        "symbols": list(SYMBOLS),
        "results": [
            asdict(item) | {"succeeded": item.succeeded}
            for item in ordered
        ],
    }

    summary_path = output_dir / "campaign_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    latest_pointer = Path("/tmp/apex_11d6d_part2e_latest_run_dir")
    latest_pointer.write_text(
        str(output_dir.resolve()) + "\n",
        encoding="utf-8",
    )

    json_reports = len(
        [
            path
            for path in output_dir.glob("*.json")
            if path.name != "campaign_summary.json"
        ]
    )
    logs = len(tuple((output_dir / "logs").glob("*.log")))

    print()
    print(f"Summary           : {summary_path}")
    print(f"JSON reports      : {json_reports}")
    print(f"Logs              : {logs}")
    print(f"Successful jobs   : {successful_count}")
    print(f"Failed jobs       : {failed_count}")
    print(f"Latest-run pointer: {latest_pointer}")

    return 0 if failed_count == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apex-command", default="apex")
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        choices=range(1, 9),
    )
    parser.add_argument("--candles", type=int, default=240)
    parser.add_argument(
        "--anchor",
        type=parse_anchor,
        help=(
            "Optional shared ISO-8601 UTC anchor. "
            "Default: latest completed 15-minute boundary."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional output directory.",
    )
    return parser


def main() -> int:
    return run_campaign(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
