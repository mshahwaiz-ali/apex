# Apex Trading Agent — Engineering Completion and Validation Plan

## Project Context

Repository:

```text
mshahwaiz-ali/apex
```

Primary branch:

```text
main
```

Apex is a deterministic Python-based crypto market analysis system. The repository already contains implementations or foundations for:

* Market-data providers
* Multi-timeframe analysis
* Technical indicators
* Market structure
* Liquidity analysis
* Strategy generation
* Candidate scoring
* Risk management
* Scanner
* Backtesting primitives
* Paper trading
* Optimization contracts
* Optional intelligence
* Simulated testnet execution safety
* CLI commands
* Automated tests
* CI configuration

The goal of this work is not to rewrite the project from scratch.

The goal is to audit, correct, complete, strengthen, and validate the existing implementation so that Apex becomes a reliable aggressive crypto opportunity engine.

Apex should search actively for near-current-price setups rather than behaving like an excessively conservative confirmation bot.

Aggressive does not mean random.

Every valid setup must still have:

* A clear market thesis
* Logical invalidation
* Defined entry zone
* Structural stop-loss
* Realistic targets
* Controlled account risk
* Acceptable liquidation distance
* Explainable scoring
* Reproducible evidence

---

# 1. Important Scope Instructions

## 1.1 README is on hold

Do not update or rewrite `README.md` in this task.

The README will be handled separately after the implementation is stable.

Documentation files may only be added or updated when they are specifically required for:

* Architecture decisions
* Backtesting methodology
* Validation reports
* Data schemas
* Operational runbooks
* Development handoff notes

Do not spend time polishing the README.

## 1.2 Preserve existing functionality

Do not remove existing working functionality merely to simplify implementation.

Before refactoring:

1. Understand the existing module
2. Inspect its tests
3. Identify its public API
4. Preserve compatible behavior
5. Add regression coverage
6. Make the smallest clean structural improvement

## 1.3 Do not claim profitability

Do not label Apex profitable, production-ready, execution-ready, or validated unless actual test evidence supports that claim.

The current task is to complete the engineering and validation framework.

## 1.4 Main branch workflow

Work directly on:

```text
main
```

Do not create unnecessary branches.

Keep commits focused and logically separated.

## 1.5 No real-money execution

Do not implement or enable real-money exchange execution.

Mainnet credentials, endpoints, order submission, or account access must remain unsupported.

Testnet support may be implemented only behind explicit safety controls.

---

# 2. Required First Step — Full Repository Audit

Before modifying code, inspect the full repository and produce a concise internal implementation map.

Inspect at minimum:

```text
pyproject.toml
config/
src/apex/
tests/
scripts/
docs/
.github/workflows/
```

Determine:

* Which roadmap phases are actually implemented
* Which modules are only contracts or skeletons
* Which CLI commands are functional
* Which CLI commands only simulate behavior
* Which modules have tests
* Which major code paths lack tests
* Whether lint, formatting, typing, and tests currently pass
* Whether imports and architecture boundaries are clean
* Whether configuration fields are actually used
* Whether committed docs accurately describe implementation status
* Whether hidden placeholders, TODOs, stubs, or fake implementations exist

Search for:

```text
TODO
FIXME
NotImplementedError
pass
placeholder
mock
stub
temporary
phase
testnet
simulated
```

Do not assume that a commit message such as “Phase 12 complete” means the phase is operationally complete.

---

# 3. Timeframe Architecture

## 3.1 Required timeframe hierarchy

Apex currently uses:

```text
4h   → macro context
1h   → intermediate context
30m  → intraday context
15m  → primary setup
5m   → entry
3m   → refinement
1m   → timing
```

Extend the system to support higher timeframes as optional contextual inputs.

Recommended full hierarchy:

```text
1W   → long-term macro regime
3D   → broad swing regime
1D   → daily market structure
12h  → swing transition context
8h   → optional intermediate macro context
6h   → optional intermediate macro context
4h   → primary macro context
2h   → transition context
1h   → intermediate trend
30m  → intraday structure
15m  → primary setup
5m   → entry structure
3m   → entry refinement
1m   → execution timing
```

Not every provider supports all native timeframes.

Therefore:

* Native timeframes should be used where available
* Unsupported higher timeframes may be deterministically resampled from lower candles
* Resampling must preserve OHLCV correctness
* Resampled candles must be marked with their source timeframe
* Partial higher-timeframe candles must be marked as active
* No lookahead may be introduced during resampling

## 3.2 Timeframe roles must be configurable

Do not hardcode the entire role mapping inside orchestration code.

Create a configuration-driven timeframe-role system.

Example roles:

```text
LONG_TERM_MACRO
MACRO
SWING
INTERMEDIATE
INTRADAY
SETUP
ENTRY
REFINEMENT
TIMING
```

Configuration should control:

* Enabled timeframes
* Role
* Weight
* Minimum candle count
* Whether active candles may be used
* Maximum allowed data staleness
* Resampling source
* Required versus optional status

