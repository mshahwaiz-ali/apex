# Apex Trading Agent — Final Simplification and Redesign Plan

## 1. Final Product Definition

Apex Trading Agent ka primary kaam hai:

> Binance market ko scan karke current price ke qareeb available long aur short opportunities identify karna, unhein score karna, rank karna, aur user ke wallet ke mutabiq executable trade plan banana.

System ka focus hoga:

* market-wide opportunity discovery;
* fast intraday and short swing trades;
* high potential reward with controlled and visible risk;
* near-current-price entries;
* long and short futures opportunities;
* future spot support without a separate duplicated product;
* transparent scoring;
* clear warnings without unnecessarily cancelling trades;
* wallet-aware position planning;
* deterministic and explainable results.

Apex ka purpose institutional reporting platform, compliance workflow, autonomous self-learning system, ya presentation framework banana nahi hai.

---

# 2. Final Operating Principle

Apex ke core workflow ko is order mein operate karna hai:

```text
Discover the market opportunity
→ evaluate possible strategies
→ score and rank every usable candidate
→ describe entry conditions and cautions
→ calculate wallet-aware execution plan
→ log the complete result
```

Risk planning trade discovery ko suppress nahi karegi.

Market caution trade ko automatically cancel nahi karegi.

A candidate sirf tab completely invalid hoga jab:

* market data invalid ho;
* contract inactive ho;
* liquidity execution ke liye unusable ho;
* trade direction structurally impossible ho;
* entry thesis already invalidated ho;
* stop and entry geometry logically inconsistent ho;
* required order exchange rules ke mutabiq place hi na ho sake.

---

# 3. Mandatory Product Decisions

## 3.1 Gainer mode completely remove karna hai

Current concepts remove honge:

* gainer scanner mode;
* gainer market category;
* gainer state machine;
* gainer-specific thresholds;
* gainer-specific strategy routing;
* gainer-specific evidence;
* normal-versus-gainer duplicate analysis;
* CLI values such as `gainers` and `all` where `all` ka meaning normal plus gainer duplication ho;
* serialized fields related specifically to gainer classification;
* tests and documentation built only around gainer mode.

Apex top movers aur accelerating markets ko naturally universe scoring mein identify karega.

Top mover hona ek market feature hoga, separate scanner identity nahi.

Examples:

```text
24h return
1h acceleration
15m acceleration
relative volume
range expansion
volume acceleration
breakout proximity
```

These features opportunity score ko influence karenge, lekin coin ko artificial “gainer mode” mein route nahi karenge.

---

## 3.2 Futures primary product rahega

Active development ka primary target:

```text
Binance USDT perpetual futures
```

Futures system must support:

* long and short opportunities;
* isolated-margin planning;
* mark-price-aware risk;
* fees and slippage;
* stop placement;
* leverage calculation;
* liquidation estimate;
* funded-account constraints;
* wallet-based quantity and margin.

---

## 3.3 Spot temporarily freeze aur hide karna hai

Spot code immediately delete nahi karna.

Spot ke liye:

* CLI commands hidden or unregistered;
* main README capability tables se remove;
* default help output se remove;
* paper workflows se disable;
* UI navigation mein future mein hidden;
* active tests sirf preserved behavior ke liye reh sakte hain;
* no new spot feature development;
* no separate spot architecture expansion.

Spot ko later same shared engine ke through enable kiya jayega:

```text
shared universe discovery
shared market features
shared strategy engine
shared scoring
shared entry engine
spot-specific execution planner
```

Spot ek separate product ya parallel architecture nahi hoga.

---

## 3.4 Autonomous self-learning remove karna hai

Apex automatically apne thresholds ya strategies modify nahi karega.

Remove or archive:

* automatic optimization workflows;
* automatic threshold mutation;
* automated candidate-versus-baseline promotion machinery not required for manual analysis;
* self-learning claims;
* autonomous adaptation language;
* unnecessary optimization orchestration.

Keep:

* complete structured logs;
* historical scan records;
* rejection reasons;
* outcomes where paper tracking is used;
* manual review reports;
* reproducible backtesting utilities.

Later issue aaye to logs aur historical records manually inspect karke targeted improvements ki jayengi.

---

# 4. Current Design Problems to Correct

## 4.1 Static symbol universe

Current configured universe limited symbols tak restricted hai.

Required behavior:

* Binance se current active contracts load karo;
* static YAML list ko primary universe na banao;
* exchange status and contract metadata validate karo;
* USDT perpetual futures dynamically discover karo;
* blacklist and optional allowlist support rakho;
* delisted, inactive, suspended, or unsuitable contracts reject karo.

Static symbols file sirf optional override hoga.

---

## 4.2 Fake gainer routing

Same configured symbols ko different category labels ke saath analyze karna band karna hai.

Har symbol exactly once primary discovery and analysis pipeline se guzrega.

Strategy selection measurable market state par based hogi, category label par nahi.

---

## 4.3 Full expensive analysis too early

Current design detailed multi-timeframe work shortlist se pehle kar sakta hai.

Required two-level model:

### Market-wide lightweight screening

All active contracts par cheap metrics calculate karo.

### Detailed trade analysis

Only top shortlisted contracts par deeper candle, structure, strategy, entry, and risk analysis chalao.

This will:

* increase market coverage;
* reduce requests;
* reduce scan time;
* focus computation on moving markets;
* create more realistic opportunity flow.

---

## 4.4 Too many hard blockers

Current environment, routing, candidate, entry, and risk decisions ko one strict approval chain mein combine nahi karna.

Required separation:

```text
Opportunity quality
Setup quality
Timing quality
Risk feasibility
Warnings
```

A weak risk plan does not erase a real market opportunity.

A sweep risk does not erase a breakout opportunity.

Higher-timeframe disagreement does not automatically erase a valid fast trade.

---

## 4.5 Binary trade visibility

Final scanner must not only display fully approved setups.

It must display:

* ready setups;
* aggressive setups;
* pullback-preferred setups;
* watch setups;
* late/chase-risk setups;
* low-confidence setups;
* invalidated setups only when useful for diagnostics.

Default scan should show the best 10–15 ranked opportunities.

A scan may show fewer only when:

* exchange data failed materially;
* insufficient active contracts were available;
* safety filters removed genuinely untradeable markets.

The system must not fabricate trade quality merely to reach a numeric quota.

---

## 4.6 Higher-timeframe over-control

The target product is primarily fast intraday opportunity discovery.

Default active analysis hierarchy:

| Timeframe | Role                                    |
| --------- | --------------------------------------- |
| `1m`      | execution timing and immediate momentum |
| `3m`      | trigger quality and microstructure      |
| `5m`      | primary entry structure                 |
| `15m`     | setup and local regime                  |
| `30m`     | intraday context                        |
| `1h`      | broader trend and danger context        |
| `4h`      | optional macro warning only             |

The `4h` timeframe must not normally veto a valid fast trade.

Examples:

```text
4h overextended → caution
4h opposing trend → lower score
4h major resistance nearby → target limitation
```

Not:

```text
4h conflict → automatic no trade
```

Longer resampled timeframes such as weekly or multi-day views are outside the default scanning workflow.

---

# 5. Target System Architecture

```text
Binance Contract Universe
        ↓
Contract and Liquidity Eligibility
        ↓
Market-Wide Opportunity Screener
        ↓
Shortlisted Symbols
        ↓
Detailed Multi-Timeframe Feature Analysis
        ↓
Market-State Classification
        ↓
Applicable Strategy Evaluation
        ↓
Candidate Scoring and Ranking
        ↓
Entry and Trade Construction
        ↓
Warnings and Cautions
        ↓
Wallet / Funded Risk Planning
        ↓
Top Opportunities + Full Diagnostics
```

---

# 6. Binance Universe Discovery

## 6.1 Futures universe source

Load from Binance exchange metadata:

* active USDT perpetual contracts;
* contract trading status;
* base asset;
* quote asset;
* tick size;
* step size;
* minimum quantity;
* minimum notional;
* leverage brackets where accessible;
* relevant precision filters.

## 6.2 Initial exclusions

Exclude:

* inactive contracts;
* contracts not settled in the configured quote asset;
* contracts with broken market data;
* contracts below minimum liquidity;
* contracts with extreme spread;
* contracts with insufficient candle history;
* manually blacklisted symbols;
* products outside selected crypto scope.

## 6.3 Do not use fixed top-volume-only selection

Low-volume assets can move sharply but may be unsafe to execute.

Volume must therefore be scored, not used as the only selection criterion.

Universe screening should balance:

* liquidity;
* movement;
* volume acceleration;
* volatility;
* spread;
* tradeability;
* entry freshness.

---

