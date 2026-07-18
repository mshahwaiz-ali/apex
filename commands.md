# Apex Command Reference

Apex exposes a small public CLI for Binance USDT perpetual-futures discovery, focused analysis, configuration validation, and chronological replay.

```text
apex scan
apex analyze SYMBOL
apex backtest SYMBOL
apex config-check
apex version
```

> Apex produces analysis. It does not place trades, recommend leverage, size positions from wallet equity, or manage exchange accounts.

## Before using the CLI

From the repository root:

```bash
cd ~/data_drive/apex
source .venv/bin/activate
```

Confirm the installed command surface:

```bash
apex --help
```

Use command-specific help whenever you need the exact installed options:

```bash
apex scan --help
apex analyze --help
apex backtest --help
apex config-check --help
```

## 1. Scan the futures market

```bash
apex scan
```

This is the broad discovery command. It:

1. discovers active Binance USDT perpetual contracts;
2. applies hard liquidity, spread, freshness, history, and exchange-metadata checks;
3. reserves coverage across trend, compression, fresh-break, fast-mover, range/rejection, benchmark-relative, and developing lanes;
4. runs the shared full analysis pipeline on each shortlisted symbol;
5. ranks and displays the strongest valid results.

A scan may return fewer results than requested. Apex does not invent or force setups to fill a quota.

### Common scan examples

Default text scan:

```bash
apex scan
```

Show only the top five displayed results:

```bash
apex scan --results 5
```

Analyze a wider shortlist, then display the top ten:

```bash
apex scan --shortlist 50 --results 10
```

Show only long candidates:

```bash
apex scan --direction long
```

Show only short candidates:

```bash
apex scan --direction short
```

Show both directions:

```bash
apex scan --direction both
```

Produce machine-readable JSON:

```bash
apex scan --output json
```

Use the short output flag:

```bash
apex scan -o json
```

Request a larger analysis candle window:

```bash
apex scan --candles 300
```

Use a static symbol list instead of live universe discovery:

```bash
apex scan --symbols-file config/symbols.yaml
```

Write the complete JSON payload to a report file while keeping terminal output:

```bash
apex scan --report data/reports/latest_scan.json
```

Append normalized analysis records to JSONL:

```bash
apex scan --record data/records/scan_history.jsonl
```

Store normalized analysis records in SQLite:

```bash
apex scan --record-db data/records/apex_analysis.sqlite3
```

Combine practical controls:

```bash
apex scan \
  --shortlist 40 \
  --results 8 \
  --direction both \
  --candles 250 \
  --report data/reports/latest_scan.json
```

### Scan options

| Option | Default | Purpose |
|---|---:|---|
| `--symbols-file PATH` | live discovery | Override the live universe with a readable symbol file |
| `--output`, `-o` | `text` | Output format: `text` or `json` |
| `--report PATH` | none | Write the full scan payload as JSON |
| `--record PATH` | none | Append normalized records to JSONL |
| `--record-db PATH` | none | Store normalized records in SQLite |
| `--candles N` | `200` | Closed-candle analysis depth; accepted range is 40-999 |
| `--results N` | `20` | Maximum displayed ranked results; accepted range is 1-50 |
| `--shortlist N` | `36` | Symbols sent to detailed analysis; accepted range is 1-100 |
| `--direction VALUE` | `both` | Display `long`, `short`, or `both` |
| `--config-dir PATH` | `config` | Configuration directory containing Apex YAML files |

## 2. Analyze one symbol

```bash
apex analyze BTCUSDT
```

This command bypasses market-wide discovery and sends the requested symbol directly into the same full analysis core used by `apex scan`.

It can return:

- market state and strategy routing;
- long, short, or `NO_TRADE` decision;
- entry status and entry zones;
- ideal entry and maximum chase;
- structural invalidation and stop;
- target and reward geometry;
- setup maturity, evidence, warnings, and contradictions;
- quality, confidence, and ranking diagnostics;
- management and expiry guidance.

### Common analysis examples

Analyze Bitcoin futures:

```bash
apex analyze BTCUSDT
```

Analyze another provider-supported futures symbol:

```bash
apex analyze ETHUSDT
```

Return JSON:

```bash
apex analyze BTCUSDT --output json
```

Use more candles per configured timeframe:

```bash
apex analyze BTCUSDT --candles 300
```

Append the result to a JSONL research record:

```bash
apex analyze BTCUSDT --record data/records/manual_analysis.jsonl
```

Store the result in SQLite:

```bash
apex analyze BTCUSDT --record-db data/records/apex_analysis.sqlite3
```

Load settings from another configuration directory:

```bash
apex analyze BTCUSDT --config-dir config
```

### Analyze options

| Option | Default | Purpose |
|---|---:|---|
| `SYMBOL` | required | Provider-supported futures symbol, such as `BTCUSDT` |
| `--output`, `-o` | `text` | Output format: `text` or `json` |
| `--candles N` | `200` | Candle depth per configured timeframe; accepted range is 40-1000 |
| `--record PATH` | none | Append the normalized result to JSONL |
| `--record-db PATH` | none | Store the normalized result in SQLite |
| `--config-dir PATH` | `config` | Configuration directory containing Apex YAML files |

## 3. Backtest a chronological campaign

```bash
apex backtest BTCUSDT
```

