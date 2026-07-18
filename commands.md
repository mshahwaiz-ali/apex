# Apex Command Reference

Apex provides a focused CLI for Binance USDT perpetual-futures discovery, single-symbol analysis, configuration validation, and chronological replay.

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
| `apex backtest SYMBOL` | Run a chronological multi-decision replay campaign. |
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
4. sends shortlisted symbols through the shared full-analysis pipeline;
5. ranks and displays the strongest surviving results.

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
| `--candles N` | `200` | Closed-candle analysis depth |
| `--results N` | `20` | Maximum displayed ranked results |
| `--shortlist N` | `36` | Symbols sent to detailed analysis |
| `--direction VALUE` | `both` | Display `long`, `short`, or `both` |
| `--config-dir PATH` | `config` | Configuration directory |

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

- market state and compatible strategy;
- long, short, or `NO_TRADE`;
- current and preferred entry opportunities;
- ideal entry and maximum-chase boundary;
- structural invalidation and stop;
- TP1, TP2, TP3, and conditional runner logic;
- expected movement and reward geometry;
- setup maturity, evidence, contradictions, and warnings;
- deterministic quality and confidence diagnostics;
- management guidance and setup expiry.

### Common examples

```bash
apex analyze BTCUSDT
apex analyze ETHUSDT --output json
apex analyze BTCUSDT --candles 300
apex analyze BTCUSDT --record data/records/manual_analysis.jsonl
apex analyze BTCUSDT --record-db data/records/apex_analysis.sqlite3
```

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

This is not a portfolio backtester. It does not model wallet allocation, leverage, required margin, liquidation, paper-account state, or live exchange execution.

Use:

```bash
apex backtest --help
```

for the exact installed options.

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
```

Shadow mode computes and exposes methodology diagnostics without allowing every new methodology gate to replace the established public decision automatically.

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
