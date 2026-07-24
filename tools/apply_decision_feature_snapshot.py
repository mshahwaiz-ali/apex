#!/usr/bin/env python3
"""Idempotently wire decision-time snapshots into backtest metadata."""

from __future__ import annotations

from pathlib import Path

PATH = Path("src/apex/backtesting/engine.py")
IMPORT_ANCHOR = "from apex.domain.models import Candle\n"
IMPORT_LINE = "from apex.domain.decision_features import decision_feature_snapshot\n"
METADATA_ANCHOR = "        **_thesis_outcome_metadata(signal, candles[:max_candles]),\n"
METADATA_LINE = "        **decision_feature_snapshot(signal),\n"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    if IMPORT_LINE not in text:
        if IMPORT_ANCHOR not in text:
            raise SystemExit("engine import anchor not found")
        text = text.replace(IMPORT_ANCHOR, IMPORT_LINE + IMPORT_ANCHOR, 1)

    if METADATA_LINE not in text:
        if METADATA_ANCHOR not in text:
            raise SystemExit("engine metadata anchor not found")
        text = text.replace(METADATA_ANCHOR, METADATA_ANCHOR + METADATA_LINE, 1)

    PATH.write_text(text, encoding="utf-8")
    print(f"patched {PATH}")


if __name__ == "__main__":
    main()