## 3.3 Higher timeframes provide context, not forced agreement

Do not require perfect alignment across all timeframes.

The system should distinguish:

* Full alignment
* Strong partial alignment
* Lower-timeframe continuation
* Lower-timeframe countertrend scalp
* Higher-timeframe reversal
* Transition regime
* Severe contradiction

A valid aggressive setup may trade against a higher timeframe when:

* It is explicitly classified as countertrend
* Risk is reduced
* Target expectations are reduced
* The setup score reflects the conflict
* Strong liquidity or reversal evidence exists
* The stop is structurally valid

---

# 4. Market Data Improvements

## 4.1 Separate analysis price from live price

Do not treat the latest closed candle close as the universal current price.

Introduce explicit fields such as:

```text
latest_closed_price
active_candle_price
ticker_price
mark_price
index_price
analysis_price
```

Rules:

* Stable indicators use closed candles by default
* Live entry and chase calculations use ticker or active-candle price
* Derivatives liquidation calculations should prefer mark price
* Output must clearly state which price was used

## 4.2 Data freshness

Add configurable staleness validation by timeframe.

Examples:

* 1m data should not be several minutes stale
* 15m data may tolerate a larger delay
* 1D data may tolerate much more delay

Each timeframe analysis should expose:

```text
last_closed_at
last_received_at
staleness_seconds
is_stale
data_confidence
```

## 4.3 Data quality validation

Ensure detection and tests exist for:

* Missing candles
* Duplicate timestamps
* Out-of-order candles
* Invalid OHLC relationships
* Negative volume
* Zero price
* Timestamp interval mismatch
* Excessive gaps
* Provider clock drift
* Active candle incorrectly marked closed
* Closed candle incorrectly marked active
* Incomplete resampled candles

## 4.4 Provider retry and rate-limit behavior

Implement or verify:

* Exponential backoff
* Maximum retry count
* Request timeout
* Rate-limit handling
* Provider-specific error normalization
* Failure isolation
* Cache reuse
* Safe concurrency

Do not retry configuration or validation failures.

---

# 5. Indicator and Feature Engine

Audit the current feature registry and ensure that every feature has:

* Explicit required candle count
* Stable output length
* Missing-value behavior
* Finite-number validation
* Unit tests
* No lookahead
* Documented units
* Parameter configuration

## 5.1 Trend indicators

Implement or verify:

* EMA 9
* EMA 20
* EMA 21
* EMA 50
* EMA 100
* EMA 200
* SMA 20
* SMA 50
* SMA 200
* EMA slope
* Distance from EMA
* EMA separation
* EMA compression
* EMA expansion
* Trend persistence
* ADX
* Directional movement `+DI/-DI`
* Supertrend as an optional feature
* Linear-regression slope
* Higher-timeframe trend strength

Do not incorrectly label two same-period averages as “fast” and “slow”.

Use explicit names such as:

```text
ema_20
ema_50
ema_200
sma_20
```

## 5.2 Momentum indicators

Implement or verify:

* RSI
* RSI slope
* RSI regime
* RSI divergence candidates
* Stochastic RSI
* MACD line
* MACD signal
* MACD histogram
* MACD histogram slope
* Rate of change
* Momentum acceleration
* Consecutive directional closes
* Candle body momentum
* Williams %R as optional
* CCI as optional

Indicators should not create trades alone.

They provide evidence for structure and strategy logic.

## 5.3 Volatility indicators

Implement or verify:

* ATR
* ATR percentage
* Normalized ATR
* ATR percentile
* Bollinger Bands
* Bollinger Band width
* Bollinger bandwidth percentile
* Keltner Channels
* Squeeze condition
* Candle range expansion
* Candle range contraction
* Realized volatility
* Volatility percentile
* Abnormal wick size
* Volatility regime
* Gap or jump detection

## 5.4 Volume features

Implement or verify:

* Average volume
* Relative volume
* Volume z-score
* Volume spike
* Directional volume pressure
* Breakout volume confirmation
* Exhaustion volume
* Volume-price divergence
* OBV
* OBV slope
* Volume-weighted momentum
* Session-relative volume where practical

## 5.5 Price-location features

Implement or verify:

* VWAP
* Anchored VWAP framework
* Distance from VWAP
* Position inside recent range
* Distance from recent swing high
* Distance from recent swing low
* Distance from support
* Distance from resistance
* Distance from liquidity pool
* Distance from Bollinger Bands
* Extension from moving averages
* Premium and discount location
* Fibonacci retracement location as optional evidence
* Nearest opposing structure distance
* Target-space availability

## 5.6 Candle-pattern features

Implement patterns as structured evidence, not direct signals:

* Bullish engulfing
* Bearish engulfing
* Pin bar
* Hammer
* Shooting star
* Inside bar
* Outside bar
* Strong displacement candle
* Rejection candle
* Doji
* Consecutive expansion candles
* Exhaustion wick
* Failed breakout close
* Break-and-reclaim candle

