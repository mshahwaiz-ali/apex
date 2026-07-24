#!/usr/bin/env python3
"""Idempotently wire pre-entry deep-failure shadow metadata into backtests."""

from __future__ import annotations

from pathlib import Path


PATH = Path("src/apex/backtesting/engine.py")

IMPORT_ANCHOR = "from apex.domain.models import Candle\n"
IMPORT_BLOCK = (
    "from apex.domain.deep_failure_risk import deep_failure_shadow_metadata\n"
    "from apex.domain.models import Candle\n"
)

METADATA_ANCHOR = """    metadata = {
        **({} if metadata is None else dict(metadata)),
        **_thesis_outcome_metadata(signal, candles[:max_candles]),
"""
METADATA_BLOCK = """    metadata = {
        **({} if metadata is None else dict(metadata)),
        **deep_failure_shadow_metadata(signal),
        **_thesis_outcome_metadata(signal, candles[:max_candles]),
"""


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    changed = False

    if "from apex.domain.deep_failure_risk import deep_failure_shadow_metadata\n" not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("engine import anchor not found")
        text = text.replace(IMPORT_ANCHOR, IMPORT_BLOCK, 1)
        changed = True

    if "        **deep_failure_shadow_metadata(signal),\n" not in text:
        if METADATA_ANCHOR not in text:
            raise SystemExit("engine metadata anchor not found")
        text = text.replace(METADATA_ANCHOR, METADATA_BLOCK, 1)
        changed = True

    if changed:
        PATH.write_text(text, encoding="utf-8")
        print(f"updated {PATH}")
    else:
        print(f"already updated {PATH}")


if __name__ == "__main__":
    main()
