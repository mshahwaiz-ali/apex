# Apex Command Reference

Apex is a deterministic Binance USDT perpetual-futures opportunity-discovery and analysis tool.
It does not manage wallets, recommend leverage, place orders, run paper accounts, operate testnet execution, or evaluate funded-account readiness.

## Public CLI

```text
apex scan
apex analyze SYMBOL
apex config-check
apex backtest SYMBOL
apex version
```

## Commands

### Scan Futures Markets

```bash
apex scan --help
apex scan
apex scan --output json
apex scan --results 20 --shortlist 30 --direction both
```

Discovers active Binance USDT perpetual-futures symbols, screens market quality, analyzes eligible symbols, and ranks deterministic opportunities.
Use `--results` to control displayed ranked results, `--shortlist` to control detailed analysis breadth, and `--direction long|short|both` to focus the final display.

### Analyze One Symbol

```bash
apex analyze BTCUSDT --help
apex analyze BTCUSDT
apex analyze BTCUSDT --output json
apex analyze BTCUSDT --config-dir config
```

Runs focused multi-timeframe analysis for one futures symbol and returns entry geometry, structural invalidation, TP1/TP2/TP3 guidance, scoring, warnings, and rejection reasons.

### Backtest One Symbol

```bash
apex backtest BTCUSDT --help
apex backtest BTCUSDT
apex backtest BTCUSDT --output json
apex backtest BTCUSDT --replay-timeframe 5m --replay-candles 24
```

Replays a focused historical prefix/holdout evaluation for one symbol. It evaluates discovery signal geometry only; it does not model wallet allocation, leverage, margin, liquidation, funded rules, paper state, or exchange execution.

### Check Configuration

```bash
apex config-check
```

Validates the active focused configuration and prints resolved settings.

### Version

```bash
apex version
```

Prints the installed Apex package version.

## Development Validation

```bash
.venv/bin/python -c "import apex.cli_app"
.venv/bin/apex --help
.venv/bin/apex scan --help
.venv/bin/apex analyze BTCUSDT --help
.venv/bin/apex backtest BTCUSDT --help
.venv/bin/pytest
.venv/bin/mypy src
git diff --check
```

Only report validation results from commands that actually ran.
