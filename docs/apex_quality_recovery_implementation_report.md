# Apex Quality Recovery Implementation Report

Date: 2026-07-27

Status: implemented locally and validated; no commit or push was performed.

## 1. Executive summary

Is implementation ka primary goal retired planning-document identity ko runtime
authority se remove karna, evidence-based authority establish karna, aur quality
recovery ke technical foundations add karna tha.

Ab runtime methodology authority:

- path: `docs/apex_quality_recovery_audit.md`
- version: `quality-recovery-v1`
- identity: path, version, availability status, aur document SHA-256

Future work alag document `docs/apex_quality_recovery_plan.md` mein rakha gaya
hai. Is plan ko runtime authority nahi banaya gaya. Is separation ka purpose yeh
hai ke software implemented facts aur proposed work ko mix na kare.

Trading decisions ke existing public commands aur core execution authorization
rules change nahi kiye gaye. New market profile fields observe-only hain.

## 2. Kya delete kiya gaya

### 2.1 Retired document identity ke references

Current tracked tree se retired methodology document path aur uski legacy
version identity ke references remove kiye gaye.

Yeh references in areas mein replace hue:

- methodology constants
- analysis records
- methodology snapshots
- discovery JSON
- backtest JSON
- configuration metadata
- unit tests
- README documentation links

Kyun delete kiya:

- old document implementation plan tha, current implemented authority nahi;
- runtime metadata plan ko evidence samajh raha tha;
- audit aur future roadmap ko clearly separate karna zaroori tha;
- stale identity downstream reports aur snapshots mein propagate ho rahi thi.

Git history rewrite nahi ki gayi. Purani state normal Git history se recover ki
ja sakti hai.

### 2.2 Generated geometry reports

Yeh five tracked generated reports delete kiye gaye:

- `data/reports/geometry_audit/clo.json`
- `data/reports/geometry_audit/era.json`
- `data/reports/geometry_audit/hei.json`
- `data/reports/geometry_audit/vanry.json`
- `data/reports/geometry_audit/scan.json`

Total removed content: 468,000 se zyada generated JSON lines.

Kyun delete kiya:

- reports retired methodology identity embed kar rahe the;
- yeh generated artifacts thay, source-of-truth code nahi;
- inko manually rewrite karna historical evidence ko misleading bana deta;
- clean regeneration future mein current methodology identity ke saath honi
  chahiye;
- deletion user-authorized thi aur reports Git history se recoverable hain.

### 2.3 Broken README link

README se missing `docs/cli_plan.md` ka link remove kiya gaya.

Kyun delete kiya:

- target file repository mein available nahi thi;
- broken documentation navigation user ko invalid destination par le ja rahi
  thi.

### 2.4 Kya delete nahi kiya

Operator-facing phrases `Trade plan` aur `No-trade plan` preserve ki gayi hain.
Yeh runtime trading output ko describe karti hain, retired document identity ko
nahi.

Existing lifecycle, conditional activation, expiry, invalidation, chase,
canonical selection, shadow isolation, aur no-trade discipline preserve kiye
gaye.

## 3. Kya add kiya gaya

### 3.1 Canonical methodology identity

File: `src/apex/application/methodology_identity.py`

Additions:

- `METHODOLOGY_AUTHORITY_PATH`
- `METHODOLOGY_VERSION`
- `methodology_identity_payload()`
- authority document ka SHA-256
- `available` aur `not_packaged` status

Kyun:

- har analysis/backtest ko exact methodology lineage dene ke liye;
- local checkout aur packaged wheel dono cases honestly represent karne ke
  liye;
- audit document change hone par identity hash change ho aur evidence traceable
  rahe.

### 3.2 Canonical market snapshot contracts

New file: `src/apex/application/quality_contracts.py`

Add kiye gaye public contracts:

- `CanonicalMarketSnapshot`
- `TimeframeSnapshot`
- `MarketBehaviorProfile`
- `ResolvedParameter`
- `ParameterProvenance`

Snapshot records:

- symbol aur decision timestamp
- closed-candle counts
- latest closed-candle timestamps
- active-candle presence
- future closed-candle count
- staleness
- timeframe alignment
- contract availability/status
- price and quantity precision
- listing age when available
- configured cost profile
- evidence availability and missing-evidence reasons
- data-quality lineage
- immutable snapshot identity

Kyun:

- scan, analyze, aur replay ko same point-in-time evidence language dene ke
  liye;
- active ya future candles ko silently decision evidence banne se rokne ke
  liye;
- unavailable derivatives evidence ko fabricate karne ke bajaye explicitly
  missing mark karne ke liye;