# 7. Market-Wide Opportunity Screener

The screener ka purpose trade approve karna nahi.

Its purpose:

> Which markets deserve detailed strategy analysis right now?

## 7.1 Required screener inputs

Prefer lightweight ticker and limited candle data:

* current price;
* bid and ask;
* spread percentage;
* 24h quote volume;
* 24h trade count where available;
* 24h percentage move;
* recent `5m`, `15m`, `30m`, and `1h` returns;
* recent volume versus baseline;
* volume acceleration;
* ATR percentage;
* recent candle-range expansion;
* trend slope;
* breakout distance;
* VWAP or short EMA distance;
* recent high/low proximity;
* wick intensity;
* directional persistence;
* current candle participation.

## 7.2 Opportunity score

Each symbol receives a `0–100` opportunity score.

Suggested components:

| Component            | Purpose                                                |
| -------------------- | ------------------------------------------------------ |
| Liquidity            | Can the trade enter and exit cleanly?                  |
| Movement             | Is the coin moving enough to provide profit potential? |
| Acceleration         | Is movement increasing rather than fading?             |
| Relative volume      | Is real participation supporting the move?             |
| Volatility usability | Is volatility profitable but not chaotic?              |
| Entry freshness      | Is the opportunity early enough?                       |
| Structure proximity  | Is price near a useful level?                          |
| Directional clarity  | Is movement one-sided enough to trade?                 |
| Spread penalty       | Will execution cost damage the setup?                  |
| Exhaustion penalty   | Is the move already too stretched?                     |
| Noise penalty        | Is price too erratic for a meaningful stop?            |

## 7.3 Shortlist size

Default:

```text
Market-wide universe: all eligible contracts
Detailed shortlist: top 30
Final displayed opportunities: top 15
```

All values configurable.

The detailed shortlist should preserve directional diversity where possible:

* strong long candidates;
* strong short candidates;
* breakout candidates;
* reversal candidates;
* compression candidates;
* pullback candidates.

---

# 8. Market-State Classification

The system should classify measurable conditions instead of routing through artificial product modes.

Possible states:

* directional trend;
* early momentum expansion;
* mature momentum expansion;
* controlled pullback;
* breakout attempt;
* confirmed breakout;
* breakout retest;
* compression;
* stable range;
* range-edge rejection;
* failed breakout;
* liquidity rejection;
* exhaustion;
* chaotic volatility;
* low-participation drift.

Multiple states may be active simultaneously.

Example:

```text
early momentum expansion
+ breakout attempt
+ high relative volume
+ moderate sweep risk
```

Market-state classification guides strategy applicability but does not automatically approve or reject a trade.

---

# 9. Strategy System

No single strategy works for every coin and every condition.

Each shortlisted symbol will be evaluated against all relevant strategies.

Strategies not applicable to the current market state should return:

```text
not_applicable
```

They should not produce false negative trade rejections.

## 9.1 Core strategy set

### Momentum breakout

Use when:

* price approaches or breaks a meaningful recent level;
* volume expands;
* directional candles persist;
* spread remains acceptable;
* move is not terminally extended.

Volume-supported breakouts have stronger continuation evidence, while immediate reversal back inside the prior range is a fakeout warning.

### Breakout continuation

Use after the initial break when:

* price sustains outside the level;
* momentum remains active;
* pullback remains shallow;
* target space still exists.

### Breakout retest

Use when:

* a broken level is retested;
* price accepts the new side of the level;
* stop can be placed logically beyond the retest failure point.

### First pullback continuation

Use when:

* strong expansion already occurred;
* first controlled pullback develops;
* volume contracts during pullback;
* direction resumes with renewed participation.

### Trend pullback

Use when:

* `15m` or `5m` structure is directional;
* price retraces into EMA, VWAP, prior breakout, or local structure;
* momentum cools without structural failure.

### Compression expansion

Use when:

* ATR and candle ranges compress;
* range boundaries are identifiable;
* participation begins increasing;
* price approaches directional release.

### Range-edge reversal

Use when:

* market is genuinely ranging;
* price reaches a validated boundary;
* rejection appears;
* sufficient space exists toward midpoint or opposite boundary.

### Failed breakout reversal

Use when:

* price breaks a meaningful level;
* continuation fails;
* price re-enters prior structure;
* opposite momentum begins.

### Liquidity-rejection reversal

Use when:

* price trades beyond an obvious high or low;
* rejection is measurable;
* close location and follow-through support reversal;
* nearby target space exists.

### VWAP reclaim or rejection

Use when:

* intraday price location around VWAP is meaningful;
* participation confirms reclaim or rejection;
* local structure supports the direction.

### Momentum scalp

Use when:

* `1m–5m` acceleration is strong;
* liquidity is sufficient;
* spread is low;
* immediate target space exists;
* holding period is expected to be short.

### Exhaustion reversal

Use cautiously when:

* extension is extreme;
* momentum weakens;
* volume or wick behavior shows rejection;
* structure begins failing.

This strategy must receive a higher uncertainty label than continuation setups.

---

# 10. Strategy Applicability Matrix

| Market condition               | Preferred strategies              |
| ------------------------------ | --------------------------------- |
| Early high-volume expansion    | Momentum breakout, momentum scalp |
| Sustained breakout             | Breakout continuation             |
| Clean level retest             | Breakout retest                   |
| First controlled retracement   | First pullback continuation       |
| Established directional market | Trend pullback                    |
| Tight volatility compression   | Compression expansion             |
| Stable range boundary          | Range-edge reversal               |
| Break and rapid re-entry       | Failed breakout reversal          |
| Sweep and rejection            | Liquidity-rejection reversal      |
| VWAP interaction               | VWAP reclaim or rejection         |
| Extreme extension and failure  | Exhaustion reversal               |

Strategy router should prioritize strategies, not restrict the complete analysis to only one strategy.

Each symbol may produce multiple candidates.

Example:

```text
SOLUSDT
1. first_pullback_continuation — 86
2. momentum_scalp — 81
3. breakout_retest — 74
```

The best candidate becomes primary, while alternatives remain visible in verbose diagnostics or JSON.

---

# 11. Candidate Scoring

Every strategy candidate receives a transparent `0–100` setup score.

## 11.1 Setup-score components

* strategy-condition quality;
* directional structure;
* momentum;
* volume confirmation;
* entry location;
* target space;
* stop quality;
* market liquidity;
* timeframe agreement;
* current-price actionability;
* spread and fee impact;
* extension penalty;
* contradiction penalty;
* instability penalty.

## 11.2 Separate score categories

Final scanner must expose:

```text
opportunity_score
setup_score
timing_score
risk_feasibility_score
final_rank_score
```

Suggested final ranking formula:

```text
final_rank_score =
    opportunity_score × opportunity_weight
  + setup_score × setup_weight
  + timing_score × timing_weight
  + risk_feasibility_score × risk_weight
  - severe_warning_penalties
```

Opportunity and setup should carry greater weight than wallet sizing.

## 11.3 Score interpretation

|    Score | Meaning                          |
| -------: | -------------------------------- |
| `85–100` | exceptional current opportunity  |
|  `75–84` | strong opportunity               |
|  `65–74` | valid but aggressive             |
|  `55–64` | speculative or developing        |
|    `<55` | weak, late, or structurally poor |

A candidate below the preferred threshold may still appear in results when it ranks among the best available opportunities, but its status and weaknesses must be explicit.

---

# 12. Final Trade Statuses

Replace overly complicated entry-state behavior with a smaller action-oriented model.

## Required statuses

### `READY_NOW`

Current price is inside or very near the preferred entry area.

### `AGGRESSIVE_NOW`

Trade can be entered now, but entry has meaningful caution such as:

* elevated extension;
* sweep risk;
* weaker confirmation;
* wider volatility;
* reduced target space.

### `PULLBACK_PREFERRED`

Current move remains tradeable, but a better entry exists nearby.

The system still shows:

* current market entry plan;
* preferred pullback zone;
* difference in risk and reward.

### `WATCH_NEAR_ENTRY`

Price is close enough that the setup may become actionable soon.

### `LATE_OR_CHASING`

Direction may be correct but current entry quality has deteriorated.

### `INVALIDATED`

The strategy thesis is no longer valid.

Remove unnecessary states whose only effect is repeatedly telling the user to wait without producing a usable plan.

---

# 13. Entry Engine Redesign

The entry engine must create a practical plan instead of acting as another rejection firewall.

## 13.1 Required outputs

Every usable candidate should include:

* current price;
* preferred entry zone;
* executable market-near entry;
* better pullback entry where applicable;
* maximum chase boundary;
* structural invalidation;
* stop-loss;
* targets;
* expected holding style;
* warnings;
* reason for the entry.

