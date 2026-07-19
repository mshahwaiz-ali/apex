# Apex Command Reference

Apex provides a focused CLI for Binance USDT perpetual-futures discovery, derivatives-aware early-warning analysis, chronological replay, and checksum-verified research campaigns.

> Apex analyzes markets. It does not place orders, manage exchange accounts, recommend leverage, or guarantee profitable trades.

## Setup

From the repository root:

```bash
cd ~/data_drive/apex
source .venv/bin/activate
```

Confirm the installed CLI:

```bash
apex --help
```

## Commands

| Command | Purpose |
|---|---|
| `apex scan` | Discover, shortlist, fully analyze, and rank active futures opportunities. |
| `apex analyze SYMBOL` | Run the shared full-analysis pipeline for one requested symbol. |
| `apex backtest SYMBOL` | Run a chronological production-path replay for one symbol. |
| `apex backtest --campaign` | Build, verify, report, or train from a point-in-time public-data campaign. |
| `apex config-check` | Validate configuration and display resolved settings. |
| `apex version` | Display the installed Apex version. |

## Scan

```bash
apex scan
```

The scan workflow:

1. discovers active Binance USDT perpetual contracts;
2. applies hard tradability checks for liquidity, spread, freshness, history, and exchange metadata;
3. reserves shortlist coverage across trend, compression, fresh-break, fast-mover, range/rejection, benchmark-relative, and developing lanes;
4. converts raw lane scores into cross-sectional percentiles;
5. sends shortlisted symbols through the shared multi-timeframe and futures-evidence pipeline;
6. ranks and displays only ready, conditional, and developing opportunities; rejected/no-setup markets remain summarized as counts.

Apex may return fewer results than requested. It does not force trades to fill a quota.

### Common examples

```bash
apex scan
apex scan --results 5
apex scan --shortlist 50 --results 10
apex scan --direction long
apex scan --direction short
apex scan --direction both
apex scan --output json
apex scan --explain
apex scan --candles 300
apex scan --symbols-file config/symbols.yaml
apex scan --report data/reports/latest_scan.json
apex scan --record data/records/scan_history.jsonl
apex scan --record-db data/records/apex_analysis.sqlite3
```

### Important options

| Option | Default | Purpose |
|---|---:|---|
| `--symbols-file PATH` | live discovery | Use a static symbol list |
| `--output`, `-o` | `text` | Select `text` or `json` output |
| `--report PATH` | none | Write the complete scan payload as JSON |
| `--record PATH` | none | Append normalized records to JSONL |
| `--record-db PATH` | none | Store normalized records in SQLite |
| `--explain` | off | Show extra readable ranking, routing, evidence, and rejection sections |
| `--candles N` | `200` | Closed-candle analysis depth |
| `--results N` | `20` | Maximum displayed ranked results |
| `--shortlist N` | `36` | Symbols sent to detailed analysis |
| `--direction VALUE` | `both` | Display `long`, `short`, or `both` |
| `--config-dir PATH` | `config` | Configuration directory |

With `outcome_tracking_enabled: true`, every scan also records individual analyzed opportunities in `data/reports/analysis.db` and reconciles older pending outcomes for the same symbols. `--record-db` replaces that automatic SQLite path for the current run.

Use the installed command help for exact ranges and current option behavior:

```bash
apex scan --help
```

## Analyze one symbol

```bash
apex analyze BTCUSDT
```

`analyze` bypasses market-wide discovery and sends the requested symbol directly into the same analysis core used by `scan`.

The output can include:

- market state probability, persistence, archetype, and compatible strategy;
- early-warning state derived from price, OI, taker flow, funding, and basis;
- long, short, or `NO_TRADE`;
- current and preferred entry opportunities;
- ideal entry and maximum-chase boundary;
- structural invalidation and stop;
- TP1, TP2, TP3, and conditional runner logic;
- expected movement and reward geometry;
- setup maturity, evidence, contradictions, and warnings;
- deterministic quality and confidence diagnostics;
- management guidance and setup expiry;
- expected R, calibrated probability interval, sample size, and artifact authority when a model is promoted;
- an explicit withholding reason when historical probability is unavailable.

