# Apex Trading Agent

## Next-Stage Master Plan

**Status:** Approved planning baseline for the next implementation stage  
**Execution environment:** Local development in VS Code on Ubuntu  
**Primary implementation tool:** Codex working locally  
**Repository policy for this stage:** Do not perform GitHub, remote, branch, pull, push, fetch, reset, or PR operations unless the user explicitly asks later.

---

# 1. Purpose of This Stage

Apex already contains a broad deterministic foundation for:

- live multi-timeframe analysis;
- futures setup generation;
- scanner modes;
- entry classification;
- leverage and liquidation-aware sizing;
- partial targets;
- trade lifecycle tracking;
- paper trading;
- chronological backtesting;
- walk-forward calibration;
- reproducible JSONL and SQLite records;
- local testnet simulation and execution-readiness reporting.

The next stage is not another architecture expansion. It is a **trading-quality, risk-policy, validation, and usability stage**.

The objective is to convert Apex into a reliable decision system that can:

1. identify high-quality futures trades for normal funded-account usage;
2. preserve the existing aggressive and extreme modes for controlled testing;
3. introduce a separate, properly designed spot-trading engine;
4. produce exact manual trade-management instructions;
5. measure setup-specific historical performance;
6. reject unproven or unsafe setups;
7. progress from backtesting to forward paper validation before any funded or real-capital use.

---

# 2. Final Product Role

Apex is the decision and guidance layer.

The user remains the manual execution layer.

```text
Apex scans markets
    -> Apex selects or rejects a setup
    -> Apex calculates entry, risk and position size
    -> Apex produces exact execution instructions
    -> User places the trade manually
    -> Apex tracks the setup and updates management guidance
    -> User performs partial exits, stop changes or full exit manually
```

Apex must never assume that a setup is valid merely because indicators agree. Every approved trade must have:

- a clearly defined thesis;
- a specific entry state;
- structural invalidation;
- realistic stop placement;
- target logic;
- position sizing;
- explicit management instructions;
- historical-edge metadata when enough data exists;
- a clear reason why it is eligible for paper, funded, or experimental use.

---

# 3. Risk System: Keep Exactly Three Modes

Apex will retain exactly three risk modes.

No fourth funded-only risk mode will be introduced.

The three modes will be redefined so that they are internally consistent and usable across futures testing and future real operation.

## 3.1 STANDARD

Primary intended use:

- normal trading;
- funded-account evaluation;
- funded-account operation;
- production paper trading;
- baseline backtesting.

Initial target defaults:

```yaml
STANDARD:
  account_loss_percentage: 0.25
  preferred_leverage: 2.0
  maximum_leverage: 5.0
  maximum_wallet_exposure_percentage: 15.0
  maximum_open_risk_percentage: 0.75
  maximum_daily_loss_percentage: 1.0
  maximum_consecutive_losses: 2
```

These are starting values and must remain configurable.

## 3.2 AGGRESSIVE

Primary intended use:

- personal-capital testing;
- high-quality momentum conditions;
- demo and controlled paper trading;
- setups with stronger evidence but wider volatility.

Initial target defaults:

```yaml
AGGRESSIVE:
  account_loss_percentage: 0.75
  preferred_leverage: 5.0
  maximum_leverage: 10.0
  maximum_wallet_exposure_percentage: 25.0
  maximum_open_risk_percentage: 1.5
  maximum_daily_loss_percentage: 2.5
  maximum_consecutive_losses: 3
```

## 3.3 EXTREME

Primary intended use:

- experimental research only;
- demo accounts;
- isolated backtests;
- explicit high-risk scenarios.

It must never be the default mode.

Initial target defaults:

```yaml
EXTREME:
  account_loss_percentage: 2.0
  preferred_leverage: 10.0
  maximum_leverage: 20.0
  maximum_wallet_exposure_percentage: 35.0
  maximum_open_risk_percentage: 3.0
  maximum_daily_loss_percentage: 5.0
  maximum_consecutive_losses: 4
```

## 3.4 Required Risk-System Cleanup

The current generic risk configuration and futures-specific configuration must not contradict each other.

Implement one canonical risk-mode source of truth.

The following rules are mandatory:

- default mode is `STANDARD`;
- leverage may be as low as `1x`;
- no mode may enforce an unnecessary minimum leverage;
- account-loss percentage is the maximum modeled wallet loss, including fees and slippage;
- maximum wallet exposure remains a separate constraint;
- liquidation must remain safely beyond structural stop-loss;
- daily lockout and consecutive-loss lockout must be enforced before setup approval;
- risk configuration used in a decision must be serialized into the analysis record;
- invalid or conflicting configuration must fail validation rather than silently selecting another value.

---

# 4. Funded-Account Rules Without a Fourth Risk Mode

Funded-account constraints belong in an **account-policy layer**, not in a new risk mode.

`STANDARD` remains the risk mode. A funded policy can then apply additional account-level restrictions.

## 4.1 Account Policy Contract

Introduce an account policy model with fields similar to:

```yaml
account_policy:
  type: FUNDED
  provider_name: null
  challenge_phase: null
  initial_balance: 50000.0
  current_balance: 50000.0
  current_equity: 50000.0
  external_daily_drawdown_limit_pct: 5.0
  external_total_drawdown_limit_pct: 10.0
  internal_daily_stop_pct: 1.0
  internal_total_drawdown_buffer_pct: 2.0
  maximum_trades_per_day: 3
  maximum_consecutive_losses: 2
  weekend_trading_allowed: true
  news_trading_allowed: false
  overnight_holding_allowed: true
  required_stop_loss: true
```

## 4.2 Separation of Responsibilities

Risk mode controls:

- risk per trade;
- leverage bounds;
- wallet exposure;
- open-risk limits;
- aggressiveness of approved setups.

Account policy controls:

- firm-specific drawdown rules;
- daily lockout;
- total loss buffer;
- trade-count limits;
- overnight/weekend/news restrictions;
- evaluation-stage restrictions;
- account eligibility.

## 4.3 Funded Eligibility Result

Every approved futures setup should include:

```text
FUNDED_ELIGIBLE
PAPER_ONLY
EXPERIMENTAL_ONLY
REJECTED
```

Eligibility must be based on:

- risk mode;
- account policy;
- setup score;
- strategy type;
- historical sample quality;
- current spread and liquidity;
- daily and total drawdown state;
- open exposure;
- event restrictions;
- data completeness.

---

# 5. Futures Normal Mode

The current futures engine remains the primary short-term trading engine.

The next work is to improve selectivity, management guidance and empirical validation.

## 5.1 Preferred Strategy Order

For `STANDARD` mode, prioritize:

1. trend pullback continuation;
2. breakout retest;
3. liquidity-sweep reversal;
4. validated range-edge reversal;
5. failed-continuation reversal with strong evidence.

The following strategies may remain available but require stricter approval:

- direct breakout continuation;
- momentum expansion;
- raw gainer continuation;
- lower-timeframe countertrend trades.

## 5.2 Strategy-Specific Thresholds

Do not use one global score threshold for every strategy.

Example configuration shape:

```yaml
strategy_approval:
  trend_pullback:
    standard_minimum_score: 74
  breakout_retest:
    standard_minimum_score: 76
  liquidity_reversal:
    standard_minimum_score: 78
  range_reversal:
    standard_minimum_score: 80
  breakout_continuation:
    standard_minimum_score: 84
  momentum_continuation:
    standard_minimum_score: 86
```

Final values must be calibrated from historical and forward-test results.

## 5.3 Entry Quality

Futures output must clearly distinguish:

- `READY_NOW`;
- `RETEST_ENTRY`;
- `RECLAIM_ENTRY`;
- `APPROACHING_ENTRY`;
- `WATCH_ONLY`;
- `MISSED`;
- `INVALIDATED`;
- `NO_TRADE`.

An approved entry must include:

- entry-zone lower and upper bounds;
- current price;
- maximum chase price;
- expected entry type;
- entry expiry;
- invalidation before entry;
- spread condition;
- precision-entry score;
- whether a market or limit entry is preferred.

---

# 6. Exact Manual Trade-Management Guidance

Apex must become operationally clear enough that the user only needs to execute the instructions.

Introduce a canonical `TradeManagementPlan` model.

