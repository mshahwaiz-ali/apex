# P1 and R1 Operations

This document describes the implemented review commands for forward paper validation and funded-account readiness.

Neither command enables autonomous real-money execution. A passing report is evidence for the next manual review stage only.

## P1 forward paper validation

Run:

```bash
apex paper-validation-review data/reports/p1-input.json \
  --output json \
  --report data/reports/p1-validation.json
```

The input document must contain:

```json
{
  "generated_at": "2026-07-14T12:00:00+00:00",
  "backtest": {
    "total_trades": 100,
    "win_rate": 0.6,
    "expectancy": 0.4,
    "maximum_drawdown": 10.0
  },
  "paper": {
    "closed_trades": 40,
    "win_rate": 0.58
  },
  "evidence": {
    "critical_lifecycle_failures": 0,
    "critical_risk_control_failures": 0,
    "manual_instruction_failures": 0,
    "paper_expectancy": 0.35,
    "paper_maximum_drawdown": 11.0
  },
  "thresholds": {
    "minimum_closed_trades": 30,
    "maximum_win_rate_deviation": 0.15,
    "maximum_expectancy_deviation": 0.5,
    "maximum_drawdown_increase": 0.25
  }
}
```

The report returns one eligibility state:

- `INSUFFICIENT_SAMPLE`
- `PAPER_ONLY`
- `READY_FOR_FUNDED_REVIEW`
- `REJECTED`

Critical lifecycle, risk-control, or manual-instruction failures produce `REJECTED`. A small sample produces `INSUFFICIENT_SAMPLE`. Non-critical performance deviations keep the result at `PAPER_ONLY`.

## R1 funded-account readiness

Run:

```bash
apex funded-readiness-review data/reports/r1-input.json \
  --output json \
  --report data/reports/funded-readiness.json
```

The input must include:

- date-stamped provider limits;
- a serialized P1 forward-validation report;
- selected risk mode;
- account-policy type and current policy decision;
- daily-lockout and total-buffer verification flags;
- completed pre-trade and post-trade checklists;
- current kill-switch state.

Readiness is blocked unless:

- provider limits are explicitly verified;
- P1 is `READY_FOR_FUNDED_REVIEW`;
- risk mode is `STANDARD`;
- account policy type is `FUNDED`;
- the account-policy decision is approved;
- daily and total drawdown controls have been verified;
- both manual checklists are complete;
- the kill switch is enabled.

A passing report does not create exchange credentials, submit orders, or authorize autonomous execution.

## Current scope limitations

The review commands consume explicit JSON evidence. They do not yet run a continuous paper daemon, calculate spot paper portfolio metrics automatically, or fetch funded-provider limits from external sources. Provider limits must be supplied from a separately verified source and marked verified deliberately.