---

# 6. Market Structure Engine

Strengthen the structure layer.

## 6.1 Swing detection

Support:

* Confirmed pivots
* Developing pivots
* Volatility-adjusted pivot sensitivity
* Timeframe-specific sensitivity
* Minimum displacement
* Minimum separation
* Major and minor swing classification

## 6.2 Structural classification

Each timeframe should provide:

```text
strong_bullish
bullish
weak_bullish
range
weak_bearish
bearish
strong_bearish
transition
uncertain
```

Include:

* Higher high
* Higher low
* Lower high
* Lower low
* Break of structure
* Change of character
* Failed break of structure
* Structure reclaim
* Trend continuation state
* Trend exhaustion state

## 6.3 Break quality

A break of structure must consider:

* Wick-only versus close break
* Break distance
* Candle body strength
* Relative volume
* Follow-through
* Immediate reclaim
* Higher-timeframe level conflict
* Volatility-normalized displacement

## 6.4 Support and resistance zones

Use zones rather than exact single-price lines.

Each zone should expose:

```text
lower_bound
upper_bound
strength
touch_count
rejection_count
break_count
last_tested_at
timeframe
freshness
role
```

Zone strength should decay when repeatedly tested.

## 6.5 Range detection

Detect:

* Stable range
* Expanding range
* Contracting range
* Ascending range
* Descending range
* Range midpoint
* Range extremes
* Number of boundary tests
* False breakout count
* Current location

---

# 7. Liquidity and Trap Engine

Strengthen liquidity detection.

## 7.1 Liquidity pools

Detect:

* Equal highs
* Equal lows
* Clustered swing highs
* Clustered swing lows
* Range highs
* Range lows
* Previous day high and low
* Previous week high and low
* Session highs and lows
* Round-number liquidity
* Recent breakout levels
* Untested structure levels

## 7.2 Liquidity sweeps

Sweep quality should consider:

* Distance beyond liquidity
* Wick size
* Body close location
* Close back inside level
* Relative volume
* Follow-through
* Structure reclaim
* Higher-timeframe location
* Time since liquidity was formed
* Number of clustered levels swept

Classify:

```text
weak_sweep
valid_sweep
strong_sweep
failed_sweep
```

## 7.3 Trap detection

Implement or verify:

* Bull trap
* Bear trap
* Long trap
* Short trap
* Breakout chase risk
* Stop-hunt rejection
* Failed continuation
* Squeeze risk
* Late-entry risk
* Exhaustion breakout

Every trap event must contain evidence and confidence.

---

# 8. Market Regime Engine

The market regime layer should classify both symbol-level and broader market conditions.

Required regimes:

```text
strong_uptrend
weak_uptrend
strong_downtrend
weak_downtrend
stable_range
volatile_range
compression
breakout_expansion
reversal_transition
high_volatility_chaos
low_volatility_stagnation
low_liquidity
uncertain
```

Regime classification should use:

* Structure
* Trend slope
* ADX
* ATR percentile
* Bandwidth percentile
* Relative volume
* Range behavior
* Breakout state
* Momentum persistence

Strategy eligibility must depend on regime.

Example:

```text
trend pullback       → trending regimes
range reversal       → stable range
compression breakout → compression
sweep reversal       → liquidity event near major level
momentum expansion   → breakout expansion
```

Do not allow every strategy to run equally in every regime.

---

# 9. Strategy Engine Improvements

Keep strategies independent.

Each strategy must:

* Produce a candidate or no candidate
* Explain supporting factors
* Explain contradictions
* Define entry concept
* Define invalidation concept
* Define target concept
* Declare preferred regimes
* Declare forbidden regimes
* Declare minimum required data
* Avoid position sizing
* Avoid order execution

## 9.1 Trend pullback continuation

Improve using:

* Higher-timeframe trend
* Pullback depth
* EMA/VWAP relationship
* Structural support or resistance
* Momentum reset
* Rejection evidence
* Relative volume normalization
* Target space
* Pullback quality
* Trend maturity

Reject:

* Deep structural failure
* Excessive extension
* Weak target space
* Chaotic volatility
* Late-stage exhaustion

## 9.2 Breakout continuation

Require:

* Defined base, range, or compression
* Valid structural break
* Volume participation
* Displacement quality
* No immediate rejection
* Sufficient target space
* Acceptable distance from breakout level

Penalize:

* Overextended breakout candle
* Low volume
* Break into higher-timeframe resistance
* Repeated failed breaks
* Poor risk-to-reward

## 9.3 Breakout retest

Require:

* Valid prior breakout
* Retest of broken zone
* Hold or reclaim behavior
* Entry timeframe confirmation
* Structural stop
* Remaining target space

## 9.4 Liquidity sweep reversal

Require:

* Clear liquidity pool
* Sweep beyond level
* Rejection or reclaim
* Momentum shift
* Structural invalidation
* Target toward opposing liquidity

## 9.5 Range-edge reversal

Require:

* Valid stable range
* Entry near range edge
* No entry near midpoint
* Rejection or failed breakout
* Clear opposite-side target
* Controlled stop outside boundary

## 9.6 Momentum expansion

Require:

* Volume expansion
* Volatility expansion
* Directional displacement
* No severe extension
* Target space
* Strong lower-timeframe continuation

This is aggressive and must have strong chase protection.

## 9.7 Failed continuation reversal

Require stronger evidence than continuation strategies:

* Failed continuation attempt
* Structural shift
* Momentum failure
* Opposing liquidity target
* Higher-timeframe location
* Reclaim or breakdown confirmation

## 9.8 Compression breakout

Use:

* ATR contraction
* Bandwidth contraction
* Candle-range contraction
* Volume contraction
* Defined compression boundaries
* Directional break
* Volume expansion
* Retest quality where available

## 9.9 Additional strategies to add

Add these only as isolated strategies with independent tests:

### VWAP reclaim or rejection

For intraday directional entries around VWAP or anchored VWAP.

### Higher-timeframe level reaction

Trade reactions from:

* Daily support/resistance
* Weekly support/resistance
* Previous day high/low
* Previous week high/low

### Trend exhaustion reversal

Use:

* Extension
* Momentum divergence
* Exhaustion volume
* Sweep
* Structure shift

### Session breakout

Optional strategy around major market sessions, only if session timestamps are modeled correctly.

### Multi-timeframe confluence entry

A separate strategy for strong alignment, not a universal voting mechanism.

---

# 10. Candidate Deduplication and Clustering

Multiple strategies may identify the same move.

Implement candidate clustering using:

* Symbol
* Direction
* Entry overlap
* Stop overlap
* Target overlap
* Shared structural event
* Shared liquidity event
* Generation time window

Cluster duplicate candidates and select:

* Dominant strategy
* Supporting secondary strategies
* Combined evidence
* Strongest invalidation
* Best risk structure

Do not generate multiple independent trades for the same underlying thesis.

Add:

* Same-symbol cooldown
* Same-direction cooldown
* Repeated-level cooldown
* Signal expiry
* Structural invalidation before entry

---

# 11. Scoring Engine

Audit the existing scoring system and make it configuration-driven.

Suggested components:

```text
trend_alignment
structure_quality
entry_quality
momentum_quality
volume_quality
liquidity_quality
volatility_suitability
regime_suitability
risk_reward_quality
stop_quality
target_space
data_confidence
extension_penalty
conflict_penalty
chase_penalty
late_entry_penalty
liquidity_penalty
```

## 11.1 Requirements

* Normalized score
* Transparent breakdown
* Strategy-specific weights
* Regime-specific adjustments
* Direction-specific explanation
* No hidden constants
* Finite output
* Deterministic behavior
* Config hash stored with result

## 11.2 Score bands

Keep thresholds configurable.

Starting interpretation:

```text
85–100 exceptional
75–84  strong
65–74  valid aggressive
55–64  experimental
below 55 reject
```

Do not optimize thresholds based only on win rate.

Evaluate:

* Expectancy
* Profit factor
* Drawdown
* Trade count
* Stability
* Fee sensitivity
* Slippage sensitivity

---

# 12. Entry Engine

Improve entry calculation.

Supported entry concepts:

* Market-near entry
* Pullback entry
* Retest entry
* Rejection entry
* Breakout entry
* Scaled entry
* Limit-zone entry

Output:

```text
current_price
analysis_price
entry_low
entry_high
preferred_entry
maximum_chase_price
entry_type
entry_expiry
current_price_inside_zone
distance_to_entry_pct
```

## 12.1 Chase protection

Reject or downgrade when:

* Price moves too far beyond preferred entry
* Stop distance expands too much
* Target space shrinks
* Risk-to-reward falls below threshold
* Entry occurs after abnormal extension
* Price reaches TP before entry
* Structure invalidates before entry

---

# 13. Stop-Loss Engine

Stops must be structural.

Possible references:

* Swing extreme
* Sweep extreme
* Range boundary
* Breakout failure level
* Retest failure level
* ATR-adjusted structure
* Higher-timeframe invalidation
* VWAP reclaim failure

Validate:

* Long stop below entry
* Short stop above entry
* Stop not inside normal noise
* Stop not excessively wide
* Stop tied to thesis
* Stop distance within profile limit
* Liquidation safely beyond stop

Add a stop-quality score.

---

# 14. Target and Trade-Management Engine

Support:

```text
TP1
TP2
TP3
```

Target sources:

* Recent swing
* Opposing liquidity
* Range midpoint
* Range boundary
* Higher-timeframe level
* ATR projection
* Measured move
* Risk multiple
* VWAP
* Anchored VWAP

Each target must expose:

```text
price
risk_reward
rationale
partial_close_pct
probability_band
```

Add configurable management policies:

```text
full_exit_tp1
partial_50_30_20
move_stop_to_breakeven_after_tp1
structure_trailing_stop
atr_trailing_stop
time_based_exit
momentum_failure_exit
```

Do not force unrealistic TP3 values merely to inflate risk-to-reward.

---

# 15. Risk Engine

Verify and improve:

* Account equity
* Risk percentage
* Position size
* Stop distance
* Notional value
* Leverage
* Liquidation buffer
* Maximum order notional
* Daily loss limit
* Concurrent risk
* Same-direction exposure
* Correlated-symbol exposure
* Consecutive-loss circuit breaker
* Strategy-specific risk
* Countertrend risk reduction

Profiles:

```text
controlled
aggressive
extreme
```

Profile configuration should affect:

* Minimum score
* Maximum account risk
* Maximum leverage
* Maximum stop distance
* Allowed strategies
* Maximum concurrent positions
* Countertrend permission
* Minimum target space
* Daily loss limit

Extreme mode must still enforce a hard risk ceiling.

Never implement martingale.

Never automatically average into losing positions.

---

# 16. Leverage and Liquidation Engine

Leverage should be derived from risk, not selected as a profit multiplier.

Consider:

* Stop distance
* Volatility
* Liquidity
* Entry precision
* Setup score
* Risk profile
* Maintenance margin assumptions
* Liquidation buffer

Output:

```text
suggested_min_leverage
suggested_max_leverage
modeled_max_leverage
estimated_liquidation_price
distance_stop_to_liquidation
liquidation_safety_ratio
```

Reject when liquidation is too close to stop or normal volatility.

Exchange-specific liquidation formulas should remain isolated.

---

# 17. True Historical Backtesting Engine

The current backtesting layer must be audited carefully.

A single pre-generated setup replay function is not a complete historical backtesting system.

Implement a chronological full-pipeline backtest runner.

## 17.1 Required workflow

For each historical decision timestamp:

1. Load only candles available at that time
2. Build higher-timeframe candles without future leakage
3. Calculate features
4. Analyze structure
5. Analyze liquidity
6. Classify regime
7. Generate strategy candidates
8. Cluster duplicates
9. Score candidates
10. Apply risk rules
11. Create setup or `NO_TRADE`
12. Simulate entry only after decision time
13. Track stop, targets, expiry, and management
14. Update portfolio exposure
15. Continue chronologically

## 17.2 No-lookahead rules

Add explicit tests for:

* Indicator lookahead
* Pivot confirmation lookahead
* Higher-timeframe resampling lookahead
* Active candle leakage
* Future volume leakage
* Future structure leakage
* Same-candle signal and fill ambiguity
* Stop and target same-candle ambiguity

## 17.3 Historical runner interface

Create a clear service such as:

```python
class HistoricalBacktestRunner:
    def run(self, request: BacktestRequest) -> BacktestStudy:
        ...
```

`BacktestRequest` should include:

```text
symbols
timeframes
start
end
warmup_period
strategy_config
scoring_config
risk_config
execution_config
starting_equity
fee_model
slippage_model
maximum_positions
```

## 17.4 Execution realism

Model:

* Fees
* Slippage
* Limit entry misses
* Entry-zone touches
* Partial fills where practical
* Signal expiry
* Maximum holding time
* Stop gaps
* Target gaps
* Conservative ambiguity
* Partial targets
* Breakeven movement
* Trailing stops
* Concurrent positions
* Portfolio equity

## 17.5 Metrics

Add:

* Starting equity
* Ending equity
* Net return
* Maximum absolute drawdown
* Maximum percentage drawdown
* Win rate
* Profit factor
* Expectancy
* Average R
* Median R
* Average win
* Average loss
* Largest win
* Largest loss
* Consecutive wins
* Consecutive losses
* Sharpe-like metric
* Sortino-like metric
* Calmar-like metric
* Exposure time
* Average holding duration
* Fee impact
* Slippage impact
* Long versus short performance
* Performance by symbol
* Performance by strategy
* Performance by regime
* Performance by timeframe role
* Performance by score band
* Performance by leverage band
* Monthly performance
* Tail-loss analysis
* Risk-of-ruin estimate
* Monte Carlo reshuffling summary

## 17.6 Dataset splitting

Support:

```text
development
validation
out_of_sample
walk_forward
```

Do not optimize on the final out-of-sample dataset.

Store dataset identifiers and hashes.

---

# 18. Optimization Engine

The optimization framework must operate on actual backtest studies.

Requirements:

* Baseline configuration
* Candidate configuration
* Exactly one variable group changed at a time
* Reproducible dataset
* Config hash
* Code version
* Dataset version
* Acceptance criteria
* Rejection reason

Variable groups:

```text
indicator_periods
structure_thresholds
liquidity_thresholds
strategy_thresholds
scoring_weights
minimum_scores
entry_parameters
stop_parameters
target_parameters
risk_parameters
regime_rules
```

