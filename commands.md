# Apex CLI Command Guide

This file is the practical user guide for the Apex command-line interface.

Apex is organized by workflow. New usage should prefer the grouped commands shown here. Older flat command names remain available as hidden compatibility aliases for existing scripts.

> Apex performs analysis, research, paper trading, validation, and guarded local/testnet-oriented simulation. It does not authorize real-money execution.

## 1. Start here

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate
apex --help
```

Main workflow groups:

| Group | Purpose |
| --- | --- |
| `apex futures` | Find and analyze leveraged futures opportunities. |
| `apex spot` | Find and analyze long-only spot opportunities. |
| `apex paper` | Record, update, and review simulated trades. |
| `apex research` | Run datasets, backtests, comparisons, and edge reports. |
| `apex validation` | Review forward evidence and readiness gates. |
| `apex system` | Check installation, configuration, and public market data. |
| `apex execute` | Use guarded local/testnet simulation and safety controls. |

Use help at any level:

```bash
apex futures --help
apex futures scan --help
apex paper --help
apex research --help
```

## 2. Symbol format

Most commands accept either compact or slashed symbols:

```text
BTCUSDT
BTC/USDT
ethusdt
ETH/USDT
```

Apex normalizes supported symbols to canonical uppercase `BASE/QUOTE` form. For unusual markets, prefer explicit `BASE/QUOTE` notation.

## 3. Futures trade discovery

### Scan the futures universe

```bash
apex futures scan
```

What it does:

- loads the configured symbol universe;
- fetches closed multi-timeframe candles;
- runs normal-market and/or gainer analysis;
- applies strategy routing, scoring, precision-entry, and risk rules;
- ranks valid opportunities and explains rejected candidates.

Useful examples:

```bash
apex futures scan --mode normal
apex futures scan --mode gainers
apex futures scan --mode all --candles 200
apex futures scan --output json
apex futures scan --report data/reports/latest_scan.json
```

Scanner modes:

| Mode | Behavior |
| --- | --- |
| `normal` | Standard market scanner; compatibility default. |
| `gainers` | Fast-mover/gainer-specific analysis path. |
| `all` | Runs normal and gainer paths independently. |

### Analyze one futures symbol

```bash
apex futures analyze BTCUSDT
```

What it does:

- analyzes one symbol in depth;
- evaluates structure, momentum, volume, volatility, liquidity, and timeframe alignment;
- returns a trade, wait state, invalidation, or structured rejection;
- builds entry, stop, targets, leverage-aware position geometry, and management guidance when approved.

Useful examples:

```bash
apex futures analyze BTCUSDT --candles 200
apex futures analyze BTCUSDT --output json
apex futures analyze BTCUSDT --report data/reports/btc_analysis.json
apex futures analyze BTCUSDT --record data/reports/analysis.jsonl
apex futures analyze BTCUSDT --record-db data/reports/analysis.db
```

### Simulate the current approved setup

```bash
apex futures simulate BTCUSDT
```

This analyzes the current market first and simulates only an approved setup. It returns a no-simulation result when no setup is approved; it does not manufacture trades.

```bash
apex futures simulate BTCUSDT --candles 240 --replay-timeframe 5m
apex futures simulate BTCUSDT --output json
```

## 4. Spot trade discovery

Spot commands are long-only. They do not use leverage, borrowing, margin, or short selling.

### Scan spot markets

```bash
apex spot scan --help
```

Scans selected live spot markets and ranks eligible opportunities.

### Analyze one spot symbol

```bash
apex spot analyze BTCUSDT --help
```

Runs deterministic spot analysis and returns the selected long-only plan or rejection reason.

### Run the complete live spot workflow

```bash
apex spot live BTCUSDT --help
```

Fetches live market data and executes the complete spot analysis workflow.

### Build a bounded spot plan

```bash
apex spot plan --help
apex spot orchestrate --help
```

These commands build bounded entry, allocation, target, exit, and account-limit plans from validated spot structure.

## 5. Paper trading

Paper commands store and update simulated positions locally. They never place exchange orders.

### Record an approved setup

```bash
apex paper record BTCUSDT
apex paper record BTCUSDT --candles 200
```

Stores the original analysis, futures-plan snapshot, and replayable lifecycle state.

### Update open paper trades

```bash
apex paper update
apex paper update BTCUSDT
apex paper update BTCUSDT --timeframe 5m --candles 80
```

Fetches fresh candles and applies entry, target, partial-close, stop, invalidation, and expiry rules.

### Show paper performance

```bash
apex paper report
apex paper report --output json
```

### Replay the paper audit history

```bash
apex paper replay-report --report data/reports/paper_replay.json
```

Default local store:

```text
data/paper_trading/trades.json
```

## 6. Research and backtesting

### Export a reproducible dataset

```bash
apex research export BTCUSDT \
  --timeframes 1m,3m,5m,15m,30m,1h,4h \
  --candles 500 \
  --output data/btc_usdt_dataset.json
```

Exports normalized, fully closed candles into deterministic JSON. Existing output files are protected unless `--force` is supplied.

### Run a chronological backtest

```bash
apex research backtest BTCUSDT \
  --dataset data/btc_usdt_dataset.json \
  --replay-timeframe 5m \
  --analysis-candles 200 \
  --decision-interval 1 \
  --candidate-cooldown 3 \
  --report-output reports/btc_baseline.json
