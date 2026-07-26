# Apex Quality Recovery Plan

This is the remaining roadmap, not the runtime methodology authority.

1. Complete point-in-time historical funding, OI, taker-flow, mark/index, listing,
   and precision archives.
2. Validate snapshot parity and reject future/misaligned data after an
   observe-only rollout.
3. Apply funding events per position holding interval.
4. Persist regime history and evaluate hysteresis without hidden global state.
5. Promote behavioral cohorts only after symbol/cohort holdouts.
6. Run strategy/timeframe/geometry shadow matrices.
7. Evaluate parameter candidates with purged walk-forward folds.
8. Calibrate probabilities only on validation data and report untouched
   reliability.
9. Promote balanced-edge configurations only through the gates in the backtest
   validation specification.

Each batch must preserve public commands, keep JSON changes additive, include a
rollback comparison, and leave failed candidates in research/shadow mode.