## 6.1 Required Output Sections

### Entry instruction

- action: enter now, place limit, wait for retest, or reject;
- entry zone;
- maximum chase price;
- order type recommendation;
- entry expiry;
- conditions that cancel the entry.

### Initial protection

- stop-loss price;
- stop type;
- risk percentage;
- risk amount;
- quantity;
- notional;
- margin;
- leverage;
- estimated fees and slippage;
- estimated liquidation price;
- stop-to-liquidation buffer.

### Target ladder

Each target must include:

- target label;
- target price;
- percentage to close;
- cumulative percentage closed;
- expected R multiple;
- rationale.

Target percentages must total 100%, unless an explicitly defined runner remains.

### Stop-management steps

Examples:

- keep original stop after TP1;
- move to breakeven only after a candle-close condition;
- move below/above the latest validated swing;
- activate trailing stop after TP2;
- do not tighten stop during normal volatility.

### Emergency exit rules

Examples:

- structural break against the trade;
- abnormal opposite volume;
- failed reclaim;
- spread expansion;
- invalidating liquidation event;
- market-wide regime reversal;
- account-policy lockout.

### Current action

Every update should contain one unambiguous action:

```text
HOLD
ENTER
DO_NOT_ENTER
PARTIAL_CLOSE
MOVE_STOP
CLOSE_ALL
CANCEL_SETUP
WAIT
```

## 6.2 Lifecycle Integration

The management plan must integrate with the existing lifecycle rather than duplicating it.

Management instructions should generate canonical lifecycle events for:

- entry;
- partial target;
- stop movement;
- breakeven activation;
- runner activation;
- trailing-stop update;
- invalidation;
- cancellation;
- expiry;
- final close.

---

# 7. Spot Trading: Separate Engine, Not Futures Reuse

Spot trading must be designed as a distinct strategy family.

It must not simply run futures logic without leverage.

## 7.1 Spot Objectives

Spot mode will focus on:

- long-only positions initially;
- liquid assets;
- controlled capital allocation;
- holding periods from approximately one day to one week;
- higher-timeframe confirmation;
- buying near favorable value zones;
- avoiding severely extended coins;
- structured scale-in and scale-out plans;
- protection against broad-market weakness.

## 7.2 Accuracy Principle

A 99% win rate cannot be promised or assumed merely because higher timeframes are used.

The design objective is instead:

- extreme selectivity;
- strong higher-timeframe alignment;
- low trade frequency;
- avoidance of weak market regimes;
- high historical precision in approved setup classes;
- preservation of capital when conditions are unclear.

Apex should prefer `NO_TRADE` over approving an unproven spot position.

The system may target very high precision during research, but no accuracy claim should be surfaced until supported by a sufficiently large out-of-sample and forward-test sample.

## 7.3 Initial Spot Timeframes

Recommended initial model:

- `1W`: macro regime and major structure;
- `3D` or `1D`: primary trend and large support/resistance;
- `12h` or `8h`: setup development;
- `4h`: entry structure;
- `1h`: optional execution refinement.

The 1m, 3m and 5m timeframes should not influence the spot thesis.

They may later be used only to reduce entry slippage after a spot setup is already approved.

## 7.4 Spot Market Regime Gate

Before analyzing individual assets, determine the broad market regime using at least:

- BTC higher-timeframe structure;
- BTC volatility and drawdown state;
- major-market breadth;
- stablecoin or market-risk proxy when data is available;
- asset-specific relative strength against BTC and USDT.

Spot setup approval states:

```text
RISK_ON
SELECTIVE_RISK_ON
NEUTRAL
RISK_OFF
CAPITULATION
RECOVERY
```

Initial behavior:

- `RISK_ON`: normal spot candidates allowed;
- `SELECTIVE_RISK_ON`: only strongest assets allowed;
- `NEUTRAL`: reduced allocation or watch only;
- `RISK_OFF`: reject new swing positions;
- `CAPITULATION`: no blind buying; wait for recovery evidence;
- `RECOVERY`: allow structured reversal or reclaim setups.

## 7.5 Spot Symbol Eligibility

Initial symbol filters should include:

- minimum quote volume;
- minimum market age/history;
- acceptable spread;
- reliable candle history;
- no obvious data gaps;
- no terminal vertical extension;
- sufficient average true range for meaningful movement;
- acceptable downside volatility;
- optional exclusion list for unstable or newly listed assets.

## 7.6 Initial Spot Strategy Families

### A. Higher-Timeframe Trend Pullback

Buy a strong asset during a controlled retracement within a valid higher-timeframe uptrend.

Evidence may include:

- weekly/daily bullish structure;
- pullback into a validated demand or moving-average zone;
- momentum reset without bearish structural failure;
- reduced sell volume during pullback;
- bullish 4h recovery or reclaim;
- sufficient space to the next major resistance.

### B. Breakout and Higher-Timeframe Retest

Buy after a meaningful daily or multi-day breakout successfully retests the broken level.

Reject when:

- breakout is already excessively extended;
- volume collapses on retest;
- the retest closes materially below the level;
- BTC regime is risk-off;
- nearest resistance leaves insufficient reward.

### C. Accumulation-Range Breakout

Detect mature accumulation or compression and enter only after a valid breakout/retest sequence.

Requirements may include:

- stable multi-day range;
- volatility contraction;
- constructive volume profile;
- breakout quality;
- retest or hold above range high;
- positive relative strength.

### D. Liquidity Sweep and Daily Recovery

Buy after a meaningful downside sweep followed by higher-timeframe recovery.

This must require more than a wick. It should include:

- sweep of a clear daily/4h liquidity level;
- close back above the level;
- recovery of local structure;
- improving volume or momentum;
- no broad-market collapse.

### E. Relative-Strength Leader Pullback

Identify coins outperforming BTC and the wider market, then wait for a controlled entry.

This strategy should reject assets whose strength is caused only by one terminal pump candle.

### F. Post-Capitulation Recovery

Experimental initially.

Only activate after:

- broad selloff exhaustion;
- reclaim of a major level;
- stabilization across multiple higher-timeframe candles;
- improving market breadth;
- controlled position sizing.

This strategy remains `PAPER_ONLY` until enough evidence exists.

## 7.7 Spot Entry Plan

A spot setup may support:

- single entry;
- two-part scaled entry;
- three-part scaled entry.

Example:

```text
Entry 1: 40% at current approved zone
Entry 2: 35% at deeper support
Entry 3: 25% only after recovery confirmation
```

Scale-in must never become uncontrolled averaging down.

Rules:

- maximum number of planned entries is fixed before entry;
- maximum total capital allocation is fixed;
- invalidation cancels all remaining entries;
- no additional buys outside the original plan;
- position risk must be calculated using total planned exposure.

## 7.8 Spot Exit and Profit-Taking

Spot output should include:

- initial protective stop or structural invalidation;
- TP1, TP2 and optional runner target;
- percentage to sell at each target;
- time-based review condition;
- profit-protection rule;
- market-regime exit condition;
- maximum intended holding period;
- early exit if the original thesis weakens.

Example initial ladder:

```text
TP1: close 25%
TP2: close 35%
TP3: close 25%
Runner: 15% with higher-timeframe trailing logic
```

The percentages are configurable and must be validated through testing.

## 7.9 Spot Position Sizing

Spot mode should support two sizing methods:

### Risk-based sizing

Position size is calculated from entry, structural invalidation and allowed account loss.

### Allocation-capped sizing

Position size is limited to a configured percentage of available capital even when risk-based sizing permits more.

The smaller result wins.

Required constraints:

- maximum allocation per position;
- maximum total spot exposure;
- maximum correlated sector exposure;
- maximum number of simultaneous positions;
- minimum stablecoin reserve;
- no leverage in the initial spot engine.

## 7.10 Spot Setup Output

Every spot analysis must return:

```json
{
  "market_type": "SPOT",
  "decision": "BUY | WATCH | HOLD_EXISTING | REDUCE | SELL | NO_TRADE",
  "market_regime": "SELECTIVE_RISK_ON",
  "strategy": "higher_timeframe_trend_pullback",
  "holding_horizon": "1d_to_7d",
  "entry_plan": {},
  "capital_allocation": {},
  "invalidation": {},
  "take_profit_plan": [],
  "management_plan": [],
  "historical_edge": {},
  "eligibility": "PAPER_ONLY",
  "warnings": []
}
```

