# Apex Quality Recovery Validation Report

**Run date:** 2026-07-27  
**Authority:** research evidence only  
**Promotion decision:** not promoted

## Completion status

The planned engineering implementation is complete:

- methodology authority and documentation cleanup;
- immutable point-in-time snapshots and closed-candle boundary enforcement;
- historical derivatives archive ingestion;
- event-level funding and conservative execution costs;
- persistent regime hysteresis;
- observe-only behavioral profiles and parameter provenance;
- canonical/shadow outcome isolation;
- purged walk-forward evaluation, calibration diagnostics, and fail-closed
  promotion gates;
- schema v6 output with one-version v5 compatibility;
- unit, static, CLI, configuration, documentation-link, and representative
  real-data validation.

This does **not** mean that a profitable configuration has been proven. Empirical
promotion remains intentionally incomplete because the controlled evidence did
not pass the predeclared gates. More multi-symbol/month executed outcomes,
complete shadow-matrix coverage, and genuine untouched probability records are
still required before any production promotion.

No commit, push, or Git-history rewrite was performed as part of this local
implementation.

## Precision-first extension

The subsequent precision-first recovery patch added engineering needed to
research loss suppression without weakening the deterministic methodology:

- immutable `CandidateFeatureSnapshot` records contain decision-time candidate,
  score, geometry, market-profile, snapshot-lineage, missing-mask, dataset,
  configuration, and code identities;
- `CandidateOutcomeLabel` stores fill and future positive-net results
  separately, with a win defined as realized net `R > 0`;
- duplicate geometry is removed inside a symbol/decision-time group, and the
  grouped chronological splitter prevents any group crossing train,
  calibration, or untouched-final partitions;
- the existing deterministic logistic-regression/HGB and isotonic framework
  trains fill and post-fill positive-net families;
- precision frontiers report coverage, win rate, expectancy, profit factor,
  average win/loss, and payoff-implied break-even accuracy;
- threshold choice is calibration-only and requires positive expectancy plus
  profit factor at least `1.20`;
- current/retest, no-chase, TP1, partial/runner, higher-cost, and delayed-fill
  alternatives are labeled `shadow_only` and counted in the attempted
  configuration population;
- `RuntimePrecisionArtifact` and `RuntimePrecisionDecision` expose calibrated
  fill/positive-net probabilities, expected-R intervals, sample authority,
  checksums, modes, states, and reason codes;
- scan, analyze, replay JSON, operator diagnostics, and SQLite opportunity rows
  receive additive precision metadata;
- default mode is `observe_only`; paper is also non-mutating; enforcement is
  fail-closed and requires both historical and fresh paper promotion.

The runtime gate is downstream of methodology, HTF, geometry, and deterministic
candidate validation. It can only rerank or suppress an already-valid
candidate. It cannot approve a rejected candidate, invent an entry/stop/target,
override direct HTF opposition, bypass chase or invalidation, or turn a
conditional opportunity into an executable trade.

### Precision promotion status

Production enforcement is **not approved**. The already inspected campaign
cannot become untouched evidence, and no complete fresh post-June-2026 period
or eight-week paper population exists as of this report date. The historical
gate also requires at least 200 untouched filled outcomes, `65%` point win
rate, a `55%` Wilson lower bound, positive bootstrap expectancy, profit factor
at least `1.20`, positive adequate folds and exclusion tests, four stable
cohorts, positive Brier skill, calibration error at most `0.05`, DSR at least
`0.95`, and PBO at most `0.20`.

Paper authority subsequently requires at least 50 resolved fills over eight
weeks, eight symbols, four cohorts, no symbol above 20%, `65%` point win rate,
a `50%` Wilson lower bound, positive bootstrap expectancy, and profit factor at
least `1.20`. If any gate fails, Apex remains paper/observe-only.

Precision-first verification completed with all 1,930 collected tests passing,
Ruff clean across source/tests/tools, mypy clean across all 331 authoritative
source files, successful configuration validation, visible research CLI
feature/outcome options, valid SQLite schema-v5 migration, and a clean
`git diff --check`.

A three-decision BTCUSDT archive smoke then exercised the real schema-v6
backtest path. It produced 18 decision-time feature snapshots across canonical
and shadow-counterfactual populations, 10 separately resolved outcome labels,
and zero production trades. The result retained the schema-v5 compatibility
marker and did not force a trade.

## Controlled public-data campaign

The controlled campaign used BTCUSDT for June 2026 and the declared
`quality-recovery-v1` methodology. Its stable dataset fingerprint was:

`383d0396a341b2e1434e8782a40a249093c753712e4dd890f69e16507e218e0b`

Archive verification:

- 34 verified files and zero missing files;
- one funding archive;
- 30 daily OI/ratio metric archives;
- one mark-price 1m archive;
- one index-price 1m archive;
- one premium-index 1m archive.