Reject candidates that:

* Improve win rate but reduce expectancy
* Improve in-sample but collapse out-of-sample
* Reduce trade sample below meaningful size
* Increase drawdown disproportionately
* Depend on one symbol
* Depend on one narrow period
* Become highly fee-sensitive
* Become highly parameter-sensitive

Add parameter-stability testing around selected values.

---

# 19. Paper-Trading Engine

Complete the forward paper-testing system.

## 19.1 Required lifecycle

```text
generated
waiting_for_entry
entered
partially_closed
stop_moved
stopped
target_hit
expired
cancelled
invalidated
```

## 19.2 Persistence

Store:

* Original analysis
* Input market snapshot
* Config hashes
* Entry zone
* Stop
* Targets
* Score breakdown
* Evidence
* Contradictions
* Entry event
* Exit events
* Fees
* Slippage
* Final PnL
* Final R
* Lifecycle history

## 19.3 Restart recovery

Paper trading must survive process restarts.

On startup:

* Reload open setups
* Reload open paper positions
* Reconcile market status
* Expire stale setups
* Continue lifecycle processing
* Avoid duplicate entries

## 19.4 Reports

Generate:

* Daily summary
* Weekly summary
* Monthly summary
* Strategy performance
* Score-band performance
* Regime performance
* Rejected-candidate review
* Backtest versus paper comparison

---

# 20. Market-Wide Intelligence

Advanced intelligence should remain isolated until validated.

Add deterministic inputs where free reliable data is available:

* Funding rate
* Open interest
* Open-interest change
* BTC market regime
* BTC dominance where available
* ETH/BTC trend
* Symbol correlation
* Market breadth
* Correlated exposure
* Broad liquidation-risk state
* Stablecoin dominance or flow only if a reliable source exists

Initially use intelligence for:

* Metadata
* Warnings
* Risk adjustment
* Exposure control

Do not allow intelligence to directly approve a weak setup.

---

# 21. Scanner Improvements

The scanner must support controlled concurrency.

Implement:

* Async or bounded parallel fetching
* Provider rate limiter
* Maximum concurrency
* Per-symbol timeout
* Failure isolation
* Deterministic result ordering
* Shared cache
* Retry budget
* Cancellation handling

Do not use uncontrolled `gather()` across all symbols and timeframes.

## 21.1 Eligibility filtering

Before full analysis, filter symbols using:

* Minimum quote volume
* Maximum spread
* Minimum trading history
* Candle availability
* Data freshness
* Volatility suitability
* Price validity
* Liquidity
* Supported market type

## 21.2 Scanner output

Return:

```text
best_overall
top_longs
top_shorts
aggressive_setups
rejected_high_potential
market_regime_summary
failures
data_warnings
generated_at
```

For rejected high-potential setups include:

* Best candidate score
* Exact rejection reason
* Required price or condition to become valid

---

# 22. Error Handling and Logging

Replace broad hidden failures with typed error handling.

Create or verify domain exceptions:

```text
ConfigurationError
ProviderError
RateLimitError
DataValidationError
StaleDataError
FeatureCalculationError
StructureAnalysisError
StrategyError
ScoringError
RiskError
BacktestError
StorageError
ExecutionError
```

Scanner may isolate failures, but unexpected exceptions must be logged with traceback.

Structured log fields should include:

```text
analysis_id
symbol
timeframe
provider
strategy
candidate_id
configuration_id
dataset_id
error_type
```

Do not log secrets.

---

# 23. Execution Boundary

Current simulated local execution must not be misrepresented as actual exchange testnet submission.

If the current engine only writes an audit event locally, rename its state and CLI output to something explicit such as:

```text
SIMULATED_SUBMITTED
LOCAL_TESTNET_SIMULATION
```

## 23.1 Actual testnet adapter

Only after simulation and paper modules are stable, add a provider protocol:

```python
class ExecutionProvider(Protocol):
    def submit_order(...)
    def cancel_order(...)
    def fetch_order(...)
    def fetch_open_orders(...)
    def fetch_position(...)
    def fetch_balance(...)
```

Implement at most one real exchange testnet adapter initially.

Requirements:

* Testnet endpoint only
* Explicit environment flag
* Explicit user confirmation
* No mainnet URL accepted
* No withdrawal support
* No API secret logging
* Idempotency key
* Duplicate protection
* Order reconciliation
* Position reconciliation
* Cancel support
* Restart recovery
* Kill switch
* Daily loss limit
* Maximum notional
* Audit log

Do not implement mainnet.

---

# 24. Configuration and Reproducibility

Move important behavior from hardcoded constants into validated configuration.

Configuration categories:

```text
general
providers
timeframes
features
structure
liquidity
regime
strategies
scoring
entry
stops
targets
risk
leverage
scanner
backtesting
paper_trading
optimization
intelligence
execution
```