---

# 8. Setup-Specific Historical Edge

Apex must stop treating confidence as a single subjective number.

Introduce an `HistoricalEdgeProfile` generated from completed chronological backtests and paper trades.

## 8.1 Segmentation Dimensions

At minimum, group performance by:

- market type: futures or spot;
- strategy;
- direction;
- symbol or symbol class;
- market regime;
- score band;
- entry state;
- volatility regime;
- liquidity/spread band;
- risk mode;
- holding-time band;
- session where relevant.

## 8.2 Required Metrics

```text
sample_size
win_rate
loss_rate
average_r
median_r
expectancy
profit_factor
maximum_drawdown
maximum_losing_streak
average_holding_time
fee_and_slippage_sensitivity
out_of_sample_result
forward_paper_result
```

## 8.3 Evidence Quality States

```text
INSUFFICIENT_SAMPLE
RESEARCH_ONLY
PROMISING
VALIDATED_BACKTEST
VALIDATED_OUT_OF_SAMPLE
VALIDATED_FORWARD_PAPER
PRODUCTION_ELIGIBLE
DEGRADED
REJECTED
```

A high current setup score cannot override insufficient historical evidence for funded eligibility.

---

# 9. Data and Provider Improvements

Do not block the next stage on every possible advanced feed.

## 9.1 Mandatory Data

For futures:

- reliable OHLCV;
- ticker price;
- bid/ask spread where available;
- volume;
- exchange precision filters;
- sufficient multi-timeframe history.

For spot:

- reliable daily and intraday OHLCV;
- ticker and spread;
- quote volume;
- long enough historical coverage;
- BTC and market-regime context.

## 9.2 Useful but Optional Initially

- order-book imbalance;
- funding rate;
- open interest;
- liquidation clusters;
- market breadth;
- sector-relative strength;
- volume profile;
- exchange inflow/outflow data.

Optional data must never be fabricated. Missing values should reduce confidence or disable only the dependent rule.

## 9.3 Provider Interfaces

Add or preserve provider-independent contracts for:

- spot and futures market metadata;
- funding rate;
- open interest;
- market breadth;
- relative-strength data;
- optional liquidation clusters.

Implementation can proceed with deterministic fixtures before external live providers are connected.

---

# 10. Backtesting Requirements

Architecture is not proof of profitability.

The next stage must produce empirical baselines.

## 10.1 Curated Dataset Program

Create reproducible datasets for:

- BTC/USDT;
- ETH/USDT;
- several large-cap altcoins;
- selected liquid mid-cap assets;
- bullish, bearish, ranging and chaotic periods;
- futures short-term setups;
- spot swing setups.

Each dataset must record:

- provider;
- symbol;
- market type;
- timeframe;
- start/end timestamps;
- extraction timestamp;
- candle count;
- completeness checks;
- stable content hash.

## 10.2 Futures Backtesting

Run chronological campaigns across:

- each strategy independently;
- combined strategy routing;
- each risk mode;
- score bands;
- symbol groups;
- volatility regimes;
- different entry states;
- realistic fees and slippage.

## 10.3 Spot Backtesting

Spot backtesting requires a separate simulator that supports:

- long-only entries;
- scaled entries;
- partial exits;
- multi-day holding;
- overnight gaps between candles;
- time-based expiry;
- higher-timeframe stop movement;
- market-regime exits;
- capital-allocation limits;
- multiple concurrent positions;
- portfolio-level exposure.

## 10.4 Data Separation

Every experiment must separate:

1. development/train period;
2. validation period;
3. untouched out-of-sample test period;
4. forward paper-trading period.

Do not choose settings using the final test period.

## 10.5 Minimum Sample Policy

Initial policy:

- below 30 trades: insufficient;
- 30-99 trades: research only;
- 100-249 trades: preliminary evidence;
- 250+ trades across multiple regimes: stronger evidence;
- production eligibility also requires out-of-sample and forward-paper stability.

These thresholds may later be made strategy-specific.

---

# 11. Forward Paper-Trading Program

