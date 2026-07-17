<div align="center">

# ⚡ Apex Trading Agent

### Deterministic Binance futures opportunity discovery and wallet-aware trade planning

Apex scans active Binance USDT perpetual markets, finds actionable long and short opportunities near the current price, ranks them transparently, and builds executable risk plans.

**Dynamic universe · Market-wide screening · Multi-timeframe analysis · Strategy ranking · Immediate and preferred entries · Standard and funded risk · Backtesting · Paper tracking**

</div>

---

## What Apex Does

Apex answers one question:

> Which Binance futures opportunities are most actionable near the current market price?

The primary workflow is:

```text
Discover active futures contracts
→ filter unusable markets
→ screen the full eligible universe
→ shortlist the strongest opportunities
→ run detailed multi-timeframe analysis
→ evaluate applicable strategies
→ score and rank candidates
→ build immediate and preferred entries
→ calculate wallet-aware position plans
→ report results in text or JSON
```

Apex is deterministic Python software. Its core trading decisions do not depend on an LLM, and it does not claim guaranteed profitability.

---

## Product Scope

### Active market

```text
Binance USDT perpetual futures
```

Apex supports:

- long and short opportunities;
- scalp, fast-intraday, intraday, and selective short-swing setups;
- entries near the current market price;
- isolated-margin planning;
- structural stops and multiple targets;
- fees, slippage, margin, and liquidation-aware sizing;
- standard-wallet and funded-account constraints;
- chronological backtesting;
- deterministic paper tracking and outcome review.

### Intentionally inactive

The default product surface does not expose:

- spot workflows;
- autonomous optimization or threshold mutation;
- automatic strategy promotion;
- exchange order execution;
- testnet execution;
- old evidence-artifact ceremony;
- development milestone commands.

Spot implementation may remain internally preserved, but Apex is currently futures-first.

---

## How Scanning Works

### 1. Dynamic futures universe

Apex loads current exchange metadata and selects eligible active USDT perpetual contracts.

Eligibility can consider:

- trading status;
- quote and contract type;
- liquidity;
- spread;
- candle availability;
- exchange precision and order filters;
- blacklist and optional allowlist rules.

A static symbol list is only an optional override.

### 2. Lightweight market-wide screening

All eligible contracts receive inexpensive screening before deep analysis.

Typical inputs include:

- price, bid, ask, and spread;
- quote volume and trade participation;
- recent returns and acceleration;
- relative volume and volume acceleration;
- ATR percentage and range expansion;
- directional persistence;
- breakout and structure proximity;
- wick intensity;
- VWAP or EMA distance;
- exhaustion and noise penalties.

Default operating targets are configurable:

```text
Detailed shortlist: 30
Displayed opportunities: 15
```

Apex may show fewer when market data is unavailable or markets are genuinely untradeable. It does not manufacture quality to fill a quota.

### 3. Detailed analysis

Shortlisted symbols receive deeper analysis across:

| Timeframe | Role |
|---|---|
| `1m` | Immediate momentum and execution timing |
| `3m` | Trigger quality and microstructure |
| `5m` | Primary entry structure |
| `15m` | Setup formation and local regime |
| `30m` | Intraday context |
| `1h` | Broader trend and danger context |
| `4h` | Optional macro warning and target context |

Higher-timeframe disagreement normally reduces confidence or target space. It does not automatically erase a valid fast trade.

---

## Strategies

Apex classifies measurable market conditions and evaluates every relevant strategy.

The active strategy set can include:

- momentum breakout;
- breakout continuation;
- breakout retest;
- first pullback continuation;
- trend pullback;
- compression expansion;
- range-edge reversal;
- failed breakout reversal;
- liquidity-rejection reversal;
- VWAP reclaim or rejection;
- momentum scalp;
- exhaustion reversal.

A symbol may produce multiple candidates. The strongest candidate becomes primary while alternatives remain available in structured output.

---

## Scoring and Ranking

Apex separates distinct decision qualities:

```text
opportunity_score
setup_score
timing_score
risk_feasibility_score
final_rank_score
```

Opportunity and setup quality drive ranking. Wallet constraints affect position feasibility and warnings without hiding a genuine market opportunity.

General score interpretation:

| Score | Meaning |
|---:|---|
| `85–100` | Exceptional current opportunity |
| `75–84` | Strong opportunity |
| `65–74` | Valid but aggressive |
| `55–64` | Speculative or developing |
| `<55` | Weak, late, or structurally poor |

Imperfect candidates may remain visible when they are among the best currently available opportunities. Their weaknesses are explicit.

---

## Entry Statuses

| Status | Meaning |
|---|---|
| `READY_NOW` | Price is inside or very near the preferred entry |
| `AGGRESSIVE_NOW` | Entry is available now with meaningful caution |
| `PULLBACK_PREFERRED` | Immediate entry is possible, but a nearby retracement improves geometry |
| `WATCH_NEAR_ENTRY` | Price is close to becoming actionable |
| `LATE_OR_CHASING` | Direction may remain valid, but current entry quality has deteriorated |
| `INVALIDATED` | The strategy thesis has structurally failed |

Where appropriate, Apex returns both:

- an executable market-near entry;
- a preferred pullback entry with better risk-to-reward.

A usable plan may include current price, entry zones, maximum chase boundary, invalidation, stop, three targets, trade horizon, evidence, and cautions.

Liquidity sweeps normally refine evidence, entries, stops, warnings, and scores. They become hard blockers only when the trade thesis has structurally failed.

---

## Risk Planning

Trade discovery and wallet planning are separate stages.

```text
Structural entry
→ structural stop
→ permitted account loss
→ quantity
→ notional
→ required margin
→ sufficient leverage
→ liquidation-safety check
```

