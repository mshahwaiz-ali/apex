#!/usr/bin/env python3
"""Wire the shared sweep/reclaim evaluator into backtesting shadow diagnostics.

This patch is intentionally idempotent. It preserves the legacy evaluator as
runtime authority and wraps it with shared-evaluator parity metadata only.
"""

from __future__ import annotations

from pathlib import Path


ENGINE = Path("src/apex/backtesting/engine.py")

IMPORT_ANCHOR = "from apex.domain.models import Candle\n"
IMPORT_BLOCK = (
    "from apex.backtesting.sweep_reclaim_adapter import (\n"
    "    assess_post_stop_sweep_reclaim,\n"
    "    sweep_reclaim_metadata,\n"
    ")\n"
)

LEGACY_NAME = "_legacy_post_stop_thesis_metadata"
PUBLIC_NAME = "_post_stop_thesis_metadata"

WRAPPER = r'''

_SWEEP_RECLAIM_PARITY_KEYS = (
    "post_stop_maximum_excursion_beyond_stop_r",
    "post_stop_maximum_close_beyond_stop_r",
    "post_stop_bars_closed_beyond_stop",
    "post_stop_max_consecutive_closes_beyond_stop",
    "post_stop_stop_reclaimed",
    "post_stop_bars_to_stop_reclaim",
    "post_stop_entry_reclaimed",
    "post_stop_bars_to_reclaim",
    "shallow_stop_sweep",
    "wick_only_stop_sweep",
    "deep_directional_failure",
    "sweep_reclaim_candidate",
    "sweep_reclaim_confirmed",
    "sweep_reclaim_rejected_reason",
    "reclaim_candle_body_ratio",
    "reclaim_close_location",
    "entry_level_reclaimed",
    "retest_held",
    "remaining_target_room_r",
    "recovery_entry_authorized",
    "recovery_entry_price",
    "recovery_entry_candle",
)


def _post_stop_thesis_metadata(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    entry: float,
    stop: float,
    stop_candle: Candle,
    config: BacktestConfig,
) -> dict[str, str | int | float | bool]:
    """Preserve legacy authority while recording shared-evaluator parity."""

    legacy = _legacy_post_stop_thesis_metadata(
        signal,
        candles,
        entry=entry,
        stop=stop,
        stop_candle=stop_candle,
        config=config,
    )
    shared = sweep_reclaim_metadata(
        assess_post_stop_sweep_reclaim(
            signal,
            entry_price=entry,
            stop_price=stop,
            stop_candle=stop_candle,
            confirmation_candles=candles,
        )
    )
    mismatches = tuple(
        key
        for key in _SWEEP_RECLAIM_PARITY_KEYS
        if not _sweep_reclaim_values_match(legacy.get(key), shared.get(key))
    )
    return {
        **legacy,
        "shared_sweep_reclaim_state": shared["shared_sweep_reclaim_state"],
        "shared_sweep_reclaim_parity": not mismatches,
        "shared_sweep_reclaim_mismatch_count": len(mismatches),
        "shared_sweep_reclaim_mismatch_fields": ",".join(mismatches),
    }


def _sweep_reclaim_values_match(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return abs(float(left) - float(right)) <= 1e-9
    return left == right
'''


def main() -> None:
    text = ENGINE.read_text(encoding="utf-8")

    if IMPORT_BLOCK not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("engine import anchor not found")
        text = text.replace(IMPORT_ANCHOR, IMPORT_BLOCK + IMPORT_ANCHOR, 1)

    public_definition = f"def {PUBLIC_NAME}("
    legacy_definition = f"def {LEGACY_NAME}("
    if legacy_definition not in text:
        if public_definition not in text:
            raise SystemExit("legacy sweep/reclaim evaluator definition not found")
        text = text.replace(public_definition, legacy_definition, 1)

    if "_SWEEP_RECLAIM_PARITY_KEYS = (" not in text:
        text = text.rstrip() + WRAPPER + "\n"

    ENGINE.write_text(text, encoding="utf-8")
    print(f"updated {ENGINE}")


if __name__ == "__main__":
    main()
