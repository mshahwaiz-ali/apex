# Historical Futures Shared-Wallet Command

## Purpose

`apex dataset historical-futures-backtest` replays verified historical futures signal records through the canonical deterministic trade simulator and then admits simulated opportunities onto one chronological shared account wallet.

This command is research-only. It does not establish historical edge, funded-account eligibility, production readiness, exchange-execution readiness, or real-money safety.

## Required artifacts

The command requires all of the following verified inputs:

- an aligned historical dataset campaign plan;
- the completed aligned dataset execution manifest;
- historical signal JSONL records;
- the matching historical signal execution manifest;
- distinct result and execution-manifest output paths.

Example:

```bash
apex dataset historical-futures-backtest \
  --campaign-id campaign-1 \
  --plan data/campaign/plan.json \
  --dataset-execution-manifest data/campaign/execution.json \
  --signal-records data/signals/records.jsonl \
  --signal-execution-manifest data/signals/execution.json \
  --result-output data/backtests/shared-result.json \
  --execution-manifest-output data/backtests/shared-execution.json \
  --starting-equity 10000 \
  --fee-pct 0.04 \
  --slippage-pct 0.02 \
  --maximum-holding-candles 48 \
  --maximum-concurrent-positions 3 \
  --maximum-wallet-exposure-pct 50 \
  --daily-loss-limit-pct 10 \
  --consecutive-loss-limit 4
```

Use either `--conservative-intrabar` or `--optimistic-intrabar` to select the configured same-candle stop/target ordering. Conservative behavior remains the default.

## Account-level replay behavior

Accepted historical plans are ordered deterministically by signal time, symbol, and candidate ID. Positions due to close are settled before later admission decisions.

The shared wallet tracks:

- realized equity and fees;
- reserved and available margin;
- peak equity and maximum drawdown;
- concurrent open positions;
- same-symbol overlap;
- total wallet exposure;
- daily realized loss;
- consecutive realized losses.

A wallet-rejected opportunity remains present in observations with:

```text
status = wallet_rejected
```

Stable account-level rejection codes include:

```text
campaign_paused
maximum_concurrent_positions
daily_loss_limit
overlapping_symbol_position
maximum_wallet_exposure
insufficient_available_margin
consecutive_loss_lockout
```

Wallet-rejected candidates do not contribute trades, fees, PnL, split trade metrics, or wallet equity.

## Required-margin evidence

Required margin must already exist in the serialized historical signal analysis under `position_size` using one of these aliases:

```text
required_margin
margin_required
margin
```

Apex does not infer missing margin from quantity, notional, leverage, wallet size, stop distance, or default leverage. Missing or invalid margin produces:

```text
historical_required_margin_missing
```

## Output integrity

The result includes the shared-wallet configuration, configuration hash, starting and ending equity, peak equity, maximum drawdown, realized PnL, total fees, rejection counts, and equity curve.

The execution manifest binds the result to:

- signal-record hash;
- signal-configuration hash;
- result hash;
- decision and accepted-trade counts;
- split counts;
- wallet-configuration hash;
- wallet rejection counts.

Result and manifest files are written atomically, reload-verified, and never silently overwritten.

# Spot Research Commands

The spot product is separate from futures. It is long-only, cash-funded, deterministic, and contains no leverage, margin, borrowing, short, or liquidation assumptions. Both commands are research and paper-trading tools; neither fetches live spot data or places orders.

## `apex spot-plan`

`spot-plan` validates an already selected canonical spot candidate plus account and price geometry, then creates bounded scale-in entries, structural invalidation, position sizing, ordered targets, and an initial lifecycle snapshot.

```bash
apex spot-plan \
  --input path/to/spot-plan-input.json \
  --config config/spot.yaml \
  --output path/to/spot-plan-result.json
```

The input must provide the selected strategy candidate, cash account state, current price, support, resistance, deeper support, recovery entry, and optional correlated-sector exposure. The planner enforces allocation and account-loss limits and rejects unsafe geometry.

## `apex spot-analyze`

`spot-analyze` evaluates all six configured spot strategy families, selects the first approved strategy in deterministic routing order, and builds a plan only when a candidate is approved.

```bash
apex spot-analyze \
  --input tests/fixtures/spot/approved_trend_pullback.json \
  --config config/spot.yaml \
  --strategy-config config/spot_strategies.yaml \
  --output data/spot-analysis.json
```

`--config` and `--strategy-config` default to the paths shown above. Standard output is stable, sorted JSON. `--output` writes the same canonical payload with a trailing newline.

The input object contains:

- `strategy_input`: normalized market regime, structure state, price zones, and explicit measurable strategy evidence;
- `account`: cash spot balances and exposure;
- support, resistance, deeper-support, and recovery-entry geometry;
- optional correlated-sector exposure.

The output contains:

- schema version;
- selected strategy or `null`;
- all six candidate evaluations with evidence and rejection reasons;
- a bounded spot plan or `null`;
- research and paper-validation warnings.

Blocked regimes, terminal extension, incomplete required evidence, or invalid geometry do not fabricate a trade. They return watch/reject candidates and no plan.

## Canonical orchestration bridge

The provider-independent application bridge accepts canonical multi-timeframe structure and regime results plus explicit setup evidence. Its deterministic flow is:

```text
multi-timeframe snapshots
-> structure classification
-> market regime
-> normalized SpotStrategyInput
-> six-strategy routing
-> bounded spot plan when approved
```

Volume ratio, pullback depth, breakout confirmation, retest hold, accumulation confirmation, liquidity sweep, daily recovery, and capitulation recovery must be supplied when observed. Missing optional evidence remains missing or unconfirmed; Apex does not infer it from unrelated fields.

This bridge does not yet provide a live spot scanner, exchange provider integration, paper-trade persistence, universe scanning, optimization, or production execution.
