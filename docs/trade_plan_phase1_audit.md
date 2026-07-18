# Trade Plan Phase 1 — Current Pipeline Audit

## Status

- Phase: 1 — Current pipeline audit
- Authority: `docs/trade_plan.md`
- Scope: documentation and mapping only
- Behavior changes: none
- Branch: `main`

This document records the existing Apex discovery and analysis pipeline before methodology changes begin. It is intentionally descriptive. Findings here identify later refactoring and methodology work, but Phase 1 does not change trading behavior.

## 1. Required Phase 1 scope

The trade plan requires the current implementation to be mapped across:

- scan and analyze command entry points;
- screening and shortlisting;
- market-data loading and candle handling;
- feature calculation and timeframe roles;
- environment and market-state classification;
- strategy generation and routing;
- candidate selection and rejection;
- entry, stop, target, and management construction;
- scoring, confidence, and ranking;
- text and JSON presentation;
- recording and reporting;
- backtesting and production equivalence.

## 2. User-facing command entry points

### 2.1 `apex scan`

Current path:

```text
src/apex/cli_commands/scanner.py
→ bootstrap configuration
→ create market-data services
→ select_futures_scan_symbols
→ scan_symbols
→ serialize_scan_result
→ render_discovery_scan or JSON
```

The scanner first discovers and shortlists symbols, then performs detailed analysis on each selected symbol.

### 2.2 `apex analyze SYMBOL`

Current path:

```text
src/apex/cli_commands/analysis.py
→ bootstrap configuration
→ create market-data services
→ analyze_selected_symbol
→ normalize_market_symbol
→ analyze_symbol
→ serialize_symbol_analysis
→ render_discovery_analysis or JSON
```

The selected-symbol wrapper only normalizes the user input before forwarding it to the canonical symbol-analysis function.

## 3. Shared analysis core

Both command paths substantially converge on:

```text
apex.application.decision_analysis.analyze_symbol
```

Current convergence:

```text
apex scan
→ scan_symbols
→ analyze_symbol

apex analyze SYMBOL
→ analyze_selected_symbol
→ analyze_symbol
```

This is directionally consistent with the trade plan. Symbol selection is separate, while detailed symbol analysis is shared.

## 4. Current detailed analysis sequence

The observed analysis path is:

```text
build_strategy_context
→ build_market_environment
→ route_market_strategies
→ analyze_strategies
→ apply_strategy_routing
→ analyze_futures_phase5
→ build_discovery_assessment
→ build_candidate_ranking_snapshot
→ attach market state and strategy route
→ serialize and present
```

Primary orchestration files:

- `src/apex/application/decision_analysis.py`
- `src/apex/application/integrated_analysis.py`
- `src/apex/application/discovery_analysis.py`
- `src/apex/application/discovery_context.py`
- `src/apex/application/market_strategy_router.py`
- `src/apex/application/market_state.py`
- `src/apex/application/futures_quality.py`
- `src/apex/application/candidate_ranking.py`

## 5. Screening and shortlisting

`apex scan` uses the futures scan-selection layer before detailed analysis:

```text
select_futures_scan_symbols
→ futures universe
→ ticker prefilter
→ futures screener
→ candle-supported shortlist
→ detailed shared analysis
```

Static symbols may override live discovery through `--symbols-file`.

Discovery selection and trade approval are already separate at a high level, but the later audit must verify that screening metrics do not leak into trade approval as undocumented gates.

## 6. Market-data and candle handling

### 6.1 Provider reuse

The integrated layer wraps the provider in a caching adapter so repeated requests for candles, ticker, order book, and exchange filters can be reused during one symbol analysis.

### 6.2 Candle-limit discrepancy

A concrete command-path discrepancy exists:

- `apex scan` passes `candle_limit + 1` from the CLI into `scan_symbols`.
- `decision_analysis.analyze_symbol` adds another `+1` before calling the integrated layer.
- `apex analyze` passes its configured candle limit without the scanner's CLI-level increment.

Therefore, scan and analyze may request different raw candle counts for the same user-supplied `--candles` value.

This is an audit finding only. It must not be changed until the closed-candle contract and all dependent tests are mapped.

## 7. Feature and timeframe context

The current context exposes per-timeframe data quality, role, and features including:

- ATR;
- fast and slow EMA;
- VWAP;
- RSI and RSI slope;
- stochastic and stochastic RSI;
- MACD histogram;
- rate of change;
- relative volume;
- trend strength;
- range position;
- volatility expansion.

Timeframe roles and staleness limits are configuration-driven and passed through both command paths.

Further audit is required to determine:

- how active versus closed candles are handled per feature;
- whether all configured roles are used consistently;
- whether correlated indicators are counted repeatedly;
- whether structure is primary or reconstructed indirectly from indicators.

## 8. Environment and market-state classification

The current integrated flow builds a multi-timeframe market environment, routes strategies from that environment, and then derives a market-state snapshot from the decision regime plus environment.

Current concepts include:

- primary regime;
- higher-timeframe bias;
- alignment and conflict scores;
- long and short suitability;
- tradeable state;
- strategy priority;
- preferred direction;
- routing score.

Further audit is required to compare current states and reason codes against the trade-plan primary and secondary state taxonomy.

## 9. Strategy generation and routing

