# Apex CLI Usage Guide

Apex is organized around user workflows rather than implementation phases or internal artifact names.

## Start here

```bash
apex
```

The visible top-level workflows are:

```text
apex futures      Find and evaluate futures opportunities
apex spot         Find and evaluate long-only spot opportunities
apex paper        Record and monitor simulated trades
apex research     Run datasets, backtests, comparisons, and calibration
apex validation   Review evidence and readiness gates
apex system       Check configuration, connectivity, and raw market data
apex execute      Testnet-only execution and safety tools
```

Use `--help` at any level:

```bash
apex futures --help
apex futures scan --help
apex paper --help
```

## Futures workflow

Scan the configured futures universe:

```bash
apex futures scan --help
```

Analyze one market in detail:

```bash
apex futures analyze BTCUSDT --help
```

Paper-simulate a currently approved setup:

```bash
apex futures simulate --help
```

Futures analysis can produce an actionable plan, a wait state, or a structured rejection. It does not place an order.

## Spot workflow

Scan selected live spot markets:

```bash
apex spot scan --help
```

Analyze one spot market:

```bash
apex spot analyze BTCUSDT --help
```

Run the complete live spot workflow:

```bash
apex spot live --help
```

Build a bounded entry, allocation, target, and exit plan:

```bash
apex spot plan --help
```

Spot commands are long-only and do not use margin, leverage, borrowing, or short selling.

## Paper trading

```bash
apex paper --help
```

Paper commands record approved setups, update them through candle-by-candle lifecycle rules, report current guidance, and summarize performance. They do not place exchange orders.

## Research and backtesting

```bash
apex research --help
```

Common workflows include:

```bash
apex research backtest --help
apex research campaign --help
apex research compare --help
apex research edge-report --help
apex research edge-validate --help
```

Advanced dataset and optimization commands remain available for compatibility but are intentionally hidden from the top-level help screen. Existing scripts using legacy command paths continue to work.

## Validation and readiness

```bash
apex validation --help
```

Common workflows include:

```bash
apex validation forward-edge --help
apex validation build-evidence --help
apex validation review --help
apex validation daily --help
apex validation history --help
apex validation funded-readiness --help
```

A readiness result is evidence for manual review. It is not execution authorization.

## System and market data

```bash
apex system --help
```

Examples:

```bash
apex system check
apex system config
apex system ticker BTCUSDT
apex system candles BTCUSDT --help
apex system version
```

## Compatibility

The previous flat command names remain callable as hidden aliases. For example, an existing script using `apex scan` can continue to run, while new interactive usage should prefer `apex futures scan`.

## Safety boundary

Apex supports analysis, research, historical replay, paper trading, evidence collection, and testnet-oriented execution tooling. Nothing in the CLI authorizes funded-account, production, or real-money execution.
