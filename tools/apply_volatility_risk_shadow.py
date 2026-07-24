#!/usr/bin/env python3
"""Idempotently wire volatility-aware shadow metadata into the backtest engine."""

from __future__ import annotations

from pathlib import Path

PATH = Path("src/apex/backtesting/engine.py")
IMPORT = "from apex.domain.volatility_risk import volatility_risk_shadow_metadata\n"
ANCHOR = "from apex.domain.models import Candle\n"
METADATA_ANCHOR = "        **decision_feature_snapshot(signal),\n"
METADATA_LINE = "        **volatility_risk_shadow_metadata(signal),\n"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    if IMPORT not in text:
        if ANCHOR not in text:
            raise SystemExit("engine import anchor not found")
        text = text.replace(ANCHOR, IMPORT + ANCHOR, 1)

    if METADATA_LINE not in text:
        if METADATA_ANCHOR not in text:
            raise SystemExit("engine metadata anchor not found")
        text = text.replace(METADATA_ANCHOR, METADATA_ANCHOR + METADATA_LINE, 1)

    PATH.write_text(text, encoding="utf-8")
    print(f"patched {PATH}")


if __name__ == "__main__":
    main()
