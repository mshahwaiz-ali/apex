# Apex Multi-Market Calibration Campaign Report

**Run date:** 2026-07-27  
**Authority:** research evidence only  
**Production promotion:** rejected  
**Production trading decisions changed:** no

## Executive result

The campaign did not verify an 85–90% win rate or any profitable production
configuration. The best predeclared precision rule reached a `50.9259%`
untouched win rate, but it remained economically invalid after costs:

- 108 untouched outcomes;
- 55 positive outcomes;
- Wilson 95% win-rate lower bound `41.6291%`;
- net expectancy `-0.384038 R`;
- bootstrap 95% expectancy lower bound `-0.644465 R`;
- profit factor `0.547803`;
- maximum drawdown `47.36 R`.

No candidate passed the promotion gates. Apex therefore retained its current
production rules instead of weakening filters to manufacture more trades.

## Dataset and market panel

The fixed representative panel covered July 2025 through June 2026:

- BTCUSDT and ETHUSDT as reporting cohorts;
- BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LINKUSDT, LTCUSDT,
  AVAXUSDT, SUIUSDT, and AAVEUSDT;
- 12 complete UTC months;
- 144 monthly 1m kline archives;
- 144 monthly funding-rate archives;
- 288 checksum-verified files and zero missing files.

The campaign manifest fingerprint was
`a584299843dac323ae166fc6bd61db447b5a9e3ffdc45221952a1ead44eaef73`.
Every archive was read only after its manifest SHA-256 matched.

The panel intentionally spans large-cap, mature alternative, high-volatility,
lower-volatility, and varying monthly-return behavior. Monthly gainer, middle,
and loser labels were calculated after the month only for evaluation
breakdowns; they were never available to the selection rule.

This is a fixed representative panel, not a complete survivorship-free
point-in-time futures universe. Aggregate trades, OI, mark price, index price,
and premium index were not present in this panel and were not fabricated.

## Replay results

| Replay profile | Decisions | Canonical trades | Filled shadow outcomes | Win rate | Net expectancy | Profit factor |
|---|---:|---:|---:|---:|---:|---:|
| 5m × 24 bars | 2,400 | 0 | 4,709 | 24.0603% | -0.735285 R | 0.207668 |
| 3m × 20 bars | 1,200 | 0 | 2,369 | 21.8236% | -0.865509 R | 0.133899 |
| 15m × 24 bars | 1,200 | 0 | 2,356 | 23.6842% | -0.779933 R | 0.171242 |

The 5m profile was the least negative of the three, not a profitable winner.
All 4,800 canonical decisions remained no-trade. The strict production
geometry therefore prevented thousands of negative-expectancy shadow
candidates from being presented as executable trades.

The dominant geometry rejection reasons were:

- costs eliminate reward: 5,277;
- TP1 below lane floor: 5,246;
- stop below the cost/noise floor: 5,081;
- target quality below floor: 5,039;
- TP1 beyond the supported horizon: 323;
- stop beyond the lane limit: 64.

These counts can overlap because one candidate can fail more than one
independent check.

## Predeclared calibration search

The search attempted 864 deterministic rules across:

- candidate source group;
- strategy-family group;
- minimum net TP1 R;
- maximum modeled cost R;
- minimum alignment score;
- maximum conflict score.

Candidate choice was limited to one setup per symbol and decision timestamp.
Five purged chronological validation folds selected the rule, and the final
20% time block was held out until selection was complete.

No rule was positive with profit factor above one in every validation fold.
The final report therefore labels the selected rule as a diagnostic fallback,
not a production setting. The final holdout has now been examined; any future
rule change requires a new, genuinely untouched time period.

## Loss-avoidance and abstention frontier

A follow-up search explicitly tested the request to take fewer losing trades.
It maximized validation win rate at minimum sample floors of 50, 100, and 200
outcomes while keeping selection confined to the five purged development
folds.

