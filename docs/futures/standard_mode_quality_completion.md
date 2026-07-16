# N3 Futures Standard-Mode Quality Pass

## Implementation status

The N3 implementation is complete in code and awaits the single end-of-phase local quality gate.

Implemented behavior:

- canonical strategy-specific thresholds for all registered futures strategies;
- `STANDARD`, `AGGRESSIVE`, and `EXTREME` threshold selection;
- preferred, controlled, and restricted strategy quality classes;
- stable strategy approval, quality-gate, and eligibility reason codes;
- breakout-retest threshold differentiation;
- stricter direct-breakout extension, volume, and target-space rules;
- stricter momentum and gainer continuation rules;
- provisional gainer rejection in `STANDARD` mode;
- setup eligibility routing to `FUNDED_ELIGIBLE`, `PAPER_ONLY`,
  `EXPERIMENTAL_ONLY`, or `REJECTED`;
- account-policy lockout precedence;
- strategy approval and eligibility serialization in public futures plans;
- N3 quality gating enabled by default in central Phase 5 orchestration with
  `STANDARD` as the default risk mode;
- explicit `AGGRESSIVE` and `EXTREME` orchestration support;
- explicit research opt-out through `apply_strategy_quality=False`;
- focused configuration, decision, quality-gate, futures-plan, and orchestration tests.

The earlier note in `docs/implementation_progress.md` stating that the central Phase 5 hook remains is superseded by this file. The central `analyze_phase5()` path now applies the N3 quality gate by default.

## Validation still required

Run locally from the repository root:

```bash
ruff format .
ruff check .
mypy src
pytest
```

Repair every finding before marking N3 quality-gate complete or beginning S1.

No profitability, funded-readiness, or production-eligibility claim is made by this implementation.
