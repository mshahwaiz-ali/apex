#!/usr/bin/env python3
"""Align reclaim state and recovery authorization semantics."""

from __future__ import annotations

from pathlib import Path


PATH = Path("src/apex/domain/sweep_reclaim.py")

OLD_STATE = """    elif not structure_confirmed:
        rejected_reason = "reclaim_not_held_or_retested"
        state = SweepReclaimState.RECLAIM_CONFIRMED
    else:
        rejected_reason = "none"
        state = SweepReclaimState.RETEST_CONFIRMED
"""

NEW_STATE = """    elif retest_held:
        rejected_reason = "none"
        state = SweepReclaimState.RETEST_CONFIRMED
    elif structure_confirmed:
        rejected_reason = "none"
        state = SweepReclaimState.RECLAIM_CONFIRMED
    else:
        rejected_reason = "reclaim_not_held_or_retested"
        state = SweepReclaimState.RECLAIM_CONFIRMED
"""

OLD_AUTHORITY = """    def recovery_entry_authorized(self) -> bool:
        return self.reclaim_confirmed and self.structure_confirmed and not self.deep_failure
"""

NEW_AUTHORITY = """    def recovery_entry_authorized(self) -> bool:
        return self.reclaim_confirmed and self.retest_held and not self.deep_failure
"""


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    changed = False

    if OLD_STATE in text:
        text = text.replace(OLD_STATE, NEW_STATE, 1)
        changed = True
    elif NEW_STATE not in text:
        raise SystemExit("expected sweep/reclaim state block not found")

    if OLD_AUTHORITY in text:
        text = text.replace(OLD_AUTHORITY, NEW_AUTHORITY, 1)
        changed = True
    elif NEW_AUTHORITY not in text:
        raise SystemExit("expected recovery authorization block not found")

    if changed:
        PATH.write_text(text, encoding="utf-8")
        print(f"updated {PATH}")
    else:
        print(f"already updated {PATH}")


if __name__ == "__main__":
    main()