Backtesting must be followed by live forward paper testing.

## 11.1 Futures Paper Track

Track:

- generated setup;
- actual entry availability;
- missed entries;
- spread and slippage at signal time;
- partial targets;
- manual-management instructions;
- final outcome;
- deviation from backtest assumptions.

## 11.2 Spot Paper Track

Track:

- setup date;
- planned entry ladder;
- actual fills;
- capital allocation;
- daily management decisions;
- maximum favorable and adverse excursion;
- exit reason;
- final return and R multiple;
- holding duration;
- broad-market regime changes.

## 11.3 Validation Duration

Do not use time alone as the gate.

Require both:

- a meaningful elapsed period across varying conditions;
- a minimum number of completed trades per strategy.

A practical first checkpoint may be 4-8 weeks, but insufficient trade samples must extend the validation period.

---

# 12. User-Facing Reports

Reports should be actionable, not just technical dumps.

## 12.1 Analysis Report

Show:

- decision;
- market type;
- strategy;
- entry state;
- current action;
- entry zone;
- stop;
- target ladder;
- exact percentages;
- position size;
- leverage or allocation;
- invalidation;
- management steps;
- eligibility;
- historical edge;
- warnings.

## 12.2 Open Trade Report

Show:

- current price;
- unrealized result;
- realized result;
- remaining quantity;
- completed targets;
- active stop;
- next trigger;
- current action;
- thesis status: valid, weakening or invalidated;
- account-policy state.

## 12.3 Daily Risk Report

Show:

- starting equity;
- current equity;
- realized daily PnL;
- open risk;
- daily drawdown used;
- remaining internal risk budget;
- consecutive losses;
- trading status: enabled or locked;
- reason for lockout.

## 12.4 Performance Report

Separate:

- futures and spot;
- paper and backtest;
- strategy;
- risk mode;
- symbol group;
- market regime;
- score band;
- eligible versus rejected setups.

---

# 13. Implementation Sequence

The work should proceed in small, testable phases.

## Phase N1 - Risk Consolidation and Account Policy

Deliverables:

- keep exactly `STANDARD`, `AGGRESSIVE`, `EXTREME`;
- change default to `STANDARD`;
- remove forced high minimum leverage;
- create one canonical risk-mode configuration source;
- add account-policy models and validation;
- add daily and total drawdown state;
- add consecutive-loss and trade-count lockouts;
- add funded eligibility result;
- serialize active policy and risk decisions.

Acceptance criteria:

- no contradiction between risk configuration files;
- 1x leverage is valid when appropriate;
- unsafe manual leverage is rejected;
- lockouts prevent approval;
- existing futures behavior remains compatible where policy does not restrict it;
- all tests, linting and strict typing pass.

## Phase N2 - Canonical Trade Management Plan

Deliverables:

- `TradeManagementPlan` domain model;
- exact entry instructions;
- target percentages;
- breakeven rules;
- stop movement rules;
- emergency exit rules;
- current-action field;
- lifecycle integration;
- text and JSON serialization.

Acceptance criteria:

- target allocation validates;
- management actions are direction-aware;
- no contradictory actions are emitted;
- lifecycle replay reproduces management state;
- approved setups always provide complete instructions.

## Phase N3 - Futures Standard-Mode Quality Pass

Deliverables:

- strategy-specific thresholds;
- breakout-retest strategy if not already distinct;
- stricter direct-breakout and momentum rules;
- setup-specific eligibility;
- improved rejection explanations;
- funded-policy routing.

Acceptance criteria:

- standard mode prefers controlled setups;
- aggressive and extreme modes remain available;
- strategy routing is deterministic and tested;
- rejected setups expose exact reasons.

## Phase S1 - Spot Domain and Configuration Foundation

Deliverables:

- separate spot domain models;
- spot configuration;
- spot decision enum;
- spot market-regime model;
- symbol eligibility;
- spot allocation and risk contracts;
- spot scanner mode;
- provider-independent data contracts.

Acceptance criteria:

- no futures leverage or short assumptions leak into spot;
- spot is long-only initially;
- configuration validates;
- deterministic unit tests pass.

## Phase S2 - Spot Feature, Structure and Regime Engine