- matching frozen input ka stable identity generate karne ke liye.

### 3.3 Market behavior profile

`MarketBehaviorProfile` mein observe-only features add kiye gaye:

- liquidity
- volatility
- directional efficiency/trendability
- chop
- wick/noise behavior
- maturity evidence where available
- false-break frequency
- execution-friction score
- dynamic behavioral cohort

Kyun:

- asset name ko market behavior ka substitute banane se bachna;
- future ranking/gating se pehle features observe aur validate karna;
- decision logic ko symbol-name special cases se behavioral evidence ki taraf
  move karna.

New profile abhi `observe_only=True` hai. Is liye yeh directly trade authorize,
reject, ya rank nahi karta.

### 3.4 Dynamic cohorts and regime hysteresis

File: `src/apex/application/market_intelligence.py`

Changes:

- BTC/ETH name-based `MAJOR` classification remove hui;
- liquidity evidence se dynamic major cohort assignment add hua;
- raw regime aur selected regime dono report hote hain;
- previous regime, hysteresis application, aur transition state expose hoti
  hai;
- chronological backtest previous selected regime ko next decision point tak
  carry karta hai.

Kyun:

- same behavior wale symbols ko same rules milne chahiye;
- label/name alone decision rule nahi hona chahiye;
- marginal regime probability changes par repeated flip-flopping reduce karna;
- live aur historical state contract ko explicit banana.

File-backed `RegimeHistoryStore` ab per-symbol bounded history atomically
persist karta hai. Lookup decision timestamp se strictly pehle ki observation
use karta hai; hidden global mutable state use nahi hoti.

### 3.5 Resolved parameter provenance

File: `src/apex/application/configuration_identity.py`

Changes:

- configuration schema version 2;
- every resolved configuration leaf ka provenance record;
- base value, adjustments, final value, unit, bounds, version, aur reason;
- current production configuration values
  `existing_production_value` classify hote hain;
- methodology identity configuration metadata mein included hai.

Supported provenance classes:

- `existing_production_value`
- `source_defined_value`
- `empirical_candidate`
- `derived_from_training_data`
- `promoted_after_out_of_sample_validation`

Kyun:

- internet se mili setting ko silently production truth banne se rokna;
- value kahan se aayi aur kyun use ho rahi hai yeh inspectable banana;
- future adaptive adjustment ko base value se separate rakhna.

### 3.6 Experiment manifest and walk-forward evaluator

New file: `src/apex/research/experiment.py`

New contract: `ExperimentManifest`

Manifest records:

- schema and experiment identity
- methodology version
- dataset fingerprint
- symbols and cohorts
- timeframes
- chronological validation method
- untouched-final-test flag
- purge and embargo bars
- attempted configuration count
- cost profile
- objective
- exact attempted configuration IDs
- declared strategy, timeframe, and geometry shadow matrix
- fold count, bootstrap samples, drawdown budget, and minimum executed outcomes

Research CLI mein new optional interface:

- `apex research campaign --experiment-spec PATH`
- `apex research campaign --outcomes-file PATH`
- `apex research campaign --data-types TEXT`
- `apex research campaign --include-daily-metrics`

Campaign output:

- schema v6
- legacy schema reference
- evaluation manifest payload
- written `experiment_manifest.json`
- metric-authority reasons
- purged/embargoed expanding folds
- validation-only configuration selection
- one untouched final holdout
- bootstrap lower bound, profit factor, drawdown, stability, and exclusion gates
- reliability bins and Brier decomposition when genuine probabilities exist
- canonical/shadow population isolation and matrix coverage

Kyun:

- experiment choices ko result ke baad silently change hone se rokna;
- dataset aur methodology lineage preserve karna;
- promotion evidence ko reproducible banana.

### 3.7 Backtest cost integrity

Files:

- `src/apex/backtesting/contracts.py`
- `src/apex/backtesting/engine.py`
- `src/apex/cli_commands/backtesting.py`

Changes:

- separate entry and exit fee percentages;
- separate entry and exit slippage percentages;
- explicit cost-profile label;
- configured conservative market-order geometry cost consumption;
- legacy symmetric values ka fallback;
- entry/exit fee calculation independently applied;
- modeled trade metadata mein exact effective cost fields;
- spread-cost inclusion policy explicitly reported.

Kyun:

- entry aur exit costs necessarily identical nahi hote;
- config mein defined conservative market profile ko backtest actually consume
  kare;
- fee, spread, aur slippage provenance visible ho;
- compatibility break kiye baghair old symmetric behavior available rahe.

