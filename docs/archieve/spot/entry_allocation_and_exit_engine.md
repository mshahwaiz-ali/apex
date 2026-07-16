# S4 — Spot Entry, Allocation and Exit Engine

## Status

Implementation is present on `main`. The complete local quality gate remains pending.

## Implemented scope

S4 converts an approved S3 strategy candidate into a bounded, cash-funded spot plan containing:

- one-to-three preplanned long-only entry legs;
- fixed entry allocation percentages;
- maximum chase price;
- structural invalidation and protective stop;
- risk-based sizing;
- allocation-capped sizing;
- total portfolio exposure cap;
- correlated-sector exposure cap;
- maximum-position-count enforcement;
- minimum quote-asset reserve;
- validated target ladder with optional runner allocation;
- deterministic lifecycle events and replay.

## Sizing rule

The final capital allocation is the minimum of:

1. capital allowed by account-loss risk;
2. configured per-position allocation cap;
3. remaining total spot exposure;
4. remaining correlated-sector exposure;
5. cash remaining after the minimum quote reserve.

No leverage, margin, liquidation, or borrowed-asset calculation exists in the S4 path.

## Averaging boundary

Scale-ins are fixed before entry. The engine does not permit:

- adding extra legs after plan generation;
- exceeding the configured entry-leg count;
- increasing total capital outside the original cap;
- planning entries below structural invalidation;
- sizing candidates that are not approved by S3.

## Exit and lifecycle boundary

The configured target percentages must total 100 percent. The final configured target can operate as a higher-timeframe runner.

Lifecycle replay supports:

- entry fills;
- partial target fills;
- full closure;
- stop closure;
- expiry before entry;
- cancellation before entry;
- structural invalidation;
- duplicate-fill and terminal-state protection.

## Validation status

Focused tests were added under `tests/unit/application/test_spot_planning.py`.

The repository quality gate must pass before S4 is declared validated:

```bash
ruff format .
ruff check .
mypy src
pytest
```

## Deferred

S4 does not implement exchange execution, portfolio persistence, historical-edge calibration, spot backtesting, or forward paper-trading storage.