Deliverables:

- weekly/daily/12h/8h/4h analysis;
- higher-timeframe trend and range classification;
- relative-strength features;
- broad-market regime gate;
- extension and downside-risk detection;
- support, resistance and demand-zone logic.

Acceptance criteria:

- spot analysis works without low-timeframe dependencies;
- risk-off regime blocks new entries;
- terminal extensions are rejected;
- fixture scenarios produce expected results.

## Phase S3 - Initial Spot Strategies

Implement in this order:

1. higher-timeframe trend pullback;
2. breakout and retest;
3. accumulation-range breakout;
4. liquidity sweep and daily recovery;
5. relative-strength leader pullback;
6. post-capitulation recovery as experimental.

Acceptance criteria:

- each strategy is independently testable;
- every candidate provides thesis and invalidation;
- strategy does not perform position sizing;
- experimental strategy remains paper-only.

## Phase S4 - Spot Entry, Allocation and Exit Engine

Deliverables:

- single and scaled entries;
- allocation-capped risk sizing;
- portfolio exposure limits;
- target ladder;
- runner management;
- time-based review and expiry;
- market-regime exits;
- spot trade lifecycle.

Acceptance criteria:

- no uncontrolled averaging down;
- total allocation is bounded;
- planned entries cannot exceed approved exposure;
- target percentages and runner state validate;
- lifecycle replay is deterministic.

## Phase V1 - Historical Edge and Dataset Pipeline

Deliverables:

- dataset metadata and hashes;
- curated futures and spot datasets;
- historical-edge aggregation;
- evidence-quality states;
- setup-specific metrics;
- report serialization and SQLite storage.

Acceptance criteria:

- results are reproducible;
- train/validation/test splits are explicit;
- insufficient samples are clearly labeled;
- no final-test leakage.

## Phase V2 - Futures and Spot Baseline Campaigns

Deliverables:

- futures campaigns by strategy and mode;
- spot long-only portfolio backtester;
- fee/slippage sensitivity;
- score-band analysis;
- regime analysis;
- baseline reports.

Acceptance criteria:

- results include expectancy and drawdown, not only win rate;
- portfolio exposure is modeled for spot;
- weak strategies are rejected or restricted;
- baseline is frozen for future comparison.

## Phase V3 - Walk-Forward Calibration

Deliverables:

- calibration candidates;
- train and validation comparisons;
- untouched final-test evaluation;
- stability checks across symbols and regimes;
- accepted/rejected parameter-change reports.

Acceptance criteria:

- no parameter is selected from final-test results;
- improvements must preserve or improve expectancy and drawdown;
- unstable one-symbol improvements are rejected.

## Phase P1 - Forward Paper Validation

Deliverables:

- continuous futures paper operation;
- continuous spot paper operation;
- daily reports;
- lifecycle audit;
- backtest-versus-live deviation reports;
- production-eligibility review.

Acceptance criteria:

- minimum strategy samples achieved;
- forward results remain reasonably consistent with modeled results;
- no critical lifecycle or risk-control failures;
- execution instructions are usable manually.

## Phase R1 - Funded Account Readiness

This phase begins only after validation.

Deliverables:

- provider-specific funded-policy preset;
- actual account limits;
- daily lockout and total-buffer verification;
- standard-mode-only enforcement;
- manual execution checklist;
- kill switch;
- pre-trade and post-trade audit.

No real-money autonomous execution is required.

---

# 14. Testing Requirements

Every implementation batch must add or update tests.

## 14.1 Risk and Policy Tests

- exactly three risk modes;
- default standard mode;
- low-leverage acceptance;
- unsafe leverage rejection;
- daily loss lock;
- total drawdown lock;
- consecutive-loss lock;
- trade-count lock;
- open-risk limit;
- funded eligibility.

## 14.2 Management Tests

- target percentages total correctly;
- runner handling;
- breakeven trigger;
- stop movement;
- emergency close;
- invalidation before entry;
- no action contradiction;
- lifecycle replay.

## 14.3 Spot Tests

- long-only invariant;
- risk-off rejection;
- scaled-entry limits;
- no unplanned averaging;
- allocation caps;
- stablecoin reserve;
- portfolio exposure;
- strategy fixtures;
- target and time-based exits;
- multi-day simulation.

