# Apex Trading Agent

Deterministic Binance USDT perpetual-futures opportunity discovery and analysis.

Apex scans active markets, evaluates multi-timeframe structure and momentum, ranks actionable long and short candidates, and produces explicit entry geometry, structural invalidation, targets, warnings, and management guidance.

## Product scope

Apex is an analysis product. It does not manage wallets, size positions from account equity, recommend leverage, model liquidation, place orders, run paper accounts, operate testnet execution, evaluate funded-account constraints, or mutate strategy configuration automatically.

The supported public CLI surface is intentionally small:

```text
apex scan
apex analyze SYMBOL
apex config-check
apex backtest SYMBOL
apex version
```

## Core workflow

```text
Discover active Binance USDT perpetual contracts
→ filter unusable markets
→ run lightweight market-wide screening
→ shortlist the strongest opportunities
→ analyze selected symbols across configured timeframes
→ evaluate applicable strategies
→ build actionable entry, stop, target, and management geometry
→ score and rank candidates deterministically
→ render text or JSON output
```

Apex may return fewer opportunities when data quality or market conditions are poor. It does not fabricate candidates to fill a quota.

## Analysis model

The default analysis timeframes are:

| Timeframe | Role |
|---|---|
| `1m` | Immediate momentum and timing |
| `3m` | Trigger refinement |
| `5m` | Primary entry structure |
| `15m` | Setup formation |
| `30m` | Intraday context |
| `1h` | Broader trend context |
| `4h` | Macro warning and target context |

Typical analytical inputs include:

- price, spread, quote volume, and participation;
- returns, acceleration, and directional persistence;
- relative volume and volume acceleration;
- ATR percentage and range expansion;
- EMA and VWAP relationships;
- breakout, retest, pullback, and range structure;
- wick behavior, liquidity sweeps, and rejection evidence;
- trend, compression, exhaustion, and noise conditions.

## Strategies

The configured strategy set can include:

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

A symbol may produce several strategy candidates. Apex ranks them deterministically and exposes the strongest candidate while retaining structured alternatives where applicable.

## Candidate statuses

| Status | Meaning |
|---|---|
| `READY_NOW` | Price is inside or immediately adjacent to the preferred entry |
| `AGGRESSIVE_NOW` | Entry is available now with explicit caution |
| `PULLBACK_PREFERRED` | Current entry is usable, but a nearby retracement improves geometry |
| `WATCH_NEAR_ENTRY` | Price is close to becoming actionable |
| `LATE_OR_CHASING` | Direction may remain valid, but current entry quality has deteriorated |
| `INVALIDATED` | The strategy thesis has structurally failed |

`NO_TRADE` is an assessment result rather than an entry status.

## Candidate output

A candidate can include:

- symbol, direction, strategy, and timestamp;
- current price and entry status;
- immediate and preferred entry zones;
- ideal entry and maximum-chase boundary;
- structural invalidation and stop price;
- target levels and reward-to-risk geometry;
- setup, timing, opportunity, and trade-quality scores;
- evidence, cautions, and rejection reasons;
- management guidance such as breakeven, trailing, momentum-failure, or time-exit conditions.

Scores describe analytical quality only. They are not position-size, wallet-risk, leverage, margin, or liquidation recommendations.

## Backtesting

`apex backtest SYMBOL` runs focused chronological replay for one symbol. The retained backtesting engine supports:

- closed-candle chronological simulation;
- explicit entry-touch handling;
- structural stop and target evaluation;
- conservative same-candle ambiguity handling;
- multiple targets and partial closes;
- configurable fees and slippage;
- missed-entry and expiry outcomes;
- deterministic dataset, configuration, and code hashes;
- summary metrics such as win rate, expectancy, profit factor, drawdown, and streaks.

Backtesting evaluates signal geometry. It does not model wallet allocation, leverage, margin, liquidation, funded-account rules, paper-account state, or exchange execution.

## Installation

Requirements:

```text
Python 3.11+
```

```bash
git clone https://github.com/mshahwaiz-ali/apex.git
cd apex
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Inspect the command surface:

```bash
apex --help
```

## Commands

### Scan the market

```bash
apex scan --help
apex scan
```

### Analyze one symbol

```bash
apex analyze BTCUSDT --help
apex analyze BTCUSDT
```

### Validate configuration

```bash
apex config-check --help
apex config-check
```

### Run a focused backtest

```bash
apex backtest BTCUSDT --help
apex backtest BTCUSDT
```

### Show the installed version

```bash
apex version
```

Text and JSON are the supported output modes.
`scan` also supports `--results`, `--shortlist`, and `--direction long|short|both` so operators can keep the broad discovery workflow compact without switching to old modes.

## Configuration

Active configuration is loaded from `config/default.yaml` and organized around Stage 3 sections:

```text
config/
├── default.yaml
├── market_environment.yaml
└── symbols.yaml
```

Configuration controls include:

- screener liquidity, spread, movement, and volatility thresholds;
- shortlist and displayed-result counts;
- analysis timeframes and timeframe roles;
- resampling and data-staleness rules;
- enabled strategies and strategy parameters;
- deterministic scoring and ranking thresholds;
- provider, caching, logging, and runtime behavior.

Validate the resolved configuration with:

```bash
apex config-check
```

## Architecture

```text
src/apex/
├── application/         # Screening, analysis, ranking, and orchestration
├── backtesting/         # Focused chronological signal replay
├── cli_commands/        # Public scan, analyze, config-check, backtest, version commands
├── config/              # Validated discovery configuration
├── data/                # Market-data providers and normalized contracts
├── domain/              # Core market and analysis models
├── features/            # Indicators and reusable market features
├── liquidity/           # Liquidity zones, sweeps, and rejection evidence
├── market_environment/  # Regime and market-state classification
├── presentation/        # Deterministic text and JSON rendering
├── scoring/             # Candidate scoring and ranking
└── strategies/          # Strategy applicability and candidate generation
```

The system favors typed contracts, deterministic behavior, explicit failure reasons, reproducible serialization, and focused chronological testing.

## Development and validation

Before a local validation batch:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate
```

Run formatting and lint fixes first:

```bash
.venv/bin/ruff format <changed-files>
.venv/bin/ruff check <changed-files> --fix
.venv/bin/ruff check <changed-files>
```

Then run scoped mypy, relevant pytest tests, and:

```bash
git diff --check
```

Only report validation results from actual terminal output.