This is a chronological multi-decision replay campaign, not a portfolio-wide optimization command.

The command:

1. downloads closed historical candles;
2. creates non-overlapping decision windows;
3. analyzes only candles closed at each decision timestamp;
4. converts each selected setup into a replay signal;
5. simulates entry, stop, structural targets, partial exits, costs, optional funding, expiry, and ambiguous candles;
6. reports campaign expectancy, drawdown, fill/expiry rates, and MFE/MAE.

Decision points with no valid setup remain no-trade observations rather than manufactured signals.

### Common backtest examples

Default focused replay:

```bash
apex backtest BTCUSDT
```

Return JSON:

```bash
apex backtest BTCUSDT --output json
```

Use `5m` replay candles and hold out 24 candles:

```bash
apex backtest BTCUSDT --replay-timeframe 5m --replay-candles 24
```

Use ten decision points and model funding drag:

```bash
apex backtest BTCUSDT --decision-points 10 --funding-pct 0.01
```

Use a deeper historical decision prefix:

```bash
apex backtest BTCUSDT --candles 400 --replay-candles 50
```

Replay another timeframe:

```bash
apex backtest ETHUSDT --replay-timeframe 15m --replay-candles 20
```

### Backtest options

| Option | Default | Purpose |
|---|---:|---|
| `SYMBOL` | required | Provider-supported futures symbol |
| `--output`, `-o` | `text` | Output format: `text` or `json` |
| `--candles N` | `240` | Historical decision-prefix depth; accepted range is 80-900 |
| `--replay-timeframe TF` | `5m` | Timeframe used for the withheld forward replay |
| `--replay-candles N` | `24` | Number of withheld replay candles; accepted range is 1-100 |
| `--decision-points N` | `5` | Non-overlapping chronological decisions; accepted range is 1-50 |
| `--funding-pct N` | `0` | Optional funding drag applied to each filled trade |
| `--config-dir PATH` | `config` | Configuration directory containing Apex YAML files |

### What this backtest does not model

It does not model:

- wallet allocation;
- leverage or required margin;
- liquidation price;
- funded-account restrictions;
- paper-account state;
- live order placement or exchange execution.

## 4. Validate configuration

```bash
apex config-check
```

This command loads and validates the active configuration, then prints the resolved settings. Run it after changing YAML files or when a command fails during bootstrap.

Examples:

```bash
apex config-check
apex config-check --help
```

The primary runtime configuration is `config/default.yaml`. The current default methodology gate is configured in shadow mode, meaning methodology diagnostics are calculated and exposed without automatically replacing every established public decision.

Analysis JSON uses schema version 2. Existing strategy and status keys remain for one compatibility cycle; canonical family, subtype, entry state, bar expiry, and rule-based quality fields are additive.

## 5. Show the installed version

```bash
apex version
```

This prints the installed Apex package version.

## Output formats

Commands that support output selection accept:

```text
text
json
```

Use text for operator-readable terminal output:

```bash
apex analyze BTCUSDT --output text
```

Use JSON for scripts, storage, comparison, and research:

```bash
apex analyze BTCUSDT --output json
```

## Understanding common decisions

| Decision or status | Practical meaning |
|---|---|
| `READY_NOW` | Configured execution conditions are complete near the current price |
| `AGGRESSIVE_NOW` | Immediate entry exists but carries explicit caution |
| `PULLBACK_PREFERRED` | Current structure may remain usable, but a retracement improves geometry |
| `RETEST_PREFERRED` | A level retest offers the preferred execution path |
| `RECLAIM_REQUIRED` | Price must regain the stated level before approval |
| `APPROACHING_ENTRY` / `WATCH_NEAR_ENTRY` | Price is close, but the entry condition is not complete |
| `WAIT_FOR_CLOSE` | The pattern or breakout depends on candle completion |
| `DEVELOPING_SETUP` | A measurable setup exists but is not yet executable |
| `LATE_ENTRY` / `LATE_OR_CHASING` | Direction may remain valid, but the current entry has deteriorated |
| `MISSED_ENTRY` | The planned geometry is no longer realistically available |
| `INVALIDATED` | The underlying trade thesis has failed structurally |
| `NO_TRADE` | No valid setup survived the current analysis and gating path |

These labels describe state, not certainty.

## Recommended operator workflow

Start with configuration validation:

```bash
apex config-check
```

Run broad discovery:

```bash
apex scan --results 10 --shortlist 30
```

Inspect one selected symbol in detail:

```bash
apex analyze BTCUSDT
```

Capture JSON when comparing or researching results:

```bash
apex analyze BTCUSDT --output json > /tmp/btc_analysis.json
```

Use focused replay to inspect how one historical decision behaved:

```bash
apex backtest BTCUSDT --output json
```

## Development smoke checks

These commands verify imports and public CLI registration. They do not replace the full test suite.

```bash
.venv/bin/python -c "import apex.cli_app"
.venv/bin/apex --help
.venv/bin/apex scan --help
.venv/bin/apex analyze BTCUSDT --help
.venv/bin/apex backtest BTCUSDT --help
.venv/bin/apex config-check --help
.venv/bin/apex version
```

For a code-change validation batch, also run the appropriate Ruff formatting and safe fixes, scoped mypy, relevant pytest tests, and:

```bash
git diff --check
```

Only claim validation results from commands whose terminal output was actually observed.