```

This replays the production pipeline in time order without future leakage and models entries, stops, targets, partial exits, fees, slippage, and expiry.

Without `--dataset`, Apex can fetch historical candles from the configured provider:

```bash
apex research backtest BTCUSDT --history-candles 500 --replay-timeframe 5m
```

### Run a campaign

```bash
apex research campaign BTCUSDT \
  --dataset data/btc_usdt_dataset.json \
  --report-output reports/btc_campaign.json
```

Campaigns run reproducible variants and rank their results. Use `--variants` for controlled experiments.

### Compare two reports

```bash
apex research compare \
  reports/btc_baseline.json \
  reports/btc_baseline_repeat.json
```

Checks dataset/config identity and reports metric drift.

### Historical edge reports

```bash
apex research edge-report --help
apex research edge-validate --help
```

These summarize performance by split and setup segment, then test stability on untouched data.

## 7. Validation and readiness

```bash
apex validation forward-edge --help
apex validation inspect-evidence --help
apex validation build-evidence --help
apex validation review --help
apex validation daily --help
apex validation history --help
apex validation funded-readiness --help
```

Purpose:

- evaluate completed paper trades;
- build reproducible evidence bundles;
- compare live paper behavior with historical expectations;
- review accumulated validation history;
- report readiness blockers for manual review.

A readiness result is evidence, not execution authorization.

## 8. System and market data

### Version and startup checks

```bash
apex system version
apex system check
```

### Validate resolved configuration

```bash
apex system config
apex system config --config-dir path/to/config
```

### Fetch public candles

```bash
apex system candles BTCUSDT
apex system candles BTCUSDT --timeframe 5m --limit 200
```

### Fetch the latest ticker

```bash
apex system ticker BTCUSDT
```

These commands use public market data and never place orders.

## 9. Execution safety tools

The execution group is restricted to guarded local/testnet-oriented simulation and audit tooling.

```bash
apex execute preview BTCUSDT
apex execute testnet BTCUSDT --confirm
apex execute status
apex execute reconcile --help
apex execute readiness --help
apex execute kill-switch enable
```

Important boundaries:

- no funded-account authorization;
- no silent fallback from production to testnet;
- explicit confirmation is required for simulated submission;
- kill-switch, duplicate protection, audit, and reconciliation remain mandatory.

## 10. Common output and file options

| Option | Purpose |
| --- | --- |
| `--output text` | Human-readable terminal output. |
| `--output json` | Machine-readable JSON output. |
| `--report PATH` | Write a complete JSON report while retaining terminal output. |
| `--record PATH` | Append an analysis record to JSONL. |
| `--record-db PATH` | Store or index records in SQLite. |
| `--candles N` | Control fetched analysis history where supported. |
| `--force` | Deliberately replace a protected output file where supported. |

Always run the command's own help to confirm its exact options:

```bash
apex COMMAND --help
apex GROUP COMMAND --help
```

## 11. Advanced compatibility commands

The legacy flat names and internal groups remain callable for scripts and specialist workflows, but they are hidden from normal top-level help.

Examples:

```text
apex scan                    -> apex futures scan
apex analyze BTCUSDT         -> apex futures analyze BTCUSDT
apex simulate-current-setup  -> apex futures simulate
apex spot-scan-live          -> apex spot scan
apex chronological-backtest  -> apex research backtest
apex compare-backtests       -> apex research compare
apex validate-config         -> apex system config
apex smoke                   -> apex system check
```

Advanced hidden groups include `dataset`, `optimize`, and `intelligence`. Use them only when a documented research workflow specifically requires them.

## 12. Troubleshooting

### Command not found

```bash
source .venv/bin/activate
python -m pip install -e "[dev]"
apex --help
```

If editable installation already exists, reinstall with:

```bash
python -m pip install -e ".[dev]"
```

### Invalid symbol

Use explicit format:

```text
BTC/USDT
```

### Configuration error

```bash
apex system config
```

Read the reported file and field, correct the YAML, and rerun the command.

### Market-data failure

Check connectivity and provider behavior with:

```bash
apex system ticker BTCUSDT
apex system candles BTCUSDT --timeframe 5m --limit 10
```

### No trade returned

`NO_TRADE`, wait states, invalidation, or rejection are valid analytical results. Use JSON output to inspect detailed reasons:

```bash
apex futures analyze BTCUSDT --output json
```

## 13. Development validation

Before claiming a code change is complete:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate

.venv/bin/ruff format <files>
.venv/bin/ruff check <files> --fix
.venv/bin/ruff check <files>
.venv/bin/mypy src/apex
.venv/bin/pytest -q
```

Automatic fixes must be followed by the non-mutating checks. Do not claim Ruff, mypy, or pytest passed without their actual terminal output.

## 14. Recommended operating sequence

For normal futures use:

```text
system check
-> futures scan
-> futures analyze selected symbol
-> paper record
-> paper update
-> paper report
-> validation review
```

For research:

```text
export dataset
-> run baseline backtest
-> repeat baseline
-> compare reports
-> change one variable group
-> run candidate backtest
-> compare candidate with baseline
-> validate out of sample
```

Generated datasets, reports, paper state, optimization output, and execution audit files should remain local unless intentionally committed.