Observed spread ko cost mein include karne ka flag report hota hai. Cost
components ko silently double-charge karne ka naya path add nahi kiya gaya.

Verified historical funding events entry ke baad se exit tak remaining position
quantity par charge/credit hote hain. Manual funding input separate stress
override ke taur par preserve aur label hota hai. Fee, spread, slippage, actual
funding, aur manual stress ek dusre mein silently merge nahi hote.

### 3.8 PBO and DSR authority

Backtest promotion statistics mein:

- DSR actual distinct attempted strategy/geometry configuration count use karta
  hai;
- PBO unsupported population par numeric value manufacture nahi karta;
- PBO `null` return karta hai;
- reason `insufficient_comparisons` ya
  `requires_fold_level_configuration_vectors` hota hai;
- multiple configurations ke identical fold vectors par bhi PBO unavailable
  rehta hai, kyunke cross-sectional comparison information absent hoti hai.

Kyun:

- single train/test comparison genuine PBO population nahi;
- numeric zero user ko false confidence de sakta tha;
- DSR trials ko actual attempted configurations reflect karna chahiye.

### 3.9 JSON schema compatibility

Backtest/research top-level output schema v6 ki gayi.

Backtest output:

- `schema_version: 6`
- `legacy_schema_version: 5`

Research campaign output:

- `schema_version: 6`
- previous schema identity retained

Additive metadata:

- `methodology_identity`
- snapshot identity
- resolved parameters
- market profile
- evaluation manifest
- metric-authority reasons

Existing v5 backtest sections, including sweep/reclaim diagnostics, retain kiye
gaye hain for the compatibility version.

### 3.10 Scan/analyze integration

Updated files:

- `src/apex/application/analysis_records.py`
- `src/apex/application/discovery_analysis.py`
- `src/apex/application/discovery_contracts.py`
- `src/apex/application/integrated_analysis.py`
- `src/apex/application/decision_analysis.py`
- `src/apex/application/selected_symbol.py`
- `src/apex/application/methodology_snapshot.py`
- `src/apex/application/__init__.py`

Changes:

- canonical snapshot aur market profile analysis object mein carried hain;
- JSON serialization additive hai;
- methodology identity analysis records aur snapshots mein included hai;
- optional prior regime complete call chain se pass hota hai;
- older test doubles ke liye safe attribute fallbacks retain hain.

Kyun:

- scan, analyze, aur replay ko parallel but inconsistent truth banane se rokna;
- operator JSON consumers ko existing fields ke saath new lineage dena;
- backwards compatibility maintain karna.

### 3.11 Public historical evidence archives

Files:

- `src/apex/research/campaign.py`
- `src/apex/domain/futures_evidence.py`

Additions:

- checksum-verified monthly funding archives;
- aggregate-trade parsing and taker-flow aggregation;
- mark, index, and premium-index kline lineage;
- daily five-minute OI and ratio metrics;
- millisecond aur microsecond timestamp normalization;
- stable campaign fingerprint jo run creation time ko identity mein include
  nahi karta.

Ratio-only metrics se raw taker volumes fabricate nahi kiye jate. Historical
contract eligibility metadata absent ho to current exchange status ko past mein
backfill nahi kiya jata.

### 3.12 Point-in-time race protection

Multi-timeframe live fetch ke duran koi candle close ho sakti hai. Context
builder ab declared decision time ke baad open hone wali rows remove karta hai
aur decision boundary cross karne wali row ko provisional active candle
reclassify karta hai. Is se snapshot aur strategy calculation same frozen prefix
consume karte hain.

## 4. Documentation jo create ki gayi

### `docs/apex_quality_recovery_audit.md`

Current implemented behavior aur evidence authority. Ismein canonical call
chain, invariants, contracts, source roles, confirmed limitations, aur evidence
gates documented hain.

### `docs/apex_root_cause_report.md`

Quality problems ke confirmed root causes aur hypotheses ko separate karta hai.

### `docs/apex_quality_recovery_plan.md`

Sirf remaining future work. Runtime authority nahi.

### `docs/apex_market_profile_spec.md`

Market behavior features, evidence availability, cohorting, aur observe-only
promotion rule.

### `docs/apex_regime_strategy_matrix.md`

Strategy families ko regimes, confirmations, invalidation, entry mode, expiry,
aur evidence requirements ke against map karta hai.

### `docs/apex_timeframe_role_matrix.md`

Higher, decision, timing, aur execution timeframes ki authority boundaries.
Low timeframe macro direction manufacture nahi kar sakta.

### `docs/apex_parameter_research_matrix.md`

Parameter source, provenance, validation state, aur promotion requirements.

