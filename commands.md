# Apex Command Reference

Apex is a command-line analysis tool for Binance USDT perpetual-futures discovery, single-symbol analysis, chronological backtesting, and historical research preparation.

> Apex does not place orders, manage exchange accounts, recommend leverage, or guarantee profitable trades.

## Setup

From the repository root:

```bash
cd ~/data_drive/apex
source .venv/bin/activate
```

Confirm the CLI is installed:

```bash
apex --help
```

## Public command tree

```text
apex
├── scan
├── analyze SYMBOL
├── backtest SYMBOL
├── research
│   └── campaign
├── config-check
└── version
```

| Command | Use it for |
|---|---|
| `apex scan` | Discover and rank opportunities across the Binance USDT perpetual universe. |
| `apex analyze SYMBOL` | Run the full shared analysis pipeline for one symbol. |
| `apex backtest SYMBOL` | Replay historical decisions for one symbol using chronological data. |
| `apex research campaign` | Prepare, verify, report, or optionally train on historical public datasets. |
| `apex config-check` | Validate and display the resolved Apex configuration. |
| `apex version` | Display the installed Apex version. |

---

## `apex scan`

### Purpose

`scan` discovers active Binance USDT perpetual markets, applies hard tradability filters, creates a shortlist, and runs the same canonical analysis engine used by `analyze`.

It can return:

- executable opportunities near CMP;
- confirmation-based opportunities;
- nearby entries;
- developing or follow-up opportunities;
- no-current-trade setup plans;
- compact per-symbol failures;
- complete structured JSON.

Apex may return fewer results than requested. It does not force trades to fill a quota.

### Basic usage

```bash
apex scan
```

### Useful examples

```bash
# Show the default market scan
apex scan

# Display fewer ranked opportunities
apex scan --results 5

# Analyze a wider shortlist but display only the best results
apex scan --shortlist 50 --results 10

# Display only long opportunities
apex scan --direction long

# Display only short opportunities
apex scan --direction short

# Display both directions
apex scan --direction both

# Include detailed methodology and evidence diagnostics
apex scan --explain

# Produce complete machine-readable output
apex scan --output json

# Save complete JSON using normal shell redirection
apex scan --output json > data/reports/latest_scan.json

# Increase closed-candle analysis depth
apex scan --candles 300

# Use a configured static symbol universe
apex scan --symbols-file config/symbols.yaml

# Load an alternate configuration directory
apex scan --config-dir config
```

### Options

| Option | Default | Description |
|---|---:|---|
| `--results INTEGER` | `20` | Maximum number of ranked opportunities displayed. |
| `--shortlist INTEGER` | `36` | Number of screened symbols sent to full analysis. |
| `--direction long\|short\|both` | `both` | Filters displayed direction only. It does not alter canonical analysis decisions. |
| `--candles INTEGER` | `200` | Closed-candle depth used by the analysis engine. |
| `--explain` | off | Appends methodology, evidence, contradiction, collision, calibration, and outcome-tracking diagnostics. |
| `--output`, `-o` | `text` | Selects `text` or complete `json` output. |
| `--symbols-file PATH` | live universe | Uses a configured static symbol list instead of market-wide discovery. |
| `--config-dir PATH` | `config` | Loads Apex YAML configuration from another directory. |

### Output groups

Normal text output is organized into:

1. Enter at CMP
2. Confirmation Entry
3. Nearby Entry
4. Developing / Follow-up
5. No Current Trade — Setup Plans
6. Failures, when present

Opportunity headers show `LONG` in green and `SHORT` in red on color-capable terminals. Cards
show CMP, ideal entry, entry range, maximum chase, stop-loss, and every available target up to
TP3; JSON retains the complete strategy, state, methodology, and diagnostic contracts.

Counts distinguish attempted, successfully analyzed, failed, displayed, and retained-opportunity
totals. A per-symbol data failure does not stop the rest of the scan.

In JSON, `portfolio_decision` distinguishes execution from monitoring:

- `actionable_at_cmp` means at least one current opportunity actually authorizes execution;
- `confirmation_at_cmp` means price is at the setup area but its required confirmation is incomplete;
- `nearby_setup_available` means measurable geometry exists away from CMP;
- `follow_up_available`, `runner_management`, and `no_valid_setup` describe the remaining portfolio states.

Use `execution_ready`, not opportunity count alone, when deciding whether an order may be placed.
Scan schema version 5 introduces the `confirmation_at_cmp` decision value.

### Outcome tracking

When `outcome_tracking_enabled` is enabled, scan automatically:

- records canonical portfolio opportunities;
- uses the configured SQLite path;
- deduplicates stable opportunity IDs;
- reconciles older pending opportunities;
- updates fills, outcomes, MFE, MAE, and expiry state.

There is no normal CLI flag for choosing a record database. Persistence remains configuration-driven.

---

## `apex analyze SYMBOL`

### Purpose

`analyze` bypasses universe discovery and sends one requested symbol directly into the same canonical multi-timeframe analysis pipeline used by `scan`.

The renderer consumes the complete `opportunity_portfolio`, not only legacy single-setup compatibility fields.

### Basic usage

```bash
apex analyze BTCUSDT
```

### Symbol format

Use the Binance perpetual symbol without a slash:

```text
BTCUSDT
ETHUSDT
SOLUSDT
```

### Useful examples

```bash
# Normal readable analysis
apex analyze BTCUSDT

# Full methodology and evidence explanation
apex analyze BTCUSDT --explain

# Complete structured authority
apex analyze BTCUSDT --output json

# Save the JSON analysis
apex analyze BTCUSDT --output json > data/reports/btc_analysis.json

# Increase analysis depth
apex analyze BTCUSDT --candles 300

# Use another configuration directory
apex analyze BTCUSDT --config-dir config
```

### Options

| Option | Default | Description |
|---|---:|---|
| `--candles INTEGER` | `200` | Closed-candle depth used by the shared analysis engine. |
| `--explain` | off | Appends methodology enforcement, evidence, contradictions, rationale, rejected candidates, calibration, and outcome-tracking detail. |
| `--output`, `-o` | `text` | Selects concise text or complete JSON. |
| `--config-dir PATH` | `config` | Loads settings from another Apex configuration directory. |

### Normal output structure

The text report may include:

1. Market Snapshot
2. Best Current Opportunity
3. Alternative Current Opportunity
4. Nearby Opportunity
5. Follow-up Opportunity
6. Developing Opportunity
7. Market Context
8. Risk and Invalidation

Empty optional sections disappear.

### Setup-plan rule

Every analyzed symbol receives a useful operator plan:

- executable setup;
- nearby or confirmation setup;
- developing or follow-up setup;
- no structurally valid setup yet.

Apex never fabricates entry, stop, or target geometry just to avoid an empty result.

### JSON output

Use JSON when you need the full structured record:

```bash
apex analyze BTCUSDT --output json
```

JSON remains the complete machine-readable authority for the canonical opportunity portfolio and diagnostics.

---

## `apex backtest SYMBOL`

### Purpose

`backtest` runs chronological historical decisions through the production analysis path.

It:

- loads historical closed candles;
- creates chronological decision points;
- blocks future candle access;
- forwards the configured methodology gate;
- reads canonical opportunity portfolios;
- simulates only execution-authorized current opportunities;
- replays pending activation plans separately without counting them as production trades;
- shadow-replays retained and geometry-rejected candidates for counterfactual evidence;
- preserves no-trade, missed-entry, invalidated, nearby, and developing decisions;
- models fees, slippage, optional funding, expiry, and conservative intrabar behavior;
- records complete trade and no-trade histories;
- reports MFE, MAE, targets, stops, partitions, fingerprints, and robustness statistics.

### Basic usage

```bash
apex backtest BTCUSDT
```

### Useful examples