Every analysis, backtest, paper trade, and optimization result should record:

```text
code_version
git_commit
configuration_hash
strategy_config_hash
risk_config_hash
dataset_hash
provider
generated_at
```

Configuration validation must reject:

* Negative periods
* Zero candle counts
* Invalid weights
* Impossible risk values
* Unsupported timeframes
* Duplicate symbols
* Invalid leverage ranges
* Invalid score thresholds
* Mainnet execution configuration

---

# 25. CLI Improvements

Audit all existing commands.

Recommended final CLI structure:

```bash
apex version
apex validate-config
apex doctor
apex analyze BTC/USDT
apex scan
apex data fetch
apex data validate
apex backtest run
apex backtest report
apex paper start
apex paper update
apex paper report
apex optimize evaluate
apex optimize compare
apex intelligence summary
apex execute preview
apex execute simulate
apex execute testnet
apex execute status
apex execute kill-switch enable
apex execute kill-switch disable
```

Add:

```bash
apex doctor
```

It should verify:

* Python version
* Configuration
* Required directories
* Provider connectivity
* Write permissions
* Database or storage access
* Enabled safety flags
* Testnet mode
* No mainnet configuration

Human-readable output and JSON output should both remain supported.

---

# 26. Storage

Keep the initial system local and simple.

Recommended:

* Parquet for candles and large historical datasets
* SQLite for paper trades, analyses, and lifecycle events
* JSON for exported reports
* JSONL for append-only audit logs

Use migrations or schema versioning for SQLite.

Do not introduce Frappe or a heavy web framework.

---

# 27. Testing Requirements

## 27.1 Unit tests

Required for:

* Candle validation
* Resampling
* Every indicator
* Swing detection
* Trend classification
* BOS and CHoCH
* Range detection
* Support/resistance
* Liquidity pools
* Sweeps
* Trap detection
* Regime classification
* Every strategy
* Candidate clustering
* Scoring
* Entry engine
* Stops
* Targets
* Position sizing
* Leverage
* Liquidation checks
* Configuration validation
* Serialization

## 27.2 Integration tests

Required for:

* Provider adapter
* Cache
* Multi-timeframe pipeline
* Full symbol analysis
* Scanner
* Backtest runner
* Paper lifecycle
* SQLite persistence
* Restart recovery
* CLI
* Testnet adapter when added

## 27.3 Regression tests

Every bug fix requires a regression test.

## 27.4 Invariant tests

Required invariants:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
volume >= 0
long stop < entry
short stop > entry
long target > entry
short target < entry
position risk <= configured risk
liquidation beyond stop safety boundary
score finite
price finite
quantity positive
no NaN
no infinity
```

## 27.5 Lookahead tests

Explicitly test:

* Pivot confirmation
* Higher-timeframe resampling
* Feature windows
* Strategy generation
* Same-candle entry
* Active candle handling

## 27.6 Fixture scenarios

Create deterministic fixtures for:

* Strong uptrend
* Strong downtrend
* Controlled pullback
* Bull trap
* Bear trap
* Liquidity sweep
* False breakout
* Stable range
* Volatile range
* Compression
* Breakout expansion
* Exhaustion
* Missing data
* Stale data
* Flat market
* Flash-crash-like candle
* Same-candle stop and target
* Gap beyond stop

---

# 28. CI and Quality Gates

Ensure local commands pass:

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=apex --cov-report=term-missing
git diff --check
```

Add a coverage threshold after measuring the current baseline.

Do not immediately set an unrealistic threshold that breaks the project.

Raise it incrementally.

Recommended CI matrix:

```text
Python 3.11
Python 3.12
Python 3.13
```

Add:

* Package build
* Editable install smoke test
* CLI smoke test
* Configuration validation
* Architecture boundary tests
* Determinism test
* Backtest fixture smoke test

---

# 29. Refactoring Guidelines

Replace development-phase naming from public APIs where practical.

Prefer:

```text
analyze_market_structure
generate_candidates
score_candidates
assess_risk
```

over:

```text
analyze_phase3
analyze_phase4
analyze_phase5
analyze_phase6
```

Do this carefully.

Maintain backward-compatible imports temporarily if tests or modules depend on old names.

Do not perform a massive blind rename.

---

# 30. Delivery Phases

## Phase A — Audit and correctness

Deliver:

* Repository implementation map
* Current quality-gate results
* Identified stubs and misleading behaviors
* Critical bug fixes
* Regression tests
* Correct execution-state naming
* Configuration audit

Completion criteria:

* Full quality gate passes
* No known misleading execution behavior
* No major untested critical path

## Phase B — Timeframes and market data

Deliver:

* Optional higher timeframes
* Timeframe-role configuration
* Safe candle resampling
* Live ticker separation
* Data freshness
* Data-quality improvements
* Tests

Completion criteria:

* Multi-timeframe analysis is deterministic
* No resampling lookahead
* Live and closed prices are correctly separated