| Minimum outcomes | Selected outcomes | Wins / losses | Win rate | Expectancy | Profit factor | Production eligible |
|---:|---:|---:|---:|---:|---:|---|
| 50 | 81 | 59 / 22 | 72.8395% | -0.053628 R | 0.819094 | No |
| 100 | 101 | 67 / 34 | 66.3366% | -0.129750 R | 0.648009 | No |
| 200 | 204 | 120 / 84 | 58.8235% | -0.213051 R | 0.611559 | No |

The 72.84% lane is the highest defensible development accuracy found by the
declared rule family, but it is not profitable. Its average win was only
`0.333355 R`, while its average loss was `1.091447 R`. At that payoff profile,
the break-even win rate is `76.6034%`, above the observed rate. The five folds
were also unstable: the first fold won only 40% and three folds had negative
expectancy.

Behavior and volatility abstention did not solve the problem. Range/chop,
normal-volatility, and high-volatility groups remained negative. The only
aggregate-positive behavior slices had 26–33 observations, negative bootstrap
lower bounds, and no stable fold evidence.

The implemented calibration report is now schema v2 and records this
abstention frontier, average win/loss R, payoff-implied break-even rate, and a
fail-closed production-eligibility decision. Production behavior remains
unchanged. The result shows that rejecting more setups can raise displayed
accuracy without creating economic edge.

## Sweep/reclaim leakage audit

An initial legacy diagnostic appeared to show 24 positive results across 30
unique aggressive reclaim events (`80%`). Inspection found that its
qualification flag summarized the complete post-stop follow-up path, including
future deep-failure candles. It was therefore not a decision-time win rate.

A separate evaluator now:

1. freezes qualification at the reclaim candle close;
2. excludes future deep-failure, hold, and retest facts from entry selection;
3. starts execution on the next candle;
4. applies the configured conservative market entry and exit costs;
5. resolves same-candle stop/target ambiguity against the trade;
6. deduplicates both geometry variants and same-market reclaim episodes;
7. reports chronological thirds and uncertainty bounds.

The clean result was:

- 99 raw qualified entries;
- 96 unique geometry events;
- 81 independent market episodes;
- 32 positive episodes;
- win rate `39.5062%`;
- Wilson 95% lower bound `29.5681%`;
- net expectancy `-0.584931 R`;
- bootstrap 95% lower bound `-0.886769 R`;
- profit factor `0.342376`;
- maximum drawdown `47.3794 R`.

The three consecutive time blocks produced win rates of `44.44%`, `44.44%`,
and `29.63%`; all three had negative expectancy and profit factor below one.
The apparent 80% result was rejected and was not promoted.

## What was implemented

- A manifest-bounded archive reader verifies every consumed kline and funding
  ZIP against the campaign manifest.
- `apex backtest` can replay a verified archive with
  `--archive-dataset-dir` and distribute decisions over the usable history
  with `--sample-full-range`.
- Full-range scheduling waits until every analysis timeframe has sufficient
  history and reserves complete forward replay candles.
- Backtest JSON records archive and decision-sampling authority.
- Historical funding events from every verified monthly archive are loaded.
- `tools/run_archive_calibration_campaign.py` runs the fixed multi-symbol
  campaign and validates schema v6 reports.
- `tools/calibrate_shadow_precision.py` performs the predeclared purged
  walk-forward rule search and reports the loss-avoidance frontier.
- `tools/evaluate_point_in_time_reclaims.py` performs the leakage-safe
  sweep/reclaim audit.
- Tests cover checksum rejection, resampling, full-range scheduling,
  decision-time reclaim selection, and outcome-independent deduplication.

No production threshold, strategy, rank, or trade authorization rule was
changed because the evidence failed.

## Change ledger

Added:

- verified campaign archive readers, so the replay cannot silently consume a
  file outside the manifest or accept a changed ZIP;
- full-range archive replay options, so decisions sample the historical span
  instead of only one recent tail;
- a parallel archive campaign runner, so the same declared configuration is
  applied consistently to every panel symbol;
- a purged walk-forward precision evaluator, so thresholds are judged before
  the final holdout is opened;
