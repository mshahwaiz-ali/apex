<div align="center">

# ⚡ Apex Trading Agent

### Deterministic Binance futures opportunity discovery and trade planning

Apex scans active Binance USDT perpetual markets, identifies near-current-price long and short opportunities, ranks them with transparent scoring, and builds wallet-aware execution plans.

**Dynamic futures universe · Market-wide screening · Multi-timeframe analysis · Strategy ranking · Structured entries · Risk planning · Backtesting · Paper tracking**

</div>

---

## What Apex Does

Apex answers one practical question:

> Which Binance futures opportunities are most actionable near the current market price?

The system:

1. discovers eligible active futures contracts;
2. applies lightweight market-wide screening;
3. shortlists the strongest current opportunities;
4. performs detailed multi-timeframe analysis;
5. evaluates applicable strategies;
6. scores and ranks usable candidates;
7. builds immediate and preferred entry plans;
8. calculates wallet-aware risk, size, margin, and leverage;
9. reports evidence, cautions, and failures in text or JSON;
10. optionally records paper outcomes for later manual review.

Apex is deterministic Python software. It does not depend on an LLM for core trading decisions and does not claim guaranteed profitability.

---

## Product Scope

### Primary market

```text
Binance USDT perpetual futures
```

Apex is designed for:

- long and short opportunities;
- scalp, fast-intraday, intraday, and selective short-swing setups;
- entries near the current price;
- isolated-margin planning;
- structural stops and targets;
- fees, slippage, margin, and liquidation-aware risk;
- standard personal-wallet and funded-account constraints.

### Inactive surfaces

The default interface does not expose:

- spot trading workflows;
- autonomous threshold mutation;
- automatic strategy promotion;
- exchange order execution;
- testnet execution;
- hidden research compatibility commands.

Preserved internal modules may remain available for controlled research or later removal, but they are not part of the active product surface.

---

## Core Workflow

```text
Active Binance futures contracts
        ↓
Contract and liquidity eligibility
        ↓
Lightweight market-wide screening
        ↓
Detailed shortlist
        ↓
Multi-timeframe feature and structure analysis
        ↓
Market-state classification
        ↓
Applicable strategy evaluation
        ↓
Candidate scoring and ranking
        ↓
Immediate and preferred entry construction
        ↓
Warnings and cautions
        ↓
Wallet-aware risk planning
        ↓
Ranked text or JSON output
```

Each symbol is analyzed once through the primary discovery pipeline. Market movement, acceleration, relative volume, volatility, liquidity, spread, structure proximity, and entry freshness influence ranking without routing symbols through a separate gainer product mode.

---

## Analysis Timeframes

| Timeframe | Role |
|---|---|
| `1m` | Immediate momentum and execution timing |
| `3m` | Trigger quality and microstructure |
| `5m` | Primary entry structure |
| `15m` | Setup formation and local regime |
| `30m` | Intraday context |
| `1h` | Broader trend and danger context |
| `4h` | Optional macro warning and target context |

Higher-timeframe disagreement can reduce confidence or limit targets, but it does not automatically erase a valid fast trade.

---

## Opportunity Screening

The market-wide screener uses inexpensive public market data to determine which contracts deserve detailed analysis.

Typical screening inputs include:

- current price, bid, ask, and spread;
- quote volume and trade participation;
- recent returns and acceleration;
- relative volume and volume acceleration;
- ATR percentage and range expansion;
- directional persistence;
- breakout and structure proximity;
- wick intensity;
- short EMA or VWAP distance;
- liquidity and execution quality;
- extension, exhaustion, and noise penalties.

The screener produces a transparent opportunity score and selects a configurable shortlist for deeper analysis.

Default operating targets:

```text
Eligible universe: all suitable active contracts
Detailed shortlist: 30
Displayed opportunities: 15
```

The scanner may show fewer results when market data fails or contracts are genuinely unsuitable. It does not fabricate trade quality to fill a quota.

---

## Market States and Strategies

Apex classifies measurable market conditions rather than forcing each symbol into a single product category.

Possible conditions include:

- directional trend;
- momentum expansion;
- controlled pullback;
- breakout attempt or confirmation;
- breakout retest;
- compression;
- stable range;
- range-edge rejection;
- failed breakout;
- liquidity rejection;
- exhaustion;
- chaotic volatility;
- low-participation drift.

Applicable strategies may include:

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

A symbol may produce multiple candidates. The best candidate becomes primary while alternatives remain available in structured diagnostics and JSON.

---

## Scoring

Apex separates different qualities instead of collapsing the entire decision into one approval flag.

Each ranked candidate can expose:

```text
opportunity_score
setup_score
timing_score
risk_feasibility_score
final_rank_score
```

The final rank emphasizes market opportunity and setup quality. Risk feasibility affects planning and warnings, but a wallet constraint does not erase a real market opportunity.

General interpretation:

| Score | Meaning |
|---:|---|
| `85–100` | Exceptional current opportunity |
| `75–84` | Strong opportunity |
| `65–74` | Valid but aggressive |
| `55–64` | Speculative or developing |
| `<55` | Weak, late, or structurally poor |

Lower-scoring candidates may still appear when they are among the best currently available opportunities. Their weaknesses remain explicit.

---

## Entry Statuses

Usable candidates are described with action-oriented statuses:

| Status | Meaning |
|---|---|
| `READY_NOW` | Current price is inside or very near the preferred entry |
| `AGGRESSIVE_NOW` | Entry is available now with meaningful caution |
| `PULLBACK_PREFERRED` | Immediate entry is possible, but a nearby retracement improves geometry |
| `WATCH_NEAR_ENTRY` | Price is close to becoming actionable |
| `LATE_OR_CHASING` | Direction may remain valid, but current entry quality has deteriorated |
| `INVALIDATED` | The strategy thesis has structurally failed |

Where appropriate, Apex returns both:

- an executable market-near entry;
- a preferred pullback entry with improved risk-to-reward.

Every usable plan can include:

- current price;
- immediate entry;
- preferred entry zone;
- maximum chase boundary;
- structural invalidation;
- stop-loss;
- conservative, primary, and extended targets;
- expected trade horizon;
- key evidence;
- cautions and warnings.

Liquidity sweeps normally refine evidence, warnings, entries, stops, and scores. They become hard blockers only when the underlying trade thesis has already failed.

---

## Risk Planning

Trade discovery and wallet planning are separate stages.

Apex first determines:

```text
structural entry
→ structural stop
→ permitted wallet loss
→ quantity
→ notional
→ required margin
→ sufficient leverage
→ liquidation safety
```

Leverage is an output of position planning. It does not improve a setup score.

### Standard profile

Designed for a personal trading wallet.

Typical configurable defaults:

```yaml
risk_per_trade_pct: 1.0
max_wallet_margin_pct: 25.0
max_total_open_risk_pct: 3.0
max_daily_loss_pct: 5.0
isolated_margin_only: true
```

### Funded profile

Designed for accounts with firm-style daily and total drawdown limits.

Typical configurable defaults:

```yaml
risk_per_trade_pct: 0.5
max_daily_loss_pct: 5.0
max_total_drawdown_pct: 10.0
max_wallet_margin_pct: 20.0
max_total_open_risk_pct: 2.0
isolated_margin_only: true
```

Risk output may include:

- wallet balance and profile;
- account risk percentage;
- maximum modeled loss;
- stop distance;
- quantity and notional;
- leverage and required margin;
- wallet margin percentage;
- fee and slippage allowance;
- liquidation estimate;
- stop-to-liquidation buffer;
- target rewards and reward-to-risk;
- funded-limit impact.

Actual funded-provider rules must be verified before relying on a funded plan.

---

## CLI

Install the project in the active virtual environment, then inspect the top-level workflows:

```bash
apex --help
```

### Scan futures markets

```bash
apex futures scan --help
```

This is the primary workflow for market-wide discovery, screening, detailed analysis, and ranked opportunity output.

### Analyze one futures market

```bash
apex futures analyze BTCUSDT --help
```