### Common examples

```bash
apex analyze BTCUSDT
apex analyze BTCUSDT --explain
apex analyze ETHUSDT --output json
apex analyze BTCUSDT --candles 300
apex analyze BTCUSDT --record data/records/manual_analysis.jsonl
apex analyze BTCUSDT --record-db data/records/apex_analysis.sqlite3
```

Important options:

| Option | Default | Purpose |
|---|---:|---|
| `--output`, `-o` | `text` | Select concise text or complete JSON |
| `--explain` | off | Show extra readable diagnostics without dumping raw JSON |
| `--candles N` | `200` | Analysis depth; installed range is `200..1000` |
| `--record PATH` | none | Append a JSONL analysis record |
| `--record-db PATH` | automatic default DB | Choose an explicit SQLite record database |
| `--config-dir PATH` | `config` | Load settings from another configuration directory |

Use:

```bash
apex analyze --help
```

for the exact installed options.

## Backtest

```bash
apex backtest BTCUSDT
```

The backtest command runs a chronological multi-decision replay campaign. It:

1. loads closed historical candles;
2. creates non-overlapping decision windows;
3. analyzes only information available at each decision timestamp;
4. converts valid selected setups into replay signals;
5. models entry, stop, structural targets, partial exits, costs, optional funding, expiry, and ambiguous candles;
6. reports campaign expectancy, drawdown, fill and expiry rates, and MFE/MAE.

No-trade decision points remain no-trade observations.

### Common examples

```bash
apex backtest BTCUSDT
apex backtest BTCUSDT --output json
apex backtest BTCUSDT --replay-timeframe 5m --replay-candles 24
apex backtest BTCUSDT --decision-points 10 --funding-pct 0.01
apex backtest BTCUSDT --candles 400 --replay-candles 50
```

### Single-symbol replay options

| Option | Default | Purpose |
|---|---:|---|
| `--output`, `-o` | `text` | Select the sectioned research report or full JSON |
| `--candles N` | `240` | Historical prefix; accepted range is `201..900` so the decision always has 200 closed bars |
| `--replay-timeframe TF` | `5m` | Candle stream used for outcome replay |
| `--replay-candles N` | `24` | Maximum candles retained after each decision |
| `--decision-points N` | `5` | Non-overlapping chronological decisions |
| `--funding-pct N` | `0.0` | Optional modeled funding drag |
| `--config-dir PATH` | `config` | Configuration directory |

The JSON report includes training, validation, and untouched final-test labels plus deflated-Sharpe and PBO promotion statistics. These fields remain non-authoritative until sufficient final-test evidence passes every promotion gate.

This is not a portfolio backtester. It does not model wallet allocation, leverage, required margin, liquidation, paper-account state, or live exchange execution.

Use:

```bash
apex backtest --help
```

for the exact installed options.

## Historical campaign and ML

```bash
apex backtest --campaign --download-missing
```

Without `--start` and `--end`, the campaign covers the latest 24 complete UTC months. If no saved universe exists, `--download-missing` builds each month's top-30 eligible USDT-perpetual membership from the previous month's quote volume. It then downloads public 1-minute klines, funding-rate archives, and aggregate trades under the git-ignored dataset directory.

### Common examples

```bash
apex backtest --campaign --download-missing
apex backtest --campaign --start 2025-01 --end 2025-06 --download-missing
apex backtest --campaign --dataset-dir /mnt/research/apex-binance --download-missing
apex backtest --campaign --symbols-file data/research/binance_um/universe_by_month.json --download-missing
apex backtest --campaign --symbols-file data/research/binance_um/universe_by_month.json --train-model --output json
apex backtest --campaign --download-missing --report data/research/campaign-report.json --output json
```

### Campaign options