Leverage is an output of position planning. It does not improve setup quality.

### Standard profile

For personal trading wallets.

Typical configurable defaults:

```yaml
risk_per_trade_pct: 1.0
max_wallet_margin_pct: 25.0
max_total_open_risk_pct: 3.0
max_daily_loss_pct: 5.0
isolated_margin_only: true
```

### Funded profile

For accounts with daily and total drawdown constraints.

Typical configurable defaults:

```yaml
risk_per_trade_pct: 0.5
max_daily_loss_pct: 5.0
max_total_drawdown_pct: 10.0
max_wallet_margin_pct: 20.0
max_total_open_risk_pct: 2.0
isolated_margin_only: true
```

A risk plan can report:

- maximum modeled loss;
- quantity and notional;
- leverage and required margin;
- wallet margin percentage;
- fees and slippage;
- liquidation estimate;
- stop-to-liquidation buffer;
- target reward and reward-to-risk;
- funded-limit impact.

Actual exchange and funded-provider rules must always be verified.

---

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

Inspect the installed command surface:

```bash
apex --help
```

---

## Commands

Apex uses grouped commands. Run `--help` at any level for the exact current options.

### Futures scanning

```bash
apex futures scan --help
```

Primary market-wide workflow:

```bash
apex futures scan
```

Use command help to configure wallet balance, risk profile, shortlist size, result count, direction, provider settings, and text or JSON output.

### Single-symbol analysis

```bash
apex futures analyze BTCUSDT --help
apex futures analyze BTCUSDT
```

Returns applicable strategies, scores, entries, stops, targets, warnings, and wallet planning for one futures symbol.

### Setup simulation

```bash
apex futures simulate --help
```

Runs deterministic paper simulation for a current setup. It does not place exchange orders.

### Paper workflows

```bash
apex paper --help
```

Use paper commands to intake opportunities, run or schedule lifecycle updates, inspect status, and review recorded outcomes.

### Research and backtesting

```bash
apex research --help
```

Research commands cover chronological backtesting, reproducible campaigns, historical comparisons, dataset work, and manual edge analysis.

### Validation and funded readiness

```bash
apex validation --help
```

Validation commands assess retained paper history, historical stability, and funded-account readiness. They do not authorize live execution.

### Configuration and provider checks

```bash
apex system --help
apex system config --help
apex system check --help
apex system ticker --help
apex system candles --help
```

These commands inspect resolved configuration and verify market-data access.

---

## Output Modes

Active analytical output modes are:

```text
text
json
```

Text output is optimized for terminal use.

JSON output preserves structured candidates, diagnostics, warnings, entry geometry, and risk plans for storage or automation.

---

## Configuration

Current configuration lives under:

```text
config/
├── default.yaml
├── risk.yaml
├── strategies.yaml
└── symbols.yaml
```

Configuration controls include:

- provider and quote asset;
- dynamic-universe rules;
- liquidity and spread thresholds;
- shortlist and result counts;
- analysis timeframes;
- strategy settings;
- scoring weights and penalties;
- Standard and Funded risk limits;
- storage, caching, concurrency, and runtime behavior.

Inspect resolved configuration with:

```bash
apex system config
```

---

## Logging, Paper Tracking, and Manual Review

Apex retains practical diagnostic visibility:

- scan and analysis records;
- discovered and excluded symbols;
- screener features and shortlist reasons;
- strategy candidates and scores;
- entry and risk plans;
- paper trades and outcomes;
- lifecycle and health diagnostics;
- historical and forward-edge evaluation;
- funded plan generation, reporting, and schema inspection.

Apex does not automatically mutate configuration or promote strategies from these records. Logs and outcomes are intended for manual diagnosis and targeted improvements.

---

## Architecture

```text
src/apex/
├── application/         # Screening, analysis, ranking, and orchestration
├── backtesting/         # Chronological simulation and historical analysis
├── cli_commands/        # Active Typer command groups
├── config/              # Validated configuration models and loaders
├── data/                # Provider interfaces and normalized market data
├── features/            # Reusable indicators and market features
├── funded/              # Funded constraints and retained plan tooling
├── liquidity/           # Liquidity zones, sweeps, and rejection evidence
├── market_environment/  # Market-state and regime classification
├── paper_trading/       # Persistent paper lifecycle and outcomes
├── presentation/        # Text and JSON presentation
├── risk/                # Position sizing, margin, leverage, liquidation
├── strategies/          # Strategy applicability and candidate generation
└── validation/          # Historical and forward validation logic
```

The system favors typed contracts, deterministic behavior, explicit failure reasons, reproducible tests, and modular boundaries.

---

## Development and Validation

Before a local batch:

```bash
cd ~/data_drive/apex
git status --short
git pull --rebase origin main
source .venv/bin/activate
```

Run the full quality suite:

```bash
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests --fix
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests
git diff --check
git status --short
```

Only report validation results from actual terminal output.

---

## Limitations

- Apex provides analysis and planning, not guaranteed outcomes.
- Public exchange data can be delayed, incomplete, or temporarily unavailable.
- Thin markets can produce slippage beyond modeled assumptions.
- Stops and liquidation estimates depend on exchange rules and current account state.
- Backtests and paper results do not guarantee future profitability.
- Funded-account rules differ by provider and must be configured accurately.
- Apex does not place live orders.

---

## Documentation

- `docs/new_plan.md` — authoritative final simplification and redesign specification.
- `docs/final_redesign_report.md` — completed redesign summary and retained product inventory.

---

## Disclaimer

Apex is research and decision-support software. Cryptocurrency derivatives involve substantial risk, including rapid losses and liquidation. Verify all data, exchange rules, account constraints, and order parameters before taking any trade.
