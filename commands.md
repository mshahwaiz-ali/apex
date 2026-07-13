# Apex Command Guide

This file documents the commands currently registered by the Apex CLI.

## 1. Setup and environment

Enter the local repository:

```bash
cd ~/data_drive/apex
```

Activate the existing virtual environment when required:

```bash
source .venv/bin/activate
```

Create it first if it does not exist:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Apex with development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Verify the installed CLI:

```bash
apex --help
apex version
```

Validate the default configuration directory:

```bash
apex validate-config
```

Validate another configuration directory:

```bash
apex validate-config --config-dir path/to/config
```

Run the lightweight application bootstrap check:

```bash
apex smoke
```

## 2. Symbol format

Commands that accept manual market symbols normalize them to canonical `BASE/QUOTE` form.

Valid examples:

```text
BTCUSDT
BTC/USDT
ethusdt
ETH/USDT
```

These all normalize to an uppercase slashed symbol such as `BTC/USDT`.

Compact symbols must end in one configured quote asset. For unusual or ambiguous markets, use explicit `BASE/QUOTE` form.

## 3. Public market data

Fetch closed OHLCV candles:

```bash
apex fetch BTCUSDT
```

Choose a timeframe and candle count:

```bash
apex fetch BTCUSDT --timeframe 5m --limit 200
```

Short options are also available:

```bash
apex fetch BTCUSDT -t 15m -l 50
```

Fetch the current ticker:

```bash
apex ticker BTCUSDT
```

## 4. Single-symbol analysis

Run complete deterministic analysis with text output:

```bash
apex analyze BTCUSDT
```

Request JSON output:

```bash
apex analyze BTCUSDT --output json
```

Use a specific analysis history length:

```bash
apex analyze BTCUSDT --candles 200
```

The current `analyze` command supports `text` and `json` terminal output. It does not currently expose a report-file option.

## 5. Market scanner

Scan the default symbol universe from `config/symbols.yaml`:

```bash
apex scan
```

Use a different symbol file:

```bash
apex scan --symbols-file config/symbols.yaml
```

Request JSON terminal output:

```bash
apex scan --output json
```

Write the complete JSON scan payload to a file while retaining terminal output:

```bash
apex scan \
  --output text \
  --report data/reports/latest_scan.json
```

Use a specific candle history length per symbol:

```bash
apex scan --candles 200
```

## 6. Historical dataset export

Verified baseline export:

```bash
apex export-dataset BTCUSDT \
  --timeframes 1m,3m,5m,15m,30m,1h,4h \
  --candles 500 \
  --output data/btc_usdt_baseline_full.json
```

The exporter:

- normalizes the market symbol;
- fetches each requested timeframe from the configured provider;
- includes only fully closed candles;
- creates parent directories when needed;
- writes deterministic, schema-versioned UTF-8 JSON;
- refuses to replace an existing output file by default.

Replace an existing dataset deliberately:

```bash
apex export-dataset BTCUSDT \
  --timeframes 1m,3m,5m,15m,30m,1h,4h \
  --candles 500 \
  --output data/btc_usdt_baseline_full.json \
  --force
```

The current exporter writes JSON only. CSV is accepted as an input format by chronological backtesting when a compatible historical dataset already exists, but `export-dataset` does not currently create CSV files.

## 7. Current setup simulation

Simulate the currently approved live setup over fetched replay candles:

```bash
apex simulate-current-setup BTCUSDT
```

Request JSON output:

```bash
apex simulate-current-setup BTCUSDT --output json
```

Choose the analysis candle count and replay timeframe:

```bash
apex simulate-current-setup BTCUSDT \
  --candles 240 \
  --replay-timeframe 5m
```

This command analyzes the current market first. When no setup is approved, it returns a no-simulation result rather than manufacturing a trade.

The former generic command name `backtest` is not part of the active CLI. Use `simulate-current-setup` for this behavior.

## 8. Chronological backtesting

Verified dataset-backed baseline:

```bash
apex chronological-backtest BTCUSDT \
  --dataset data/btc_usdt_baseline_full.json \
  --replay-timeframe 5m \
  --analysis-candles 200 \
  --decision-interval 1 \
  --candidate-cooldown 3 \
  --report-output reports/btc_baseline.json
```

### Dataset mode

Use `--dataset` to replay a local JSON or CSV historical candle dataset:

```bash
apex chronological-backtest BTCUSDT \
  --dataset data/btc_usdt_baseline_full.json
```

The loader verifies the expected symbol and required timeframes.

### Live-provider history mode

When `--dataset` is omitted, Apex fetches historical candles from the configured live provider:

```bash
apex chronological-backtest BTCUSDT \
  --history-candles 500 \
  --replay-timeframe 5m
```

This is still a historical simulation. It does not place orders.

### Important options

`--analysis-candles` controls the rolling analysis window. The production warm-up contract is 200 closed candles, so the established baseline uses:

```bash
--analysis-candles 200
```

`--decision-interval` controls how many replay candles elapse between fresh decisions:

```bash
--decision-interval 1
```

`--candidate-cooldown` prevents immediate repeated consideration of the same candidate after it appears:

```bash
--candidate-cooldown 3
```

`--history-candles` applies only when Apex fetches history from the provider rather than loading `--dataset`.

`--report-output` writes the complete JSON report:

```bash
--report-output reports/btc_baseline.json
```

Existing reports are protected. Replace one deliberately with:

```bash
--force
```

The command also prints the complete JSON report to standard output.

## 9. Reproducibility comparison

Compare two saved chronological reports:

```bash
apex compare-backtests \
  reports/btc_baseline.json \
  reports/btc_baseline_repeat.json
```

The comparison checks run identity and aggregate results, including:

- dataset hash equality;
- configuration hash equality;
- selected metric values from both reports;
- metric deltas, including `trade_count` derived from report field `total_trades`.

Matching dataset and configuration hashes establish that both reports used the same historical input and deterministic configuration. Zero metric deltas then confirm equal selected outcomes.

## 10. Paper trading

Analyze a symbol and record an approved setup locally:

```bash
apex paper record BTCUSDT
```

Choose the analysis history length:

```bash
apex paper record BTCUSDT --candles 200
```

Update all open paper trades with fresh candles:

```bash
apex paper update
```

Update only one normalized symbol:

```bash
apex paper update BTCUSDT
```

Choose the update timeframe and candle count:

```bash
apex paper update BTCUSDT \
  --timeframe 5m \
  --candles 80
```

Show paper-trading performance:

```bash
apex paper report
```

Request JSON output:

```bash
apex paper report --output json
```

Paper trades are stored locally under the configured data directory, normally in:

```text
data/paper_trading/trades.json
```

## 11. Execution and testnet status

Apex does not currently submit real exchange orders. The registered execution commands provide guarded local testnet-simulation behavior only.

Preview an execution intent without submitting or recording an order:

```bash
apex execute preview BTCUSDT
```

Request JSON output:

```bash
apex execute preview BTCUSDT --output json
```

Record a local testnet simulation event after explicit confirmation:

```bash
apex execute testnet BTCUSDT --confirm
```

Without `--confirm`, execution remains disabled by configuration passed to the simulator.

Show execution safety status:

```bash
apex execute status
```

Enable the local execution kill switch:

```bash
apex execute kill-switch enable
```

Current execution status is accurately described as:

```text
local_testnet_simulation_only
```

Do not treat these commands as proof of exchange connectivity or real order execution.

## 12. Intelligence commands

Show optional deterministic intelligence configuration status:

```bash
apex intelligence summary
```

Request JSON output:

```bash
apex intelligence summary --output json
```

This command reports metadata such as funding, open-interest, and correlation feature flags. It does not independently change trade decisions.

## 13. Optimization commands

Evaluate one existing performance report without changing configuration:

```bash
apex optimize evaluate \
  --input path/to/performance_report.json
```

Request JSON output:

```bash
apex optimize evaluate \
  --input path/to/performance_report.json \
  --output json
```

Compare a baseline and candidate performance report:

```bash
apex optimize compare \
  --baseline path/to/baseline.json \
  --candidate path/to/candidate.json
```

Select the controlled optimization variable group when required:

```bash
apex optimize compare \
  --baseline path/to/baseline.json \
  --candidate path/to/candidate.json \
  --group scoring_thresholds
```

These framework commands write their latest result under:

```text
data/optimization/
```

They do not automatically rewrite strategy configuration.

## 14. Quality validation

Run non-mutating validation commands:

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

These commands verify tests, lint rules, formatting, and static typing without intentionally rewriting project files.

Run mutation commands separately when you deliberately want automatic changes:

```bash
ruff format .
ruff check --fix .
```

After automatic formatting or fixes, rerun the complete non-mutating validation set.

## 15. Practical baseline workflow

Use this controlled sequence for strategy development and calibration:

```text
export dataset
→ run baseline
→ repeat baseline
→ compare reports
→ make one controlled change
→ rerun quality checks
→ run candidate backtest
→ compare candidate against baseline
```

Concrete example:

```bash
apex export-dataset BTCUSDT \
  --timeframes 1m,3m,5m,15m,30m,1h,4h \
  --candles 500 \
  --output data/btc_usdt_baseline_full.json

apex chronological-backtest BTCUSDT \
  --dataset data/btc_usdt_baseline_full.json \
  --replay-timeframe 5m \
  --analysis-candles 200 \
  --decision-interval 1 \
  --candidate-cooldown 3 \
  --report-output reports/btc_baseline.json

apex chronological-backtest BTCUSDT \
  --dataset data/btc_usdt_baseline_full.json \
  --replay-timeframe 5m \
  --analysis-candles 200 \
  --decision-interval 1 \
  --candidate-cooldown 3 \
  --report-output reports/btc_baseline_repeat.json

apex compare-backtests \
  reports/btc_baseline.json \
  reports/btc_baseline_repeat.json

pytest
ruff check .
ruff format --check .
mypy src
```

Do not alter production indicator periods or trading thresholds merely to produce trades. A valid zero-trade baseline remains useful when it is deterministic and failure-free.

## 16. Generated paths

### `data/`

The configured runtime data directory stores generated datasets and local subsystem state, including examples such as:

```text
data/btc_usdt_baseline_full.json
data/paper_trading/trades.json
data/optimization/latest-evaluate.json
data/optimization/latest-compare.json
```

### `reports/`

The top-level `reports/` directory is suitable for chronological backtest outputs:

```text
reports/btc_baseline.json
reports/btc_baseline_repeat.json
```

The repository `.gitignore` excludes:

```text
/reports/
```

These generated reports therefore remain local unless intentionally moved or tracked elsewhere.

## 17. Discovering command help

Use Typer help at any command level to confirm the installed interface:

```bash
apex --help
apex analyze --help
apex scan --help
apex export-dataset --help
apex simulate-current-setup --help
apex chronological-backtest --help
apex compare-backtests --help
apex paper --help
apex execute --help
apex optimize --help
apex intelligence --help
```