## 14.4 Backtesting Tests

- no lookahead;
- intrabar ambiguity handled conservatively;
- data split isolation;
- reproducible IDs;
- partial fills;
- fees and slippage;
- portfolio-level spot exposure;
- historical-edge aggregation.

---

# 15. Quality Gates for Every Local Implementation Batch

Run locally:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest --cov=apex --cov-report=term-missing
git diff --check
```

Also run focused tests for the modules changed before the full gate.

Do not claim completion unless:

- relevant focused tests pass;
- full tests pass;
- lint passes;
- formatting passes;
- strict typing passes;
- documentation reflects actual behavior;
- no unimplemented behavior is described as complete.

---

# 16. Local Development Instructions for Codex

Codex should operate only in the existing local checkout.

For this stage:

- inspect the current architecture before editing;
- preserve existing working behavior;
- implement one phase at a time;
- keep modules small and domain-focused;
- update or add tests with every behavior change;
- update this plan or implementation-progress documentation when behavior changes;
- do not use GitHub tools;
- do not fetch, pull, push, reset, create branches, open pull requests or perform remote operations;
- do not modify unrelated files;
- do not introduce paid services or mandatory external APIs;
- use deterministic fixtures for optional data integrations;
- do not add real-money exchange execution;
- keep all secrets out of source control and logs.

At the end of each phase, Codex should report:

- files changed;
- behavior added or modified;
- tests added;
- focused validation results;
- full validation results;
- known limitations;
- exact next recommended phase.

---

# 17. Explicit Non-Goals for This Stage

Do not add:

- a fourth risk mode;
- guaranteed win-rate claims;
- martingale sizing;
- uncontrolled averaging down;
- autonomous real-money trading;
- paid LLM dependency;
- heavy web frameworks;
- a mobile app;
- social sentiment scraping;
- unvalidated machine-learning ranking;
- unnecessary infrastructure;
- speculative indicators without measurable tests.

---

# 18. Definition of Success

This stage is successful when Apex can demonstrate all of the following:

## Futures

- standard mode is safe enough for funded-account testing;
- aggressive and extreme remain isolated and explicit;
- every trade includes exact manual instructions;
- risk and policy lockouts are enforced;
- strategies have setup-specific historical evidence;
- backtest and forward-paper results are measurable and reproducible.

## Spot

- spot is a separate long-only higher-timeframe engine;
- market regime controls entry eligibility;
- entries, allocations and exits are fully planned;
- one-day to one-week positions can be simulated and tracked;
- capital exposure is controlled at portfolio level;
- high selectivity is measured rather than assumed.

## Validation

- historical datasets are curated;
- train, validation and final-test periods are isolated;
- forward paper trading confirms operational behavior;
- production eligibility is based on evidence;
- no real-capital step is taken merely because the software is feature-complete.

---

# 19. Immediate Next Step

Start with:

## Phase N1 - Risk Consolidation and Account Policy

Do not begin spot implementation until N1 and N2 are stable, because both futures and spot will depend on the same clean risk, account-policy and trade-management foundations.

After N1 and N2:

1. complete the futures standard-mode quality pass;
2. build the separate spot foundation;
3. implement spot strategies incrementally;
4. build curated datasets;
5. run baseline campaigns;
6. calibrate without leakage;
7. run forward paper validation;
8. only then evaluate funded-account readiness.

---

# 20. Final Direction

Apex is no longer defined only as an aggressive futures opportunity engine.

It is becoming a two-track deterministic trading system:

```text
Apex Futures
- short-term long and short setups
- three risk modes
- standard mode for funded-account operation
- exact leverage, stop, target and lifecycle guidance

Apex Spot
- long-only higher-timeframe swing setups
- one-day to one-week holding horizon
- market-regime and portfolio-allocation controls
- structured entries, exits and capital preservation
```

The target is not maximum trade frequency or an unsupported accuracy claim.

The target is the strongest repeatable combination of:

- selectivity;
- accuracy;
- expectancy;
- controlled drawdown;
- clear execution guidance;
- reproducibility;
- operational discipline.
