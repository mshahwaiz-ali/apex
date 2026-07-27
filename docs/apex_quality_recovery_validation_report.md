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