## 13.2 Two entry alternatives

Where appropriate, return:

### Immediate entry

For the user who wants current action.

### Preferred entry

For improved risk-to-reward if price retraces.

Example:

```text
Immediate entry:
  1.245–1.252
  Setup remains valid but extension is moderate.

Preferred entry:
  1.226–1.235
  Better stop geometry and improved reward-to-risk.
```

This avoids converting every non-perfect current price into `NO_TRADE`.

## 13.3 Stop placement

Stop must be derived from:

* structural failure;
* swing invalidation;
* breakout failure;
* retest failure;
* rejection extreme;
* volatility buffer;
* spread and execution allowance.

Stop should not be selected merely to fit a desired leverage.

## 13.4 Targets

Return at least:

* conservative target;
* primary target;
* extended target where structure supports it.

Targets may use:

* nearby liquidity;
* previous swing;
* range boundary;
* measured move;
* ATR projection;
* risk multiple;
* opposing structure.

---

# 14. Liquidity Sweeps and Warnings

Liquidity sweeps must remain detectable.

However, sweep information is normally:

```text
evidence
warning
score adjustment
entry refinement
stop refinement
```

It is not normally:

```text
automatic trade cancellation
```

## 14.1 Examples

### Breakout with sweep risk

```text
Trade remains valid.
Caution: recent high may attract a liquidity sweep before continuation.
Preferred entry is below the breakout candle midpoint.
```

### Long after downside sweep

```text
Bullish evidence strengthened by rejection below prior low.
Stop should remain beyond the sweep extreme.
```

### Short after upside sweep

```text
Bearish reversal evidence strengthened.
Current entry is acceptable only if price remains below the reclaimed level.
```

## 14.2 Hard invalidation

Sweep behavior becomes a hard blocker only when:

* the planned direction has already structurally failed;
* the candidate is based on false assumptions;
* price has crossed the defined invalidation;
* resulting stop geometry becomes impossible.

---

# 15. Risk Planning

Trade discovery and risk planning must remain separate.

## 15.1 Required risk profiles

Only two user-facing profiles remain:

```text
STANDARD
FUNDED
```

Remove:

* aggressive;
* extreme;
* any duplicate or experimental risk-mode names;
* strategy eligibility differences based only on these deleted modes.

---

## 15.2 Standard profile

Purpose:

Normal personal trading wallet.

Default configurable rules:

* default account risk per trade: `1%`;
* configurable reasonable range: `0.25%–2%`;
* isolated margin for futures;
* position size based on stop distance;
* fees and slippage included;
* no fixed profit-oriented leverage target;
* leverage chosen only to fit required margin and liquidation safety;
* maximum wallet allocation configurable;
* concurrent exposure limit;
* optional daily loss limit.

Suggested defaults:

```yaml
standard:
  risk_per_trade_pct: 1.0
  max_wallet_margin_pct: 25.0
  max_total_open_risk_pct: 3.0
  max_daily_loss_pct: 5.0
  isolated_margin_only: true
```

The widely used position-sizing principle is to define stop distance first and size the position so a stop hit loses only a small portion of the account. Binance’s current educational guidance uses the 1% rule as a common example.

---

## 15.3 Funded profile

Purpose:

Accounts with firm-style daily and overall loss constraints.

Default rules requested:

```yaml
funded:
  risk_per_trade_pct: 0.5
  max_daily_loss_pct: 5.0
  max_total_drawdown_pct: 10.0
  max_wallet_margin_pct: 20.0
  max_total_open_risk_pct: 2.0
  isolated_margin_only: true
```

All limits configurable because actual funded-account rules may differ.

Funded planner must track:

* starting balance;
* current equity;
* daily starting equity;
* realized daily loss;
* open risk;
* remaining daily loss allowance;
* remaining total drawdown allowance;
* number of active trades;
* correlated directional exposure.

The planner should reduce or reject position size when funded limits would be exceeded.

---

## 15.4 Leverage policy

Leverage is an output of position planning.

It is not a setup score and not a reason to prefer one directional thesis.

Required order:

```text
Choose structural stop
→ calculate permitted wallet loss
→ calculate position quantity
→ calculate notional
→ calculate required margin
→ select sufficient leverage
→ verify liquidation remains beyond stop
```

Futures leverage amplifies losses as well as gains, and liquidation depends on margin and maintenance requirements.