Contract-metadata history and raw aggregate taker flow were not supplied. Their
coverage is explicitly unavailable; no values were fabricated.

## Replay evidence

The 100-decision controlled replay produced:

- 100 canonical decisions and zero forced canonical trades;
- 100 canonical no-trade evaluation rows;
- 207 raw base shadow trades, of which 190 became filled evaluation rows;
- 182 filled shadow rows under the higher funding-cost stress configuration.

A separate controlled holding-period replay consumed one real June funding
event across 500 candles. Historical funding cost was `3.269013048`; manual
funding stress was zero. The event and manual components were reported
separately.

## Walk-forward result

The experiment declared two configurations, five expanding folds, six-bar
purge and embargo, all 12 strategy families, seven timeframes, and four geometry
profiles.

Final holdout evidence:

- 17 canonical decision rows;
- zero executed canonical outcomes;
- 17 no-trade outcomes;
- net expectancy `0.0 R`;
- bootstrap 95% lower bound `0.0 R`;
- profit factor unavailable because no executed wins/losses existed;
- maximum drawdown `0.0 R`;
- calibration unavailable because genuine untouched probabilities and binary
  outcomes were absent.

PBO is unavailable because the two configuration fold vectors had no
cross-sectional variation. Returning a numeric zero would overstate evidence.

The declared shadow matrix contained 336 cells. Six cells were observed
(`1.7857%` coverage), all on 5m shadow geometry, and their observed net
expectancies were negative. Shadow results did not enter canonical expectancy.

## Promotion decision

No configuration was promoted. The fail-closed gates reported:

- insufficient untouched executed outcomes;
- bootstrap lower bound not above zero;
- profit factor not above one;
- non-positive validation folds;
- cohort instability;
- best-symbol/month dependence could not be cleared;
- PBO unavailable;
- declared shadow matrix incomplete.

This is a valid quality-recovery result: the implementation completed the
measurement and promotion machinery, while the evidence correctly refused a
production change.

## Broad multi-market calibration

A second campaign expanded the evidence to 12 representative symbols over 12
complete months, with 288 manifest-verified kline and funding archives. It ran:

- 2,400 full-range decisions at 5m × 24;
- 1,200 full-range decisions at 3m × 20;
- 1,200 full-range decisions at 15m × 24;
- 864 predeclared precision rules through five purged validation folds and one
  final 20% holdout.

All 4,800 canonical decisions remained no-trade. Shadow candidates were
negative after conservative costs in every horizon. The selected final-holdout
rule reached a `50.9259%` win rate but had `-0.384038 R` expectancy, a
`-0.644465 R` bootstrap lower bound, and `0.547803` profit factor. It was not
promoted.

A validation-only abstention frontier then tested stricter loss avoidance. The
highest-accuracy lane produced 59 wins and 22 losses (`72.8395%`), but its
average win was `0.333355 R` versus a `1.091447 R` average loss. Its break-even
requirement was therefore `76.6034%`; realized expectancy was `-0.053628 R`
and profit factor was `0.819094`. It was unstable across folds and remained
observe-only.

A legacy sweep/reclaim diagnostic initially displayed an 80% result on 30
events. A leakage audit showed that the eligibility flag included future
post-stop path facts. The new point-in-time evaluator reduced the clean
independent population to 81 episodes with a `39.5062%` win rate,
`-0.584931 R` expectancy, and `0.342376` profit factor. This candidate was also
rejected.

The full market panel, timeframe results, selection process, leakage finding,
and reproduction commands are recorded in the
[`Apex Multi-Market Calibration Campaign Report`](apex_calibration_campaign_report.md).

In practical terms:

- engineering status: **complete**;
- validation framework status: **complete and operational**;
- controlled campaign status: **completed**;
- production parameter promotion: **not approved**;
- long-term empirical evidence collection: **ongoing**.

## Live point-in-time smoke

The live BTCUSDT analysis reported:

- contract status `TRADING`;
- valid price/quantity precision;
- listing age present;
- zero future closed candles on every timeframe;
- one provisional active candle per timeframe;
- snapshot quality `degraded`, not rejected, solely because active candles were
  present but non-authoritative;
- persisted prior regime history available.

The smoke confirms that candles closing during a multi-timeframe fetch cannot
cross the declared decision boundary and become historical evidence.

## Representative cross-symbol replay smokes

Five-decision live chronological replays were also completed for ETHUSDT and
SOLUSDT with six replay candles:

- both emitted schema v6 with the v5 compatibility marker;
- both retrieved 500 historical funding events;
- ETH produced five canonical no-trade decisions and five isolated shadow
  trades;
- SOL produced five canonical no-trade decisions and zero shadow trades;
- neither replay forced a canonical trade;
- both reported PBO unavailable because no valid comparison population existed.

These smokes verify provider, funding, replay, JSON compatibility, and
no-trade/shadow isolation across representative symbols. They are diagnostics,
not promotion evidence.
