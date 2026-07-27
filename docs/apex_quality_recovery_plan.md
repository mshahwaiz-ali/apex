# Apex Quality Recovery Plan

This is the future-work roadmap, not the runtime methodology authority.

## Implemented foundation

1. Checksum-verified funding, aggregate-trade, mark/index/premium, and daily
   OI/ratio archive ingestion.
2. Immutable snapshot identity, closed-candle boundary enforcement, contract and
   precision validation, and explicit degraded/rejected quality.
3. Event-level holding-period funding with a separate manual stress override.
4. Explicit persistent regime history and chronological hysteresis.
5. Observe-only behavioral cohorts and market-profile metadata.
6. Strategy/timeframe/geometry shadow-matrix reporting.
7. Versioned experiment manifests, purged/embargoed expanding walk-forward
   folds, validation-only selection, and one untouched final holdout.
8. Reliability diagrams, Brier decomposition, bootstrap intervals, PBO
   availability rules, sensitivity, and exclusion tests.
9. Fail-closed balanced-edge promotion gates.

## Remaining empirical work

1. Capture point-in-time exchange-information history and any unavailable raw
   taker-flow archives; never substitute current metadata for historical truth.
2. Accumulate predeclared multi-symbol, multi-cohort, multi-timeframe canonical
   outcomes until the untouched executed-outcome minimum is met.
3. Complete every declared shadow-matrix cell and investigate losing cells
   without promoting them.
4. Assess probability calibration only after untouched executed outcomes carry
   genuine pre-outcome probabilities and binary labels.
5. Promote a candidate only if every gate in the validation specification
   passes. The July 2026 controlled campaign promoted nothing.

Each batch must preserve public commands, keep JSON changes additive, include a
rollback comparison, and leave failed candidates in research/shadow mode.