## 15.5 Risk outputs

Every planned trade should include:

* wallet balance;
* profile;
* account risk percentage;
* maximum loss amount;
* entry;
* stop;
* stop distance;
* quantity;
* notional;
* leverage;
* required margin;
* wallet margin percentage;
* estimated entry and exit costs;
* liquidation estimate;
* stop-to-liquidation buffer;
* target rewards;
* expected reward-to-risk;
* funded-limit impact where applicable.

---

# 16. Scanner Output

Default output should be concise and practical.

## 16.1 Scan summary

```text
Eligible contracts: 312
Detailed analyses: 30
Ranked opportunities shown: 15
Long candidates: 9
Short candidates: 6
Ready now: 4
Aggressive now: 5
Pullback preferred: 4
Watch near entry: 2
```

## 16.2 Ranked opportunity card

Each result:

```text
Rank
Symbol
Direction
Strategy
Final rank score
Opportunity score
Setup score
Timing score
Status
Current price
Immediate entry
Preferred entry
Stop-loss
TP1
TP2
TP3
Expected reward-to-risk
Estimated trade horizon
Key evidence
Main cautions
Risk-plan availability
```

## 16.3 Do not hide imperfect candidates

The top list should include the best currently available opportunities even when they contain cautions.

Examples:

```text
Strong setup, moderate chase risk
Valid setup, low liquidity quality
Good direction, pullback preferred
High movement potential, speculative reversal
```

---

# 17. Expected Trade Horizon

Every candidate should classify its expected duration:

* scalp: approximately minutes;
* fast intraday: approximately under a few hours;
* intraday: current trading session;
* short swing: potentially beyond current session.

The default scanner should prioritize:

```text
scalp
fast intraday
intraday
```

Longer short-swing trades can appear but should not dominate rankings unless their opportunity quality is materially stronger.

---

# 18. Logging and Manual Review

Keep detailed logging, but simplify operations.

## 18.1 Log each scan

Store:

* timestamp;
* discovered universe;
* excluded symbols and reasons;
* screener features;
* shortlist;
* all strategy candidates;
* scores;
* selected candidate;
* entry plan;
* warnings;
* risk plan;
* failures;
* active configuration hash or version.

## 18.2 Optional paper outcome logging

Paper mode may record:

* whether entry was reached;
* maximum favorable movement;
* maximum adverse movement;
* target hits;
* stop hit;
* expiration;
* actual holding time.

No automatic learning or automatic configuration changes.

Manual diagnosis should remain possible.

---

# 19. Configuration Simplification

Create one canonical configuration hierarchy.

Suggested files:

```text
config/
├── market.yaml
├── strategies.yaml
├── scoring.yaml
├── risk.yaml
└── runtime.yaml
```

## 19.1 `market.yaml`

Contains:

* provider;
* futures universe rules;
* quote asset;
* liquidity limits;
* spread limits;
* shortlist size;
* final result count;
* timeframe selection;
* blacklists and optional allowlists.

## 19.2 `strategies.yaml`

Contains:

* enabled strategies;
* applicability thresholds;
* strategy-specific settings;
* no empty or legacy duplicate strategy lists.

## 19.3 `scoring.yaml`

Contains:

* opportunity weights;
* setup weights;
* timing weights;
* penalties;
* display thresholds;
* ranking weights.

## 19.4 `risk.yaml`

Contains only:

* standard profile;
* funded profile;
* execution costs;
* leverage safety;
* margin constraints.

## 19.5 `runtime.yaml`

Contains:

* directories;
* logging;
* caching;
* request limits;
* concurrency;
* output defaults.

Remove duplicate settings spread across unrelated files.

---

# 20. Remove or Archive Unnecessary Systems

Before deletion, imports and tests must be traced. No blind mass deletion.

## 20.1 Remove

* gainer mode and all dedicated gainer models;
* aggressive and extreme risk profiles;
* autonomous learning claims and unused automatic optimization flow;
* testnet execution from active CLI and documentation;
* unused advanced-intelligence placeholders;
* duplicate strategy configuration;
* duplicated output-selection compatibility layers;
* verbose and debug presentation modes where they provide no analytical value;
* presentation-only modules built around unused paper operational reports;
* duplicate spot versus futures formatting architecture;
* unnecessary long-timeframe resampling in default workflow;
* dead exports and compatibility facades;
* obsolete commands that only support removed workflows.