This shows applicable strategies, candidate scores, entries, stops, targets, warnings, and risk planning for one symbol.

### Simulate the current setup

```bash
apex futures simulate --help
```

This paper-simulates a currently approved setup without placing an exchange order.

### Paper tracking

```bash
apex paper --help
```

Paper workflows record opportunities and advance deterministic trade lifecycle state.

### Backtesting and research

```bash
apex research --help
```

The research group provides chronological backtesting, reproducible campaigns, comparison, historical edge analysis, validation, and dataset export.

### Validation

```bash
apex validation --help
```

Validation workflows review completed paper evidence, historical stability, and funded-account constraints. Validation artifacts do not authorize exchange execution.

### Configuration and system checks

```bash
apex system config --help
apex system check --help
apex system ticker --help
apex system candles --help
```

---

## Output Modes

Active command output modes are:

```text
text
json
```

Text output is designed for direct terminal use and includes useful diagnostics by default.

JSON output preserves structured payloads for automation, storage, testing, and manual analysis.

---

## Configuration

Apex uses validated YAML and environment-based configuration.

Current configuration areas include:

```text
config/
├── default.yaml
├── risk.yaml
├── strategies.yaml
└── symbols.yaml
```

The configured symbol file is an optional override. Dynamic futures-universe discovery is the primary live-scanning source when enabled.

Configuration controls include:

- provider and quote asset;
- universe eligibility and exclusions;
- liquidity and spread limits;
- shortlist and result counts;
- analysis timeframes;
- enabled strategies and thresholds;
- scoring weights and penalties;
- Standard and Funded risk limits;
- caching, persistence, and runtime behavior.

Validate resolved settings with:

```bash
apex system config
```

---

## Development Setup

Requirements:

```text
Python 3.11+
```

Create and activate the virtual environment, then install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the quality suite:

```bash
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests --fix
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests
git diff --check
git status --short
```

Validation results should be reported only from actual command output.

---

## Architecture

Apex uses a modular `src` layout.

```text
src/apex/
├── application/       # Analysis, screening, ranking, and orchestration
├── backtesting/       # Chronological simulation and historical analysis
├── data/              # Provider abstractions and normalized market data
├── features/          # Reusable indicators and market features
├── liquidity/         # Liquidity zones, sweeps, and rejection evidence
├── market_environment/# Market condition and regime classification
├── paper_trading/     # Persistent paper lifecycle and outcome tracking
├── presentation/      # Text presentation for canonical payloads
├── risk/              # Stops, sizing, leverage, margin, and account controls
├── scoring/           # Candidate scoring, conflicts, and ranking
├── strategies/        # Independent long and short candidate generators
└── structure/         # Swings, ranges, trends, and structural events
```

Important boundaries:

- providers collect and normalize data;
- feature and structure modules interpret markets;
- strategies generate candidates;
- scoring ranks candidates;
- entry logic builds actionable plans;
- risk logic sizes and validates wallet feasibility;
- presentation renders existing payloads without recomputing decisions;
- paper and backtesting workflows consume the same deterministic analysis contracts.

---

## Logging and Review

Apex can preserve:

- discovered and excluded contracts;
- screener features;
- shortlisted symbols;
- strategy candidates;
- scores and selected candidates;
- entry and risk plans;
- provider failures;
- warnings;
- configuration identity;
- paper outcomes and lifecycle transitions.

These records support reproducible backtesting and manual diagnosis. Apex does not automatically rewrite production configuration from historical outcomes.

---

## Safety and Limitations

Apex is analytical software, not a guarantee of profit.

Important limitations:

- market data may be delayed, incomplete, or unavailable;
- simulated fills differ from live exchange execution;
- fees, slippage, funding, and liquidation estimates are models;
- high leverage can produce rapid losses;
- low-liquidity markets can gap through expected prices;
- historical and paper performance may not continue;
- funded-provider rules can change;
- no active Apex command authorizes unrestricted real-money execution.

Use isolated risk, independently verify exchange rules, and never risk capital that cannot be lost.

---

## License

Proprietary. All rights reserved.