```bash
# Default chronological replay
apex backtest BTCUSDT

# Complete structured output
apex backtest BTCUSDT --output json

# Save the complete structured backtest payload
apex backtest BTCUSDT --report-file data/reports/btc_backtest.json

# Use a 5-minute replay stream and a 24-candle holding window
apex backtest BTCUSDT --replay-timeframe 5m --replay-candles 24

# Run more chronological decision points
apex backtest BTCUSDT --decision-points 10

# Anchor comparable runs to the same historical cutoff
apex backtest BTCUSDT --as-of 2026-07-22T12:00:00Z

# Apply a labeled manual funding stress override
apex backtest BTCUSDT --funding-pct 0.01

# Apply verified historical funding events from a Binance monthly archive
apex backtest BTCUSDT \
  --funding-archive data/research/binance_um/fundingRate/BTCUSDT-fundingRate-2026-06.zip

# Increase historical analysis depth
apex backtest BTCUSDT --candles 400 --replay-candles 50

# Combine readable terminal output with a complete JSON report file
apex backtest BTCUSDT \
  --decision-points 10 \
  --report-file data/reports/btc_backtest.json
```

### Options

| Option | Default | Description |
|---|---:|---|
| `--candles INTEGER` | `240` | Historical prefix used to form chronological analysis windows. |
| `--replay-timeframe TIMEFRAME` | `5m` | Candle stream used for historical outcome replay. |
| `--replay-candles INTEGER` | `24` | Maximum replay candles retained after each decision. |
| `--decision-points INTEGER` | `5` | Number of non-overlapping chronological decisions. |
| `--funding-pct FLOAT` | `0.0` | Optional manual funding stress override, reported separately from history. |
| `--funding-archive FILE` | live history when available | Verified Binance monthly funding ZIP used for event-level holding-period costs. |
| `--as-of TIMESTAMP` | none | Anchors the latest visible candle to a timezone-aware ISO-8601 cutoff. |
| `--report-file PATH` | none | Writes the complete structured backtest payload to JSON. |
| `--output`, `-o` | `text` | Selects readable text or complete JSON. |
| `--config-dir PATH` | `config` | Loads another Apex configuration directory. |

### Text report sections

The backtest report includes:

1. Test Configuration
2. Performance Summary
3. Outcome Distribution
4. Risk and Excursion
5. Partition Performance
6. Trade Record
7. No-Trade Decisions
8. Conditional Replay (diagnostic only)
9. Candidate Shadow Replay (diagnostic only)
10. Robustness

### Important interpretation

Backtest output is historical research, not proof of future profitability.

Production, conditional, and shadow metrics are intentionally separate. Conditional and
shadow results diagnose activation, filtering, direction, and geometry; they must not be read as
execution-authorized portfolio performance.

### Standard anchored campaign (216 runs)

The bundled campaign runner evaluates 18 symbols across the 1m×20, 5m×24, and 15m×20 profiles
at four shared 24-hour-spaced anchors. It uses three parallel workers by default and writes an
isolated report, log, and campaign summary under `backtest-samples/anchored-216/`.

```bash
python3 tools/run_anchored_backtest_campaign.py
```

Use `--workers 1` for fully sequential execution or `--workers 4` when the provider and machine
can safely sustain more concurrent requests.

The command does not model:

- wallet allocation;
- leverage;
- required margin;
- liquidation;
- exchange account state;
- live order execution.

---

## `apex research campaign`

### Purpose

`research campaign` prepares and verifies a point-in-time historical public-data campaign.

It can:

- resolve a complete UTC month range;
- use or build a point-in-time symbol universe;
- download monthly klines, funding, aggregate trades, mark/index/premium
  lineages, and optional daily historical metrics;
- verify downloaded files;
- write a campaign manifest;
- report missing files and reasons;
- optionally train campaign models;
- write a versioned experiment manifest;
- evaluate canonical outcome files with purged walk-forward folds and an
  untouched final test;
- preserve a complete JSON report.

This command does not claim strategy profitability.

