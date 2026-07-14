# P1 and R1 Operations

This document describes the implemented review commands for forward paper validation and funded-account readiness.

No command enables autonomous real-money execution. A passing report is evidence for the next manual review stage only.

## P1 daily forward-paper validation

Generate or review the canonical daily P1 report with the existing commands:

```bash
apex paper-validation-generate BACKTEST_REPORT.json
apex paper-validation-review INPUT.json
apex paper-validation-run BACKTEST_REPORT.json
```

Persist one date-keyed daily snapshot and current cumulative strategy counts:

```bash
apex paper-validation-daily P1_REPORT.json \
  --paper-store data/paper_trading/trades.json \
  --history data/validation/daily.json \
  --minimum-per-strategy 10
```

The daily report returns one eligibility state:

- `INSUFFICIENT_SAMPLE`
- `PAPER_ONLY`
- `READY_FOR_FUNDED_REVIEW`
- `REJECTED`

Critical lifecycle, risk-control, or manual-instruction failures produce `REJECTED`. A small sample produces `INSUFFICIENT_SAMPLE`. Non-critical performance deviations keep the result at `PAPER_ONLY`.

The paper-history evidence generator derives only closed count, win rate, realized-R expectancy, maximum drawdown, and lifecycle replay failures. Risk-control and manual-instruction failures remain explicit operator evidence.

## Aggregate P1 history review

Review accumulated daily history and write the schema-versioned aggregate report:

```bash
apex paper-validation-history-review \
  --history data/validation/daily.json \
  --report data/validation/history-review.json
```

Default aggregate checks cover:

- at least 10 distinct validation days;
- at least 30 cumulative closed samples;
- at least 10 cumulative samples for every observed strategy;
- at least 5 consecutive days without a `REJECTED` daily result;
- an 80% `READY_FOR_FUNDED_REVIEW` ratio among mature days, with the latest day ready;
- no excessive deterioration in win-rate deviation, expectancy deviation, or drawdown increase between the first and latest stored records.

Daily paper counts are cumulative snapshots. The aggregate evaluator therefore uses the latest count instead of summing daily counts and double-counting the same trades.

The report schema version is `1` and includes the decision, blocker codes, validation-day and sample counts, strategy shortfalls, failure-free streak, mature/ready day counts, ready-day ratio, and all three deterioration measurements.

## R1 funded-account readiness

The canonical history-backed review is:

```bash
apex funded-readiness-from-history data/reports/r1-evidence.json \
  --history-review data/validation/history-review.json \
  --output json \
  --report data/reports/funded-readiness.json
```

The R1 evidence document must include:

- date-stamped provider limits from a verified source;
- selected risk mode;
- account-policy type and current policy decision;
- daily-lockout and total-buffer verification flags;
- completed pre-trade and post-trade checklists;
- current kill-switch state.

Readiness is blocked unless:

- provider limits are explicitly verified;
- the aggregate P1 history report is ready for funded review;
- risk mode is exactly `STANDARD`;
- account policy type is `FUNDED`;
- the account-policy decision is approved;
- daily and total drawdown controls have been verified;
- both manual checklists are complete;
- the kill switch is enabled.

The earlier `funded-readiness-review` and `funded-readiness-from-report` commands remain registered for backward compatibility. They are legacy single-report paths and do not replace the aggregate-history gate for current R1 operations.

## Current scope limitations

These contracts do not prove P1 completion. Continuous futures paper operation, continuous spot paper operation, real accumulated forward samples, and the complete quality gate remain outstanding. Provider limits are never fetched or invented and must be supplied from a separately verified source. A passing report does not create exchange credentials, submit orders, or authorize autonomous execution.
