#!/usr/bin/env python3
"""Keep reclaim state distinct from structure authorization.

A reclaim may be structurally confirmed by the next candle holding above/below
entry without an actual retest. In that case recovery can remain authorized, but
the descriptive state must stay RECLAIM_CONFIRMED rather than RETEST_CONFIRMED.
"""

from __future__ import annotations

from pathlib import Path


PATH = Path("src/apex/domain/sweep_reclaim.py")
OLD = '''    elif not structure_confirmed:\n        rejected_reason = "reclaim_not_held_or_retested"\n        state = SweepReclaimState.RECLAIM_CONFIRMED\n    else:\n        rejected_reason = "none"\n        state = SweepReclaimState.RETEST_CONFIRMED\n'''
NEW = '''    elif retest_held:\n        rejected_reason = "none"\n        state = SweepReclaimState.RETEST_CONFIRMED\n    elif structure_confirmed:\n        rejected_reason = "none"\n        state = SweepReclaimState.RECLAIM_CONFIRMED\n    else:\n        rejected_reason = "reclaim_not_held_or_retested"\n        state = SweepReclaimState.RECLAIM_CONFIRMED\n'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if NEW in text:
        print(f"already updated {PATH}")
        return
    if OLD not in text:
        raise SystemExit("expected sweep/reclaim state block not found")
    PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"updated {PATH}")


if __name__ == "__main__":
    main()