### Basic usage

```bash
apex research campaign
```

### Useful examples

```bash
# Inspect or prepare the default latest 24 complete UTC months
apex research campaign

# Build missing universe data and download missing archives
apex research campaign --download-missing

# Download point-in-time derivatives lineage and daily OI/ratio metrics
apex research campaign \
  --data-types fundingRate,markPriceKlines,indexPriceKlines,premiumIndexKlines \
  --include-daily-metrics \
  --download-missing

# Restrict the campaign to a month range
apex research campaign \
  --start 2025-01 \
  --end 2025-06 \
  --download-missing

# Use a specific dataset root
apex research campaign \
  --dataset-dir /mnt/research/apex-binance \
  --download-missing

# Use a saved point-in-time universe
apex research campaign \
  --symbols-file data/research/binance_um/universe_by_month.json

# Request model training
apex research campaign \
  --symbols-file data/research/binance_um/universe_by_month.json \
  --train-model

# Produce JSON terminal output
apex research campaign --output json

# Save the complete structured campaign payload
apex research campaign \
  --download-missing \
  --report-file data/research/campaign_report.json

# Evaluate predeclared outcome populations without changing runtime decisions
apex research campaign \
  --experiment-spec data/research/experiment.json \
  --outcomes-file data/research/outcomes.jsonl \
  --report-file data/research/evaluation_campaign.json
```

### Options

| Option | Default | Description |
|---|---:|---|
| `--start TEXT` | latest available range | Inclusive complete UTC month/date lower bound. |
| `--end TEXT` | latest complete month | Inclusive complete UTC month/date upper bound. |
| `--symbols-file FILE` | saved/dynamic universe | JSON symbol list or month-to-symbol mapping. |
| `--dataset-dir DIRECTORY` | `data/research/binance_um` | Dataset, universe, manifest, features, and model root. |
| `--download-missing` | off | Builds missing universe data and downloads missing verified archives. |
| `--train-model` | off | Requests campaign model training when required feature data exists. |
| `--data-types TEXT` | `klines,fundingRate,aggTrades` | Comma-separated monthly archive families. |
| `--include-daily-metrics` | off | Includes checksum-verified daily OI and ratio archives. |
| `--experiment-spec FILE` | generated default | Uses a predeclared versioned experiment manifest. |
| `--outcomes-file FILE` | none | Evaluates JSON/JSONL canonical and shadow outcome populations. |
| `--report-file PATH` | none | Writes the complete structured campaign payload to JSON. |
| `--output`, `-o` | `text` | Selects readable text or complete JSON. |
| `--config-dir DIRECTORY` | `config` | Loads another Apex configuration directory. |

### Text report sections

The campaign renderer includes:

1. Campaign Configuration
2. Dataset Coverage
3. Universe Summary
4. Missing Data
5. Manifest
6. Model Training
7. Artifacts

### Data behavior

- Downloads are checksum-verified.
- Missing historical files remain explicit.
- Missing OI or other unavailable evidence is never converted to zero.
- Canonical decisions and shadow experiments remain separate populations.
- Final-test promotion counts executed canonical outcomes, not no-trade rows.
- PBO remains unavailable without multiple varying configuration-fold vectors.
- Model authority remains withheld until all promotion gates pass.
- `--report-file` preserves complete campaign details even when terminal output is concise.

---

## `apex config-check`

### Purpose

Validates and displays the resolved Apex configuration.

```bash
apex config-check
```

Use this before scan, analyze, backtest, or research work when configuration may have changed.

The primary configuration directory is:

```text
config/
```

The primary default file is:

```text
config/default.yaml
```

Common settings include:

```yaml
methodology_gate_mode: enforce
futures_evidence_enabled: true
outcome_tracking_enabled: true
```

Optional evidence is fail-soft: unavailable optional data does not crash analysis and is not fabricated.

---

## `apex version`

Displays the installed Apex version:

```bash
apex version
```

---

## Output modes

