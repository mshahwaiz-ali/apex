# Validation, Testing, and Operations

## Quality gate

Before considering a batch complete, run:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate

.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
git status
```

Use safe Ruff fixes before verification when files changed:

```bash
.venv/bin/ruff format <files>
.venv/bin/ruff check <files> --fix
```

Never report a clean gate without the actual command output.

## Test strategy

### Unit tests

Cover domain invariants, data validation, indicators, structure, liquidity, strategy conditions, scoring, risk, sizing, leverage, lifecycle, configuration, and serialization.

### Integration tests

Cover provider adapters, cache behavior, multi-timeframe orchestration, scanner isolation, storage, CLI commands, backtesting pipelines, paper state, and readiness artifacts.

### Regression tests

Every defect fix should preserve a focused test reproducing the original failure.

### Scenario fixtures

Maintain representative scenarios such as trend pullbacks, ranges, sweeps, traps, genuine and false breakouts, compression, extreme volatility, stale or missing data, and flat markets.

## Core invariants

- Candle high cannot be below candle low.
- Long stops must be below entry; short stops must be above entry.
- Targets must be directionally valid.
- Position risk cannot exceed configured limits.
- Isolated liquidation must remain beyond structural invalidation by the required buffer.
- No serialized result may contain NaN or infinite values.
- One failed symbol or strategy must not crash an unrelated scanner result.
- Readiness evidence must never imply execution authorization.

## Performance evaluation

Do not optimize for win rate alone. Evaluate:

- Expectancy
- Profit factor
- Maximum drawdown
- Average win and loss
- Tail losses
- Liquidation rate
- Fee and slippage sensitivity
- Stability across symbols, regimes, score bands, and time periods
- Opportunity frequency and holding time

Historical development, validation, and out-of-sample periods must remain separated. Use walk-forward testing for later calibration.

## Validation gates

### Technical correctness

Formatting, linting, strict typing, tests, deterministic outputs, and stable data retrieval are clean.

### Historical viability

Adequate sample size, positive modeled expectancy, acceptable drawdown, multiple-symbol support, and no lookahead leakage.

### Out-of-sample viability

Performance remains stable on unseen periods without score-band or regime collapse.

### Forward paper viability

Live paper behavior broadly matches modeled assumptions after realistic fees, slippage, timing, and lifecycle effects.

### Funded readiness

Requires verified provider limits, a compatible provider-policy binding, completed forward-validation evidence, standard risk mode, approved funded policy, lockout and buffer verification, complete checklists, and enabled kill switch.

### Execution readiness

Requires testnet validation of precision, isolated margin, reduce-only behavior, duplicate prevention, reconciliation, maximum-loss controls, and kill switches.

## Operational safety

- Keep API keys out of Git and logs.
- Separate public-data and trading credentials.
- Use least privilege and read-only credentials where possible.
- Keep execution disabled by default.
- Preserve analysis IDs, configuration hashes, timestamps, and source references for auditability.
- Treat GitHub file writes as unsafe until the complete file is refetched and verified.
