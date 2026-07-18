# Apex Trading Agent

Apex is a deterministic Binance USDT perpetual-futures discovery, trade-analysis, and chronological replay engine.

It discovers tradable markets, shortlists different opportunity types, evaluates multi-timeframe structure, routes compatible strategies, searches for current and developing entries, defines structural invalidation, projects realistic targets, and explains why a setup is actionable, cautious, developing, late, rejected, or unavailable.

> Apex is an analysis product. It does not place orders, manage wallets or exchange accounts, recommend leverage, or guarantee profitable trades.

## Public CLI

```text
apex scan
apex analyze SYMBOL
apex backtest SYMBOL
apex config-check
apex version
```

See [`commands.md`](commands.md) for usage examples and command options.

## Current product scope

Apex currently supports:

- live Binance USDT perpetual-futures universe discovery;
- hard market-usability checks;
- lane-based shortlisting instead of a raw-gainer-only queue;
- shared full analysis for `scan` and `analyze`;
- multi-timeframe market-state and structure analysis;
- strategy-specific setup generation and entry evaluation;
- structural stops, target geometry, duration, and management guidance;
- deterministic text and JSON output;
- append-only JSONL and SQLite analysis records;
- chronological multi-decision replay through `apex backtest`.

Apex does not force a trade or a minimum result count. A symbol may correctly resolve to `NO_TRADE`.

## Shared analysis architecture

`apex scan` and `apex analyze SYMBOL` use the same full-analysis core after symbol selection.

```text
symbol selection
→ market-data loading
→ multi-timeframe structure and market state
→ strategy routing and candidate generation
→ methodology evidence and gating
→ entry opportunity search
→ invalidation, stop, targets, duration, and management
→ scoring, ranking, and explanation
→ text or JSON output
```

The only command-level difference is symbol selection:

- `scan` discovers, screens, and shortlists the futures universe.
- `analyze` sends one requested symbol directly into full analysis.

## Discovery model

The scanner separates basic tradability from opportunity discovery.

Hard tradability checks cover areas such as:

- liquidity and spread;
- market-data freshness and history;
- exchange metadata and precision;
- candle continuity and basic execution quality.

Surviving markets can receive shortlist coverage through lanes such as:

- trend continuation;
- compression and expansion;
- fresh breakout or breakdown;
- fast mover;
- range boundary or liquidity rejection;
- benchmark-relative strength or weakness;
- developing setup.

Discovery rank decides which symbols deserve deeper analysis. It does not approve a trade.

## Analysis methodology

Apex is structure-first. Indicators provide categorized evidence rather than independent votes.

The engine can evaluate:

- swing structure, support, resistance, ranges, breakouts, retests, and polarity;
- trend, compression, expansion, transition, exhaustion, and chaotic conditions;
- EMA and VWAP relationships;
- RSI and MACD momentum state;
- relative volume, participation, ATR, and volatility expansion;
- wick behavior, liquidity sweeps, rejection, reclaim, and candle completion;
- optional futures-specific evidence when reliable data is available.

Correlated indicators are grouped so repeated versions of the same information cannot dominate a score.

## Strategy families

The configured strategy set includes families such as:

- momentum breakout;
- breakout continuation and retest;
- first-pullback and trend-pullback continuation;
- compression expansion;
- range reversal;
- failed-breakout reversal;
- liquidity-rejection reversal;
- VWAP reclaim or rejection;
- momentum scalp;
- exhaustion reversal.

Each strategy is evaluated against market state, setup maturity, entry quality, structural invalidation, target room, contradictions, and strategy-specific requirements.

## Entry and output states

Outputs can distinguish:

```text
READY_NOW
AGGRESSIVE_NOW
PULLBACK_PREFERRED
RETEST_PREFERRED
RECLAIM_REQUIRED
APPROACHING_ENTRY
WAIT_FOR_CLOSE
DEVELOPING_SETUP
LATE_ENTRY
MISSED_ENTRY
INVALIDATED
NO_TRADE
```

`READY_NOW` means configured execution conditions are complete. It does not imply certainty or a guaranteed win.

Scores describe analytical quality. They are not win probabilities unless explicit out-of-sample calibration metadata is present.

## Methodology gate

The trade-plan methodology contracts, evidence taxonomy, setup maturity, target feasibility, stop-noise checks, and decision diagnostics are integrated into the shared analysis path.

The current default configuration uses:

```yaml
methodology_gate_mode: shadow
```

Shadow mode exposes methodology diagnostics while preserving the established public decision path for comparison and validation. Stricter enforcement should be enabled only through reviewed configuration and validated tests.

## Backtesting scope

`apex backtest SYMBOL` runs a chronological multi-decision campaign:

- decisions use only information available at their timestamps;
- future candles are withheld for replay;
- entries, stops, structural targets, partial exits, costs, optional funding, expiry, and same-candle ambiguity are evaluated deterministically;
- campaign-level expectancy, drawdown, fill and expiry rates, MFE, and MAE are reported.

It is not a portfolio optimizer and does not model wallet allocation, leverage, margin, liquidation, paper-account state, or live exchange execution.

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

Confirm the CLI:

```bash
apex --help
```

## Configuration

Runtime configuration lives under `config/`, with `config/default.yaml` as the primary configuration.

Validate it with:

```bash
apex config-check
```

Configuration controls provider behavior, screening, discovery budgets, enabled strategies, timeframe roles, data rules, methodology-gate mode, scoring, and ranking.

## Repository architecture

```text
src/apex/
├── application/         # Discovery, shared analysis, methodology, ranking, orchestration
├── backtesting/         # Chronological replay campaigns
├── cli_commands/        # Public CLI commands
├── config/              # Validated YAML-backed settings
├── data/                # Providers and normalized market data
├── domain/              # Core contracts and models
├── features/            # Indicators and evidence
├── liquidity/           # Zones, sweeps, and rejection evidence
├── market_environment/  # Market-state classification
├── presentation/        # Deterministic text and JSON rendering
├── scoring/             # Candidate quality and ranking
└── strategies/          # Strategy applicability and setup generation
```

The repository favors strict typing, deterministic behavior, explicit rejection reasons, reproducible serialization, and production-equivalent historical evaluation.

## Development validation

Before local validation:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate
```

For documentation-only changes:

```bash
git diff --check
```

For code changes, run the appropriate scoped Ruff formatting and safe fixes, scoped mypy, relevant pytest tests, CLI smoke checks, and `git diff --check`.

Never report a validation command as passed unless its actual terminal output was observed.

## Methodology authority

[`docs/trade_plan.md`](docs/trade_plan.md) is the implementation authority for discovery, shared analysis, market state, evidence, strategy routing, entries, invalidation, targets, duration, scoring, rejection, ranking, and output reasoning.