### Text

Text is the default operator-facing mode:

```bash
apex scan
apex analyze BTCUSDT
apex backtest BTCUSDT
apex research campaign
```

### JSON

JSON preserves the complete structured record:

```bash
apex scan --output json
apex analyze BTCUSDT --output json
apex backtest BTCUSDT --output json
apex research campaign --output json
```

Use shell redirection when a command does not expose `--report-file`:

```bash
apex scan --output json > data/reports/scan.json
apex analyze BTCUSDT --output json > data/reports/btc_analysis.json
```

Use `--report-file` for backtest and research campaign:

```bash
apex backtest BTCUSDT --report-file data/reports/btc_backtest.json
apex research campaign --report-file data/research/campaign_report.json
```

---

## Explain mode

`--explain` appends diagnostics without changing the canonical decision.

Examples:

```bash
apex scan --explain
apex analyze BTCUSDT --explain
```

Explain output can include:

- methodology enforcement;
- opportunity portfolio mapping;
- multi-timeframe evidence;
- entry and chase rationale;
- stop and target rationale;
- supporting evidence;
- contradictions;
- missing evidence;
- collision and sequence;
- rejected or suppressed candidates;
- data quality;
- outcome-tracking status;
- historical calibration.

Use JSON when complete untruncated diagnostics are required.

---

## Canonical decision states

| State | Meaning |
|---|---|
| `READY_NOW` | Execution conditions are complete near current price. |
| `AGGRESSIVE_NOW` | An immediate but explicitly cautious entry is available. |
| `PULLBACK_PREFERRED` | Direction may be valid, but a retracement offers better geometry. |
| `RETEST_PREFERRED` | A level retest is the preferred execution path. |
| `RECLAIM_REQUIRED` | Price must regain a stated level before entry. |
| `APPROACHING_ENTRY` | Price is close to an incomplete entry condition. |
| `WAIT_FOR_CLOSE` | Candle completion is required. |
| `DEVELOPING_SETUP` | A measurable setup exists but is not executable yet. |
| `LATE_ENTRY` | Direction may remain valid, but entry quality has deteriorated. |
| `MISSED_ENTRY` | Planned geometry is no longer realistically available. |
| `INVALIDATED` | The structural thesis has failed. |
| `NO_TRADE` | No valid opportunity survived analysis and gating. |

These states describe setup condition, not certainty or win probability.

---

## Recommended daily workflow

```bash
# 1. Confirm configuration
apex config-check

# 2. Discover markets
apex scan --results 10 --shortlist 36

# 3. Inspect one candidate deeply
apex analyze BTCUSDT --explain

# 4. Save a complete structured analysis when needed
apex analyze BTCUSDT --output json > data/reports/btc_analysis.json

# 5. Evaluate historical behavior
apex backtest BTCUSDT \
  --decision-points 10 \
  --report-file data/reports/btc_backtest.json
```

For historical dataset work:

```bash
apex research campaign \
  --download-missing \
  --report-file data/research/campaign_report.json
```

---

## Removed legacy options

The following options are intentionally no longer part of the public CLI:

```text
scan --record
scan --record-db
scan --report
analyze --record
analyze --record-db
backtest --campaign
backtest --report
```

Use instead:

- automatic configuration-driven SQLite outcome tracking;
- `--output json` with shell redirection for scan/analyze;
- `--report-file` for backtest and research campaign;
- `apex research campaign` for historical campaign work.

---

## Help and troubleshooting

Show command help:

```bash
apex --help
apex scan --help
apex analyze --help
apex backtest --help
apex research --help
apex research campaign --help
apex config-check --help
apex version --help
```

Common checks:

```bash
# Confirm the virtual environment
which python
which apex

# Confirm package version
apex version

# Validate configuration
apex config-check

# Confirm repository state during development
git status --short
```

When a command fails, read the error before retrying. Do not silently replace missing market data, stale candles, unavailable symbols, incomplete historical files, or invalid limits with guessed values.
