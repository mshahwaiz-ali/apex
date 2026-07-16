# S9 Historical Spot Replay and Backtest Completion

## Status

S9 is functionally complete and locally validated as of 2026-07-15.

This stage establishes deterministic historical spot replay and shared-wallet execution research. It does not claim profitability, funded-account eligibility, production readiness, or real-money safety.

## Completed scope

- Historical bid/ask spread unavailability is disclosed instead of converted into false spread rejection.
- Observed excessive spread remains ineligible and live eligibility remains strict.
- Replay support geometry uses canonical thesis semantics.
- Incompatible approved-strategy invalidation is rejected before planning.
- The real campaign replay produced 1,083 decisions, 1,083 eligibility passes, zero replay failures, zero approved plans, and no false `SPREAD_TOO_WIDE` decisions.
- The shared-wallet replay correctly preserved the valid zero-plan result with no fills or trades.
- Deterministic execution coverage includes a profitable final-target trade, a stop-loss trade, fees, slippage, chronological events, shared-wallet accounting, per-symbol metrics, and stable payload and manifest hashes.
- Full-runner edge coverage includes entry expiry, maximum-holding `TIME_EXIT`, conservative ambiguous-candle handling, open-position limits, total-exposure limits, and duplicate-symbol rejection.
- `apex dataset spot-history-backtest` persists deterministic result and manifest artifacts.
- Persisted artifacts are immediately reloaded and verified for result hash, provenance, summary counts, and ending equity before CLI success is reported.
- CLI-level non-zero execution persistence coverage is included.

## Recorded campaign hashes

Historical replay records:

```text
1163bcc7af39a788f11f91924af6e53221281784d7f6761036b3d379ba24062f
```

Real shared-wallet backtest result:

```text
19af5b17c3e0d742a88f386f456d4b8e4902efdef1328ee7107a86872da48d1b
```

## Validation evidence

Focused validation reported locally:

```text
Success: no issues found in 265 source files
11 tests passed
```

Complete repository validation reported locally:

```text
Success: no issues found in 265 source files
1176 passed in 5.30s
git diff --check: no output
working tree clean
branch main up to date with origin/main
```

## Boundary

S9 proves deterministic behavior, persistence integrity, chronological execution semantics, and test coverage. It does not prove positive expectancy. Empirical calibration, untouched final-test reporting, and stability analysis belong to S10.