## Phase C — Feature, structure, liquidity, and regime

Deliver:

* Indicator audit and missing indicators
* Improved structure
* Liquidity pools and sweeps
* Trap detection
* Regime engine
* Fixture coverage

Completion criteria:

* Each module produces explainable output
* All important events have tests

## Phase D — Strategies and scoring

Deliver:

* Improved existing strategies
* Additional isolated strategies
* Candidate clustering
* Strategy eligibility by regime
* Transparent scoring
* Entry and chase protection

Completion criteria:

* Every candidate includes thesis and contradiction
* Duplicate trade theses are clustered
* Weak setups are rejected consistently

## Phase E — Risk and trade management

Deliver:

* Structural stops
* Multi-target engine
* Partial exits
* Breakeven movement
* Trailing options
* Position sizing
* Leverage and liquidation
* Exposure controls

Completion criteria:

* Every approved setup has controlled risk
* All risk invariants pass

## Phase F — True backtesting

Deliver:

* Chronological full-pipeline runner
* No-lookahead tests
* Portfolio simulation
* Realistic execution assumptions
* Full metrics
* Dataset splits
* Reproducible reports

Completion criteria:

* Results can be reproduced
* No known future-data leakage
* Reports include strategy, regime, score, and symbol breakdowns

## Phase G — Optimization

Deliver:

* Baseline comparison
* One-variable-group optimization
* Validation and out-of-sample gates
* Parameter stability
* Rejection rules

Completion criteria:

* Optimization cannot accept win-rate-only degradation
* Accepted changes survive out-of-sample validation

## Phase H — Paper trading

Deliver:

* Full lifecycle
* Persistence
* Restart recovery
* Scheduled update flow
* Reports
* Backtest versus paper comparison

Completion criteria:

* The system can run continuously without real orders
* Every setup is auditable

## Phase I — Optional actual exchange testnet

Deliver only after previous phases pass:

* Execution provider interface
* One testnet adapter
* Order and position reconciliation
* Idempotency
* Kill switch
* Restart recovery
* Audit logs

Completion criteria:

* No mainnet support
* Duplicate order protection verified
* Reconciliation tested
* Safety controls tested

---

# 31. Validation Gates

## Gate 1 — Engineering correctness

Required:

* Ruff passes
* Formatting passes
* Mypy passes
* Tests pass
* No NaN or infinite outputs
* Determinism tests pass
* Data validation passes

## Gate 2 — Historical baseline

Required:

* Meaningful sample size
* Fees included
* Slippage included
* No lookahead
* Reports per strategy
* Reports per regime
* Reports per symbol
* Reports per score band

## Gate 3 — Out-of-sample

Required:

* Untouched period
* Acceptable expectancy
* Acceptable drawdown
* No single-symbol dependency
* No severe parameter sensitivity

## Gate 4 — Forward paper

Required:

* Meaningful sample
* Entry timing realistically tracked
* Slippage measured
* Backtest versus paper divergence analyzed
* Stable operation

## Gate 5 — Testnet execution

Required:

* Explicit confirmation
* Kill switch
* Duplicate prevention
* Max notional
* Daily loss circuit breaker
* Order reconciliation
* Position reconciliation
* Restart recovery
* No mainnet support

---

# 32. Required Final Output from Codex

At the end of each implementation phase, provide:

## Completed work

List:

* Files added
* Files modified
* Behavior added
* Bugs fixed
* Tests added

## Verification

Provide exact results for:

```text
ruff
format
mypy
pytest
coverage
git diff --check
```

## Remaining limitations

State honestly:

* What is still incomplete
* What is simulated
* What requires data
* What requires forward testing
* What is not production-ready

## Architecture notes

Explain any important design decisions.

## Next recommended phase

Do not begin unrelated improvements automatically.

Complete the current phase cleanly before advancing.

---

# 33. Immediate Implementation Order

Start in this exact order:

1. Full repository audit
2. Run complete quality gate
3. Fix current failures
4. Correct misleading simulated testnet terminology
5. Audit timeframe roles and add configurable higher-timeframe support
6. Separate live price from closed-candle analysis price
7. Implement safe timeframe resampling
8. Audit and correct indicator naming and periods
9. Strengthen structure, liquidity, and regime engines
10. Improve strategy eligibility and candidate clustering
11. Complete entry, stop, target, leverage, and exposure rules
12. Build the true chronological backtesting runner
13. Add no-lookahead validation
14. Produce first reproducible historical baseline
15. Complete paper-trading lifecycle
16. Only then consider an actual exchange testnet adapter

The highest-priority engineering goal is:

> Build a trustworthy chronological multi-timeframe backtesting and forward-paper framework that can prove whether the existing strategies have repeatable expectancy.

Do not prioritize:

* UI
* Web dashboard
* Frappe
* LLM integration
* Real-money execution
* README redesign
* Excessive strategy count

until the deterministic engine is objectively validated.
