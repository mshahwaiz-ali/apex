"""Run manifest-verified, full-range canonical archive replays in parallel."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_BACKTEST_SCHEMA_VERSION = 6
DEFAULT_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "AVAXUSDT",
    "SUIUSDT",
    "AAVEUSDT",
)


@dataclass(frozen=True, slots=True)
class ArchiveReplayResult:
    symbol: str
    report_file: str
    log_file: str
    return_code: int
    report_valid: bool
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0 and self.report_valid


def _run_symbol(
    symbol: str,
    *,
    apex_command: str,
    archive_dataset_dir: Path,
    output_dir: Path,
    config_dir: Path,
    candles: int,
    decision_points: int,
    replay_timeframe: str,
    replay_candles: int,
) -> ArchiveReplayResult:
    report_path = output_dir / f"{symbol.lower()}_report.json"
    log_path = output_dir / "logs" / f"{symbol.lower()}.log"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = (
        apex_command,
        "backtest",
        symbol,
        "--archive-dataset-dir",
        str(archive_dataset_dir),
        "--sample-full-range",
        "--candles",
        str(candles),
        "--decision-points",
        str(decision_points),
        "--replay-timeframe",
        replay_timeframe,
        "--replay-candles",
        str(replay_candles),
        "--config-dir",
        str(config_dir),
        "--report-file",
        str(report_path),
    )
    with log_path.open("w", encoding="utf-8") as log:
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
            payload = json.loads(report_path.read_text(encoding="utf-8"))
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
    return ArchiveReplayResult(
        symbol=symbol,
        report_file=str(report_path),
        log_file=str(log_path),
        return_code=completed.returncode,
        report_valid=report_valid,
        error=error,
    )


def run_campaign(args: argparse.Namespace) -> int:
    symbols = tuple(args.symbol) if args.symbol else DEFAULT_SYMBOLS
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[ArchiveReplayResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _run_symbol,
                symbol,
                apex_command=args.apex_command,
                archive_dataset_dir=args.archive_dataset_dir,
                output_dir=args.output_dir,
                config_dir=args.config_dir,
                candles=args.candles,
                decision_points=args.decision_points,
                replay_timeframe=args.replay_timeframe,
                replay_candles=args.replay_candles,
            ): symbol
            for symbol in symbols
        }
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            print(
                f"[{index:02d}/{len(futures):02d}] "
                f"{'OK' if result.succeeded else 'FAILED'} {result.symbol}",
                flush=True,
            )

    ordered = tuple(sorted(results, key=lambda item: item.symbol))
    summary = {
        "schema_version": 1,
        "campaign_kind": "manifest_verified_full_range_calibration",
        "generated_at": datetime.now(UTC).isoformat(),
        "archive_dataset_dir": str(args.archive_dataset_dir),
        "config_dir": str(args.config_dir),
        "symbols": list(symbols),
        "decision_points_per_symbol": args.decision_points,
        "replay_timeframe": args.replay_timeframe,
        "replay_candles": args.replay_candles,
        "successful_count": sum(item.succeeded for item in ordered),
        "failed_count": sum(not item.succeeded for item in ordered),
        "results": [asdict(item) | {"succeeded": item.succeeded} for item in ordered],
    }
    (args.output_dir / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "outcome_bundle.json").write_text(
        json.dumps(
            {"outcome_files": [Path(item.report_file).name for item in ordered if item.succeeded]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if summary["failed_count"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--apex-command", default=".venv/bin/apex")
    parser.add_argument("--workers", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--candles", type=int, default=201)
    parser.add_argument("--decision-points", type=int, default=200)
    parser.add_argument("--replay-timeframe", default="5m")
    parser.add_argument("--replay-candles", type=int, default=24)
    parser.add_argument("--symbol", action="append")
    return parser


def main() -> int:
    return run_campaign(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