- a point-in-time reclaim evaluator, because the legacy full-path diagnostic
  was unsuitable for entry calibration;
- focused tests and this evidence report.

Updated:

- backtest schema-v6 execution assumptions with candle-source and
  decision-sampling authority;
- the existing anchored runner's schema expectation from v5 to v6;
- README, command documentation, and the quality-recovery validation report.

Deleted:

- no source or documentation file was deleted in this calibration patch;
- no Git history was rewritten;
- no runtime threshold was removed or replaced;
- no research failure was hidden. The misleading 80% diagnostic is retained as
  an explicitly rejected finding so the audit trail remains reviewable.

## Validation performed

- Ruff: all repository files passed.
- Mypy: runtime source plus all changed campaign/calibration tools passed (332
  source files).
- Pytest: all 1,930 collected tests passed after the precision-first extension.
- CLI: public command names remained unchanged; archive replay options appeared
  in `apex backtest --help`.
- Configuration: `apex config-check --output json` completed successfully.
- JSON: all 12 baseline reports validated as schema v6 with the v5 compatibility
  marker and `quality-recovery-v1` audit authority.
- Documentation: 15 Markdown files were checked and had zero missing local
  links.
- Retired methodology identity cleanup: the current tree contains no obsolete
  authority path or version marker.
- Diff hygiene: `git diff --check` passed.

An intentionally broad `mypy src tools` invocation also exposed 36 pre-existing
typing errors in five unrelated exploratory scripts. Those scripts were not
changed or used as campaign authority. They remain visible technical debt and
do not alter the successful authoritative-source and changed-tool check above.

## Reproduction

```bash
python3 tools/run_archive_calibration_campaign.py \
  --archive-dataset-dir data/research/calibration_2025_2026 \
  --output-dir data/research/calibration_2025_2026/baseline \
  --decision-points 200 \
  --replay-timeframe 5m \
  --replay-candles 24

python3 tools/calibrate_shadow_precision.py \
  --report-dir data/research/calibration_2025_2026/baseline \
  --archive-dataset-dir data/research/calibration_2025_2026 \
  --output data/research/calibration_2025_2026/precision_calibration_report.json

python3 tools/evaluate_point_in_time_reclaims.py \
  --report-dir data/research/calibration_2025_2026/baseline \
  --archive-dataset-dir data/research/calibration_2025_2026 \
  --output data/research/calibration_2025_2026/point_in_time_reclaim_report.json
```

The local dataset and generated reports are research artifacts and are not
treated as source-controlled runtime configuration.

## Honest highest win/loss conclusion

The highest clean untouched rule result in this campaign was 55 wins and 53
non-wins, or approximately `1.04:1` by count, but its loss magnitude made it
unprofitable. The clean sweep/reclaim result was 32 wins and 49 non-wins, or
approximately `0.65:1`.

An 85–90% rate would require at least eight or nine correct outcomes per ten
trades on new data. This campaign provides no evidence that Apex can deliver
that rate. The defensible result is to preserve no-trade discipline and
continue collecting a new forward holdout before any calibration is promoted.

## Precision-first follow-up status

The follow-up implementation converts this report's loss-suppression question
into explicit research and runtime contracts. It does not reinterpret the
`72.8395%` validation lane as profitable and does not reuse the inspected final
period as untouched evidence.

Implemented after this campaign:

- separate decision-time feature and future-outcome JSONL contracts;
- group-safe chronological purge/embargo;
- deterministic fill and positive-net model families with validation-only
  isotonic calibration and threshold selection;
- payoff-aware precision frontiers and shadow management/cost stress;
- checksum-verified runtime precision artifacts;
- observe-only, paper, and fail-closed enforcement states;
- strict historical and eight-week paper promotion evaluators.

Current activation remains `observe_only`. There is no trusted promoted runtime
artifact in the repository, no newly proven 65% profitable final population,
and no completed fresh paper sample. Therefore this engineering update changes
neither production thresholds nor the honest highest clean campaign result
reported above.