Current sequence:

```text
analyze_strategies(context)
→ apply_strategy_routing(...)
→ analyze_futures_phase5(...)
```

The strategy layer produces candidates, routing filters or prioritizes them, and the futures-quality phase scores and selects a candidate.

Further audit must map every active strategy to:

- compatible and prohibited states;
- mandatory and optional evidence;
- confirmation policy;
- blockers and penalties;
- entry models;
- invalidation method;
- target method;
- expiry policy;
- historical segment key.

## 10. Candidate selection and rejection

The futures-quality phase currently returns:

- all scored candidates;
- ranked candidates;
- rejected candidates;
- selected candidate;
- no-trade reason;
- per-candidate outcome, score, evidence, metadata, and reasons.

The public decision layer exposes high-level reason codes such as:

- `ENVIRONMENT_BLOCKED`;
- `NO_ROUTED_STRATEGY`;
- `NO_CANDIDATE_GENERATED`;
- `CANDIDATE_REJECTED`;
- `NO_TRADE`;
- or the selected setup's entry status.

Further audit must identify which rejections are true logical gates and which should later become visible soft penalties under the trade plan.

## 11. Entry, stop, targets, and management

Current serialized setup fields include:

### Entry

- lower and upper zone boundaries;
- preferred entry;
- current price;
- maximum chase price;
- whether current price is inside the zone;
- entry status.

### Stop

- stop price;
- absolute and percentage distance;
- quality score and band;
- rationale.

### Targets

- label;
- price;
- reward;
- risk/reward;
- partial-close percentage;
- rationale.

### Management

- policy kind;
- trigger;
- action;
- rationale;
- warnings.

Further audit must trace the exact builders and determine whether invalidation, stop buffer, execution cost, liquidation geometry, movement envelope, duration, and expiry are currently separate or conflated.

## 12. Scoring, confidence, and ranking

Current outputs include:

- candidate final score;
- opportunity score;
- setup score;
- timing score;
- trade-quality score;
- rank penalty score;
- setup confidence score;
- quality label;
- final rank score.

The scanner sorts primarily by candidate ranking data when available. Older internal layers also contain setup-confidence and best-R sorting helpers.

Further audit must establish the actual active ranking path and identify dormant or overlapping sort logic.

The trade plan requires confidence to describe analytical quality rather than uncalibrated win probability. Current output wording and score semantics must therefore be mapped precisely before Phase 11 or Phase 13 changes.

## 13. Presentation and serialization

### Scanner

The scanner serializes ranked results, optionally attaches screening details and configuration metadata, and renders text through `render_discovery_scan`.

### Selected-symbol analysis

The analyze command serializes one symbol, attaches configuration metadata, and renders text through `render_discovery_analysis`.

Both expose the same underlying setup contract, but use different top-level payload and presentation paths. Phase 1 must identify intentional command-level differences versus analysis-wording differences that violate the shared-core requirement.

## 14. Recording and reporting

Both commands can build a normalized analysis record and write it to:

- append-only JSONL;
- SQLite.

The scanner can additionally write a JSON report.

Further audit must verify that persisted records contain enough source data and decision metadata for production-equivalent replay and later calibration.

## 15. Backtesting audit boundary

The backtesting subsystem still requires a complete file-level map. The remaining Phase 1 audit must establish:

- strategy and feature reuse between live and backtest paths;
- candle-close and active-candle equivalence;
- entry-touch assumptions;
- same-candle stop/target ambiguity handling;
- fees, funding, spread, and slippage;
- partial exits and management policies;
- changing historical symbol universe;
- liquidation handling;
- segmentation and stored metrics;
- train, validation, test, and walk-forward support.

No profitability conclusion is permitted from the Phase 1 audit.

## 16. Confirmed initial findings

1. Scan and analyze already share the canonical detailed symbol-analysis function.
2. Symbol selection is correctly separated from detailed analysis at the command level.
3. The application stack contains several historical wrapper layers, which increases the risk of duplicated transformations and inactive logic.
4. Scan and analyze have a raw candle-limit discrepancy caused by increments at different layers.
5. Market environment, market state, strategy routing, candidate scoring, and candidate ranking exist, but their taxonomies and gates are not yet normalized to `trade_plan.md`.
6. Entry, stop, targets, management, confidence, and ranking are exposed, but the audit must still trace their exact construction and semantics.
7. Text and JSON presentation remain command-specific above the shared analysis result.
8. Backtest equivalence has not yet been established.

## 17. Remaining Phase 1 work

- Map futures screening and shortlist scoring in detail.
- Map all context features and closed-candle rules.
- Map market-environment and market-state rule tables.
- Inventory active strategies and evidence requirements.
- Trace entry-zone construction and chase rules.
- Trace structural invalidation and stop construction.
- Trace target generation, partial exits, duration, and expiry.
- Trace hard blockers, soft penalties, confidence, and ranking.
- Trace public serializers and renderers field by field.
- Map backtest orchestration and compare it with live analysis.
- Produce a final gap matrix against every Phase 1 category.

## 18. Change log

### Initial baseline

- Added the Phase 1 audit artifact.
- Recorded the top-level command and shared-core flow.
- Recorded the first confirmed scan/analyze discrepancy.
- Made no trading behavior changes.
