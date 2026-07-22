"""Run the standard 216-job Apex backtest campaign with shared UTC anchors."""

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
    "AKEUSDT",
    "BANKUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "BTWUSDT",
    "BULLAUSDT",
    "EPICUSDT",
    "ERAUSDT",
    "ESPORTSUSDT",
    "ETHUSDT",
    "HEMIUSDT",
    "LABUSDT",
    "PYTHUSDT",
    "REUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "TACUSDT",
    "VANRYUSDT",
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
    anchor: str
    report_file: str
    log_file: str
    return_code: int
    report_valid: bool
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0 and self.report_valid


def default_anchors(now: datetime | None = None) -> tuple[datetime, ...]:
    """Return four shared, 24-hour-spaced, completed 15-minute boundaries."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    latest = current.replace(
        minute=(current.minute // 15) * 15,
        second=0,
        microsecond=0,
    )
    return tuple(latest - timedelta(hours=24 * index) for index in range(4))


def parse_anchor(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("anchors must include a timezone")
    return parsed.astimezone(UTC)


def build_jobs(
    *,
    anchors: Sequence[datetime],
    output_dir: Path,
) -> tuple[CampaignJob, ...]:
    jobs: list[CampaignJob] = []
    log_dir = output_dir / "logs"
    for anchor in anchors:
        anchor_label = anchor.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        for symbol in SYMBOLS:
            for profile in PROFILES:
                stem = (
                    f"{symbol}_{profile.name}_{profile.timeframe}_"
                    f"{profile.replay_candles}_{anchor_label}"
                )
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


def run_job(job: CampaignJob, *, apex_command: str, candle_limit: int) -> JobResult:
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
            payload = json.loads(job.report_path.read_text(encoding="utf-8"))
            actual_schema = payload.get("schema_version") if isinstance(payload, dict) else None
            report_valid = actual_schema == EXPECTED_BACKTEST_SCHEMA_VERSION
            if not report_valid:
                error = (
                    "report schema is missing or unexpected: "
                    f"expected {EXPECTED_BACKTEST_SCHEMA_VERSION}, got {actual_schema!r}"
                )
        except (OSError, json.JSONDecodeError) as exc:
            error = f"report validation failed: {exc}"
    else:
        error = f"apex exited with code {completed.returncode}"

    return JobResult(
        symbol=job.symbol,
        profile=job.profile.name,
        anchor=job.anchor.isoformat(),
        report_file=str(job.report_path),
        log_file=str(job.log_path),
        return_code=completed.returncode,
        report_valid=report_valid,
        error=error,
    )


def run_campaign(args: argparse.Namespace) -> int:
    anchors = tuple(args.anchor) if args.anchor else default_anchors()
    jobs = build_jobs(anchors=anchors, output_dir=args.output_dir)
    results: list[JobResult] = []
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
        for completed_count, future in enumerate(as_completed(future_by_job), start=1):
            result = future.result()
            results.append(result)
            status = "OK" if result.succeeded else "FAILED"
            print(
                f"[{completed_count:03d}/{len(jobs):03d}] {status} "
                f"{result.symbol} {result.profile} {result.anchor}",
                flush=True,
            )

    ordered = sorted(results, key=lambda item: (item.anchor, item.symbol, item.profile))
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "job_count": len(jobs),
        "successful_count": sum(item.succeeded for item in ordered),
        "failed_count": sum(not item.succeeded for item in ordered),
        "workers": args.workers,
        "anchors": [item.isoformat() for item in anchors],
        "profiles": [asdict(profile) for profile in PROFILES],
        "symbols": list(SYMBOLS),
        "results": [asdict(item) | {"succeeded": item.succeeded} for item in ordered],
    }
    summary_path = args.output_dir / "campaign_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0 if summary["failed_count"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apex-command", default="apex")
    parser.add_argument("--workers", type=int, default=3, choices=range(1, 9))
    parser.add_argument("--candles", type=int, default=240)
    parser.add_argument(
        "--anchor",
        action="append",
        type=parse_anchor,
        help="Repeat for custom shared ISO-8601 anchors; default is four 24h-spaced anchors.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backtest-samples") / "anchored-216",
    )
    return parser


def main() -> int:
    return run_campaign(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