| Option | Default | Purpose |
|---|---:|---|
| `--campaign` | off | Select multi-symbol campaign mode; makes positional `SYMBOL` optional |
| `--start VALUE` | latest 24-month range | Inclusive UTC month/date lower bound |
| `--end VALUE` | latest complete month | Inclusive UTC month/date upper bound |
| `--symbols-file PATH` | dynamic/saved universe | JSON symbol list or month-to-symbol mapping |
| `--dataset-dir PATH` | `data/research/binance_um` | Git-ignored archive, manifest, features, and models root |
| `--download-missing` | off | Build missing universe data and download checksum-verified archives |
| `--train-model` | off | Train the three model families when `feature_rows.jsonl` exists |
| `--report PATH` | none | Write the complete campaign report as JSON |

Downloads are resumable and verified against Binance SHA-256 checksum files. Missing historical OI or order-book evidence remains missing; it is never converted to zero.

Model training compares fixed-seed regularized logistic regression and histogram gradient boosting, applies chronological 60/20/20 splits with purge/embargo, and calibrates on validation-only data using isotonic regression. Runtime expected-R ranking activates only after integrity and promotion gates pass.

## Configuration

```bash
apex config-check
```

The primary runtime configuration is:

```text
config/default.yaml
```

The current default methodology gate is:

```yaml
methodology_gate_mode: shadow
futures_evidence_enabled: true
outcome_tracking_enabled: true
```

Shadow mode computes and exposes methodology diagnostics without allowing every new methodology gate to replace the established public decision automatically. Futures evidence and local outcome reconciliation are fail-soft: unavailable optional evidence does not crash analysis or become fabricated data.

Analysis JSON uses schema version 2. Canonical strategy family, subtype, entry state, bar expiry, and rule-based quality fields are additive during the compatibility period.

## Common decision states

| State | Meaning |
|---|---|
| `READY_NOW` | Rule-defined execution conditions are complete near current price |
| `AGGRESSIVE_NOW` | An immediate entry exists with explicit caution |
| `PULLBACK_PREFERRED` | A retracement offers better geometry |
| `RETEST_PREFERRED` | A level retest is the preferred entry path |
| `RECLAIM_REQUIRED` | Price must regain the stated level |
| `APPROACHING_ENTRY` | Price is near an incomplete entry condition |
| `WAIT_FOR_CLOSE` | Candle completion is required |
| `DEVELOPING_SETUP` | A measurable setup exists but is not executable yet |
| `LATE_ENTRY` | Direction may remain valid, but entry quality has deteriorated |
| `MISSED_ENTRY` | The planned geometry is no longer realistically available |
| `INVALIDATED` | The underlying thesis has failed structurally |
| `NO_TRADE` | No valid setup survived analysis and gating |

These states describe setup condition, not certainty.

## Early-warning states

| State | Interpretation |
|---|---|
| `BREAKOUT_PREPARATION` / `BREAKDOWN_PREPARATION` | Compression and range location align with directional taker participation |
| `BULLISH_PARTICIPATION` / `BEARISH_PARTICIPATION` | Price, OI, and aggressive flow expand coherently |
| `SHORT_COVERING` | Price rises while OI contracts; this is not treated as fresh long positioning |
| `LONG_LIQUIDATION` | Price falls while OI contracts; this is not treated as fresh short positioning |
| `CROWDED_LONG_FRAGILITY` / `CROWDED_SHORT_FRAGILITY` | Funding indicates crowded positioning and liquidation risk, not standalone direction |
| `EXHAUSTION_REVERSAL_WATCH` | An extended move is losing participation acceleration |
| `CONTRADICTORY_EVIDENCE` | Price and participation inputs disagree |
| `INSUFFICIENT_EVIDENCE` | Required independent inputs are missing or stale |
| `NEUTRAL` | No coherent early-warning matrix is active |

Early warnings change context and rank; they do not bypass entry geometry, invalidation, liquidity, freshness, or target-room requirements.

## Practical workflow

```bash
apex config-check
apex scan --results 10 --shortlist 36
apex analyze BTCUSDT
apex backtest BTCUSDT --output json
```

For machine-readable research output:

```bash
apex analyze BTCUSDT --output json > /tmp/btc_analysis.json
```

## Development validation

Documentation-only changes require at minimum:

```bash
git diff --check
```

For code changes, run scoped Ruff formatting and safe fixes, scoped mypy, relevant pytest tests, CLI smoke checks, and `git diff --check`.

Only report validation results that were actually observed.
