# Apex Trading Agent

Apex is a deterministic Binance USDT perpetual-futures opportunity-discovery and trade-analysis engine.

It discovers active markets, screens execution quality, evaluates multi-timeframe structure, routes compatible strategies, searches for usable entries, defines structural invalidation, projects realistic targets, and explains why a setup is actionable, developing, late, rejected, or unavailable.

> Apex is an analysis product. It does not place orders, manage wallets, recommend leverage, operate paper or testnet accounts, or guarantee profitable trades.

## Public CLI

```text
apex scan
apex analyze SYMBOL
apex backtest SYMBOL
apex config-check
apex version
```

For complete examples and option explanations, see [`commands.md`](commands.md).

## Core design

`apex scan` and `apex analyze SYMBOL` share the same analysis core.

```text
Symbol selection
→ market-data loading
→ multi-timeframe analysis
→ market-state and strategy routing
→ candidate generation
→ methodology evidence and gating
→ entry, stop, target, duration, and management geometry
→ scoring, ranking, and explanation
→ text or JSON output
```

The commands differ only at symbol selection:

- `scan` discovers, screens, and shortlists the futures universe.
- `analyze` sends one requested symbol directly into the shared analysis pipeline.

Apex does not force trades or fill a result quota. Poor market quality, invalid structure, weak target room, or incomplete evidence may produce `NO_TRADE`.

## What an analysis explains

A selected setup can describe:

- symbol, direction, strategy, and market state;
- current price and entry status;
- immediate and preferred entry zones;
- ideal entry and maximum-chase boundary;
- structural invalidation and stop price;
- TP1, TP2, TP3, and conditional runner logic;
- expected movement and reward geometry;
- setup maturity, evidence, contradictions, and warnings;
- deterministic quality and ranking scores;
- management guidance and time-based expiry.

Scores represent analytical quality. They are not calibrated win probabilities unless an output explicitly includes historical calibration metadata.

## Default timeframe roles

| Timeframe | Role |
|---|---|
| `1m` | Immediate timing |
| `3m` | Trigger refinement |
| `5m` | Entry structure |
| `15m` | Setup formation |
| `30m` | Intraday context |
| `1h` | Intermediate structure |
| `4h` | Macro structure, obstacles, and target context |

Lower timeframes refine execution; they do not erase direct higher-timeframe structural opposition.

## Analysis methodology

Apex is structure-first. Indicators provide evidence rather than independent votes.

Typical inputs include:

- swing structure, support, resistance, ranges, breakouts, retests, and polarity;
- trend, compression, expansion, exhaustion, and chaotic conditions;
- EMA and VWAP relationships;
- RSI and MACD momentum state;
- relative volume, participation, ATR, and volatility expansion;
- wick behavior, liquidity sweeps, rejection, reclaim, and candle completion;
- optional futures evidence when reliable data is available.

Correlated indicators are grouped so several versions of the same information cannot dominate a score.

## Strategy families

The active configuration enables:

- momentum breakout;
- breakout continuation;
- breakout retest;
- first-pullback continuation;
- trend pullback;
- compression expansion;
- range reversal;
- failed-breakout reversal;
- liquidity-rejection reversal;
- VWAP reclaim or rejection;
- momentum scalp;
- exhaustion reversal.

Each symbol may create several candidates. Apex evaluates compatibility, maturity, entry quality, invalidation, target room, contradictions, and ranking before selecting the strongest result.

## Entry and decision states

Public output distinguishes actionable entries from developing or degraded setups. Depending on the selected contract and presentation layer, outputs can include states such as:

- `READY_NOW`
- `AGGRESSIVE_NOW`
- `PULLBACK_PREFERRED`
- `RETEST_PREFERRED`
- `RECLAIM_REQUIRED`
- `APPROACHING_ENTRY` or `WATCH_NEAR_ENTRY`
- `WAIT_FOR_CLOSE`
- `DEVELOPING_SETUP`
- `LATE_ENTRY` or `LATE_OR_CHASING`
- `MISSED_ENTRY`
- `INVALIDATED`
- `NO_TRADE`