### `docs/apex_backtest_validation_spec.md`

Chronological folds, untouched test, holdouts, purge/embargo, cost stress,
decision funnel, calibration, and promotion gates.

### `docs/apex_external_sources.md`

External sources, unka applicable scope, aur direct production adoption limits.

### `docs/apex_cleanup_candidates.md`

Is implementation mein removed items aur proof ke baghair retain kiye gaye
candidates.

### `docs/apex_quality_recovery_implementation_report.md`

Yeh current report: implemented changes, deletion rationale, compatibility,
validation, aur remaining work ka detailed record.

### `docs/apex_quality_recovery_validation_report.md`

Verified public archives, real funding replay, canonical/shadow outcome counts,
walk-forward gates, live snapshot smoke, aur explicit no-promotion result.

## 5. Tests jo add ya update kiye gaye

New tests:

- `tests/unit/application/test_quality_recovery_contracts.py`
  - stable snapshot identity
  - future-data rejection
  - parameter leaf coverage
  - bounds validation
  - observe-only market profile
- `tests/unit/backtesting/test_asymmetric_cost_profile.py`
  - asymmetric entry/exit costs
  - cost metadata
- `tests/unit/research/test_experiment_manifest.py`
  - stable manifest identity
  - serialization round trip
- `tests/unit/research/test_walk_forward_evaluation.py`
  - purged/embargoed folds
  - canonical/shadow isolation
  - PBO availability
  - calibration and fail-closed promotion
- `tests/unit/application/test_regime_history_store.py`
  - atomic persistence
  - bounded history
  - strict point-in-time lookup

Updated tests:

- methodology identity and alignment
- dynamic market-intelligence cohorts
- regime hysteresis behavior

## 6. Validation evidence

Completed checks:

- full test suite: 1,911 tests passed;
- Ruff: passed;
- strict mypy: passed across 328 source files;
- root, backtest, and research CLI help: passed;
- `config-check` JSON parse: passed;
- README local link targets: passed;
- retired authority path/version trace search over tracked current files: no
  match;
- Git whitespace/error check: passed;
- live BTCUSDT point-in-time snapshot smoke: passed;
- live ETHUSDT and SOLUSDT chronological replay smokes: passed;
- controlled 34-file public archive campaign: all files verified, zero missing;
- two-configuration purged walk-forward campaign: completed and correctly
  refused promotion.

The original suite count grew because new coverage was added. Real-data
validation details are preserved in
`docs/apex_quality_recovery_validation_report.md`.

## 7. Trading behavior par impact

Intentional non-impact:

- public command names unchanged;
- execution authorization still requires existing readiness contracts;
- no-trade remains a valid outcome;
- observe-only profile fields do not gate or rank;
- conditional activation, invalidation, expiry, chase, canonical, and shadow
  behavior preserved;
- current 0-100 values calibrated probabilities declare nahi kiye gaye.

Intentional evaluation impact:

- backtest configured conservative market costs consume karta hai;
- regime hysteresis chronological replay mein state carry karti hai;
- DSR attempt population honest hai;
- unsupported PBO unavailable hai;
- outputs mein stronger lineage and metric-authority labels hain.

## 8. Abhi kya remaining hai

Implementation machinery complete hai, lekin empirical promotion complete claim
nahi ki gayi:

- historical exchange-information snapshots capture karna;
- declared 336-cell shadow matrix ko multi-symbol/timeframe evidence se fill
  karna;
- minimum untouched executed-outcome population accumulate karna;
- genuine pre-outcome probabilities milne par calibration assess karna;
- koi parameter sirf tab promote karna jab har out-of-sample gate pass ho.

Controlled campaign ne zero canonical trades aur negative observed shadow cells
report kiye. Is liye no-promotion implementation failure nahi, evidence gate ka
correct result hai.

## 9. Repository and Git boundary

- No commit created.
- No branch created.
- No push performed.
- No Git history rewritten.
- Deleted generated reports Git history se recoverable hain.
- Pre-existing `trading_view/` work ko quality-recovery scope mein edit, delete,
  ya claim nahi kiya gaya.

## 10. Final conclusion

Implementation ne retired plan identity ko runtime authority se cleanly remove
kiya, evidence audit ko canonical authority banaya, snapshot/provenance/profile
contracts introduce kiye, actual funding aur regime history integrate ki,
verified historical archives add kiye, aur reproducible walk-forward promotion
machinery complete ki.

Jahan sufficient evidence available nahi tha wahan system numeric certainty ya
completion manufacture nahi karta. Remaining validation work clearly roadmap
mein isolated hai.