## 20.2 Archive or unregister

* spot commands;
* spot paper intake;
* spot reports;
* execution commands;
* old optimization utilities that may still help manual research;
* legacy migration or compatibility code required only for old artifacts.

## 20.3 Keep

* provider adapters;
* candle normalization;
* ticker and order-book support;
* feature engine;
* structure calculations;
* liquidity detection;
* strategy logic that remains useful;
* scoring primitives;
* entry geometry;
* stop and target calculations;
* position sizing;
* liquidation calculations;
* deterministic backtesting core;
* paper trade storage where simple;
* JSON output;
* tests for retained behavior.

---

# 21. Remove Development-Era Terminology

The user-facing and internal repository should not contain roadmap-era labels.

Remove from:

* source-code names;
* classes;
* functions;
* variables;
* payload fields;
* schema fields where safe;
* CLI commands;
* comments;
* docstrings;
* tests;
* fixtures;
* README;
* docs;
* output text;
* report headings;
* filenames.

Patterns to eliminate include:

* numbered phase labels;
* numbered stage labels inherited from development;
* abbreviated milestone labels;
* internal roadmap codenames;
* review names tied to old implementation milestones.

Replace with descriptive functional names.

Examples:

```text
candidate_selection_diagnostics
risk_rejection_diagnostics
paper_validation_review
historical_evidence
trade_entry_diagnostics
```

Names should describe behavior, not the order in which the feature was originally developed.

## 21.1 Compatibility handling

Where old persisted JSON or SQLite records contain legacy keys:

* support a temporary read-only migration adapter if needed;
* write only new descriptive keys;
* remove compatibility after old records are migrated or declared disposable.

---

# 22. CLI Simplification

Primary commands should be limited.

Suggested active CLI:

```bash
apex scan
apex analyze SYMBOL
apex paper-run
apex paper-status
apex backtest
apex config-check
```

## 22.1 `apex scan`

Default behavior:

* discover active futures universe;
* screen all eligible contracts;
* analyze top shortlist;
* display top 15 opportunities;
* use standard risk profile unless selected otherwise.

Options:

```text
--profile standard|funded
--wallet-balance
--risk-per-trade
--results
--shortlist
--direction long|short|both
--output text|json
--paper-log
```

## 22.2 `apex analyze SYMBOL`

Detailed analysis for one symbol.

Shows:

* all applicable strategies;
* scores;
* immediate and preferred entries;
* warnings;
* wallet plan.

## 22.3 Hidden systems

Until re-enabled:

* spot commands;
* testnet execution;
* autonomous optimization;
* elaborate operational review commands.

---

# 23. Execution Sequence

Changes must be implemented in this order.

## Step 1 — Repository inventory

Create exact inventories of:

* gainer references;
* risk-mode references;
* spot registrations;
* development-era terminology;
* presentation modules;
* optimization and execution commands;
* strategy configuration consumers;
* persisted schema dependencies.

No behavior changes yet.

## Step 2 — Lock baseline behavior

Record:

* current CLI command list;
* current scan payload schema;
* current futures scan result;
* existing test count;
* existing configuration files;
* retained core module list.

This is for comparison only.

## Step 3 — Remove gainer system

* remove enum values;
* remove category duplication;
* remove gainer thresholds;
* remove gainer routing;
* simplify scanner to analyze each symbol once;
* update serialization;
* remove dedicated tests and docs;
* ensure no orphan imports remain.

## Step 4 — Simplify risk profiles

* retain `STANDARD`;
* add or retain `FUNDED`;
* remove other profiles;
* separate candidate discovery from wallet approval;
* ensure risk failure remains visible without erasing opportunity analysis;
* update CLI and config.

## Step 5 — Freeze spot

* unregister spot CLI;
* hide spot documentation;
* prevent spot workflows from appearing in default interface;
* preserve source temporarily;
* mark modules as frozen internally without user-facing roadmap language.

## Step 6 — Add dynamic futures universe discovery

* load current Binance contracts;
* filter eligible USDT perpetuals;
* cache exchange metadata;
* respect rate limits;
* add blacklist;
* validate precision and status.

## Step 7 — Build lightweight market screener

* batch ticker collection;
* limited candle calculations;
* opportunity-score model;
* top-shortlist selection;
* explain shortlist reason.

## Step 8 — Refactor detailed strategy analysis