`READY_NOW` means the configured execution conditions are complete. It does not mean the trade is certain to win.

## Current methodology-gate state

The trade-plan methodology contracts, evidence, setup maturity, target feasibility, stop-noise checks, and decision diagnostics are integrated into the shared analysis path.

The default configuration currently uses:

```yaml
methodology_gate_mode: shadow
```

In shadow mode, Apex computes and exposes methodology diagnostics without allowing every new gate to replace the established public decision automatically. This supports safe comparison and validation before stricter enforcement. Change gate behavior only through reviewed configuration and validated tests.

## Scan workflow

`apex scan`:

1. discovers active Binance USDT perpetual contracts;
2. applies tradability checks without requiring a minimum recent move;
3. shortlists symbols through lane budgets rather than a raw-mover queue;
4. runs the shared full analysis for each shortlisted symbol;
5. filters the display by long, short, or both directions;
6. returns ranked text or JSON results.

Useful controls include `--results`, `--shortlist`, `--direction`, `--candles`, `--symbols-file`, `--report`, `--record`, and `--record-db`.

## Focused analysis

`apex analyze BTCUSDT` bypasses market-wide selection and applies the same full analysis core directly to `BTCUSDT`.

It supports text or JSON output plus optional append-only JSONL and SQLite analysis records.

## Backtesting

`apex backtest SYMBOL` performs a chronological multi-decision replay campaign:

- only closed historical candles are used for the decision prefix;
- withheld candles are used for forward replay;
- entry touch, stop, targets, partial closes, costs, expiry, and same-candle ambiguity are evaluated deterministically;
- text or JSON output is supported.

The default campaign evaluates five non-overlapping decisions and reports costs, partials, fill/expiry rates, and MFE/MAE. It is not a portfolio backtester and does not model wallet allocation, leverage, margin, liquidation, paper-account state, or exchange execution.

## Installation

Requirements: Python 3.11 or newer.

```bash
git clone https://github.com/mshahwaiz-ali/apex.git
cd apex
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Inspect the installed command surface:

```bash
apex --help
```

## Configuration

The active configuration lives under `config/`, with `config/default.yaml` as the primary runtime configuration.

It controls:

- provider and runtime behavior;
- futures screening thresholds and weights;
- shortlist size and result limits;
- enabled strategies;
- analysis timeframes and timeframe roles;
- data-staleness and resampling rules;
- methodology-gate mode;
- deterministic scoring and ranking behavior.

Validate the resolved configuration with:

```bash
apex config-check
```

## Architecture

```text
src/apex/
├── application/         # Selection, shared analysis, methodology, ranking, orchestration
├── backtesting/         # Focused chronological replay
├── cli_commands/        # Public CLI commands
├── config/              # Validated YAML-backed settings
├── data/                # Providers and normalized market data
├── domain/              # Core contracts and models
├── features/            # Reusable indicators and evidence
├── liquidity/           # Zones, sweeps, and rejection evidence
├── market_environment/  # Market-state classification
├── presentation/        # Deterministic text and JSON rendering
├── scoring/             # Candidate quality and ranking
└── strategies/          # Strategy applicability and setup generation
```

The repository favors strict typing, deterministic behavior, explicit failure reasons, reproducible serialization, and production-equivalent historical evaluation.

## Development validation

Before validation:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate
```

For documentation-only changes, run at minimum:

```bash
git diff --check
```

For code changes, run the appropriate Ruff formatting and safe fixes, scoped mypy, relevant pytest tests, CLI smoke checks, and `git diff --check`.

Never report a validation command as passed unless its actual terminal output was observed.

## Methodology authority

[`docs/trade_plan.md`](docs/trade_plan.md) is the implementation authority for trade discovery, shared analysis, market state, evidence, strategy routing, entries, invalidation, targets, duration, scoring, rejection, ranking, and output reasoning.