* market-state classification;
* strategy applicability matrix;
* multiple candidate generation;
* no artificial mode-based routing;
* keep alternatives;
* normalize candidate evidence.

## Step 9 — Redesign entry behavior

* immediate and preferred entries;
* simplified statuses;
* warnings instead of unnecessary cancellation;
* sweep detection as evidence and caution;
* reduce wait-only outputs.

## Step 10 — Redesign scoring and ranking

* separate opportunity, setup, timing, and risk scores;
* display top 15 by default;
* retain lower-quality candidates with explicit labels;
* avoid selecting only final-approved setups.

## Step 11 — Simplify presentation

Keep:

```text
text
json
```

Remove duplicate legacy selectors and presentation-only abstractions that do not affect analysis.

## Step 12 — Remove development-era terminology

* rename code;
* rename payload fields;
* rename files where needed;
* clean comments and documentation;
* migrate disposable persisted records;
* run repository-wide verification.

## Step 13 — Simplify logging and paper tracking

* retain scan logs;
* retain paper outcome records;
* remove automatic learning;
* remove unnecessary evidence ceremony;
* keep manual diagnostic visibility.

## Step 14 — Delete confirmed dead code

Only after all references are removed:

* delete orphan modules;
* delete orphan tests;
* delete unused configs;
* delete dead exports;
* delete old CLI registration;
* delete stale docs.

## Step 15 — Update project documentation

README should explain only:

* what Apex does;
* how scanning works;
* strategies;
* scoring;
* entry statuses;
* standard and funded risk;
* commands;
* limitations;
* futures-first status.

No development history or old roadmap language.

---

# 24. Acceptance Criteria

The redesign is complete only when all conditions below are met.

## 24.1 Scanner behavior

* dynamically discovers active Binance futures contracts;
* does not depend on a 16-symbol static list;
* analyzes every selected symbol only once;
* no gainer mode exists;
* lightweight screening runs before full analysis;
* top 15 opportunities display by default;
* results include long and short candidates;
* imperfect candidates remain visible with cautions.

## 24.2 Strategy behavior

* strategy selection is market-state based;
* multiple candidates can exist per coin;
* sweeps influence evidence and warnings;
* sweeps do not automatically cancel unrelated valid trades;
* higher-timeframe disagreement usually reduces score rather than vetoing;
* current-price and preferred-pullback plans are both supported.

## 24.3 Risk behavior

* only standard and funded profiles exist;
* wallet plan is calculated after opportunity discovery;
* structural stop comes before leverage;
* leverage does not increase setup score;
* liquidation remains beyond intended stop with configured buffer;
* funded daily and total loss limits are enforced.

## 24.4 Spot behavior

* spot implementation remains preserved;
* spot is absent from default CLI and documentation;
* no new separate spot architecture is added.

## 24.5 Simplification

* no gainer-specific code remains;
* no old development milestone terminology remains;
* no unnecessary active execution commands remain;
* no autonomous learning claims remain;
* duplicate configs are removed;
* active output modes are text and JSON;
* dead modules are deleted after reference verification.

## 24.6 Quality

Required before accepting each implementation batch:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate

.venv/bin/ruff format <changed-files>
.venv/bin/ruff check <changed-files> --fix
.venv/bin/ruff check <changed-files>
.venv/bin/mypy <changed-scope>
.venv/bin/pytest <relevant-tests>
```

Full repository validation is required after all redesign work.

No validation result should be claimed until actual terminal output is available.

---

# 25. Final User Experience

The intended final command:

```bash
apex scan --wallet-balance 100 --profile standard
```

Expected behavior:

```text
Apex scans the complete eligible Binance futures universe.

It identifies markets with current movement, liquidity, volume,
structure, and entry potential.

It performs detailed analysis on the strongest shortlist.

It displays approximately 10–15 best available opportunities,
including aggressive and pullback-preferred candidates.

Each opportunity includes:
- direction;
- strategy;
- scores;
- current and preferred entries;
- stop;
- targets;
- warnings;
- wallet-aware quantity, margin, leverage, and maximum loss.
```

The system should help the user find trades faster than manual chart-by-chart scanning.

It must not hide almost every usable idea behind conservative confirmation gates.

It must also not pretend that every displayed opportunity is guaranteed to succeed.

The final Apex product is:

> A practical, aggressive but controlled Binance opportunity scanner and trade planner—not a reporting platform, not a roadmap archive, and not a trade-rejection machine.
