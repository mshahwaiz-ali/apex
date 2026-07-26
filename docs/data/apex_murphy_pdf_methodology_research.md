# Apex Trading Project — PDF Methodology Research

**Source:** John J. Murphy, *Technical Analysis of the Financial Markets*  
**Uploaded PDF coverage:** 150 scanned PDF pages. The scan reaches **printed book page 113**, ending in Chapter 5 during the discussion of complex head-and-shoulders patterns. It does **not** contain the remainder of the book listed in the table of contents.

**Purpose:** Translate the material actually present in the uploaded PDF into implementation-oriented research for Apex, without changing repository architecture or writing code.

---

## 0. Scope, evidence standard, and interpretation rules

This document distinguishes four things:

1. **What the author explicitly states**
2. **Operational interpretations suitable for a deterministic engine**
3. **Rules that need empirical validation**
4. **Material too subjective to automate safely**

The book presents technical-analysis principles and examples, not modern statistical proof. Therefore:

- No setup is treated as inherently profitable.
- Pattern detection is separated from trade approval.
- Directional bias is separated from entry timing.
- Expected price movement is separated from leveraged return.
- A candlestick or chart pattern does not automatically imply a target unless a target method is given.
- Active-candle observations are provisional unless the cited passage explicitly permits intraperiod use.
- Closing-price confirmation is preferred where the source explicitly requires it.
- Where the book gives alternative thresholds, the alternatives are preserved rather than collapsed into one universal rule.

**PDF page vs. printed page:** References use both:
- `PDF p.X` = scanned PDF page number.
- `Book p.Y` = printed page number visible on the page.

---

# 1. Executive findings for Apex

## 1.1 Highest-impact conclusions

### 1. A trade state such as `READY_NOW` must require more than pattern proximity

The source repeatedly separates:
- trend or market context,
- pattern development,
- confirmation,
- timing,
- and risk control.

Examples:
- A trendline break alone is a warning, not automatically a full reversal (PDF pp.105–109; Book pp.68–72).
- A head-and-shoulders top is not complete until the neckline is decisively broken, preferably on a closing basis (PDF pp.143–144; Book pp.106–107).
- A reversal pattern requires a prior trend to reverse (PDF pp.138–140; Book pp.101–103).

**Apex implication:** `READY_NOW` should not be emitted merely because current price touches a zone or the active candle resembles a trigger. It should require:
1. eligible regime,
2. valid structure,
3. completed confirmation condition,
4. acceptable entry geometry,
5. valid stop location,
6. sufficient projected reward after costs,
7. no rejection rule.

### 2. Closed-candle confirmation must be explicit and setup-specific

The book gives special weight to closes:
- Dow Theory uses closing prices for signals; intraday penetration alone is insufficient (PDF pp.67–68; Book pp.30–31).
- Trendline breaks are more significant on a close beyond the line than an intraday penetration (PDF p.108; Book p.71).
- Head-and-shoulders neckline completion is framed as a decisive closing violation (PDF pp.143–144; Book pp.106–107).

**Apex implication:** Every setup needs:
- `confirmation_basis = close | intrabar_allowed | mixed`
- `confirmation_timeframe`
- `active_candle_status = provisional | actionable`
- clear output wording when the trigger is not yet closed.

### 3. Entry zones should be structural ranges, not arbitrary single prices

The source treats support and resistance as areas, not exact ticks (PDF pp.92–101; Book pp.55–64). Importance rises with:
- time spent in the zone,
- volume transacted there,
- recency,
- number of tests,
- and distance moved away.

**Apex implication:** Replace single-price “entry zones” with:
- structural zone low/high,
- ideal entry,
- maximum chase,
- invalidation boundary,
- and confirmation level.

### 4. Targets must come from structure and setup, not a fixed percentage

Target methods in the covered pages include:
- measured move from channel width (PDF p.122; Book p.85),
- trendline measuring implication (PDF pp.109–111; Book pp.72–74),
- head-and-shoulders height projected from neckline (PDF pp.145–147; Book pp.108–110),
- support/resistance and prior reaction levels as target adjustments (PDF pp.146–147; Book pp.109–110),
- gap measurement for runaway/measuring gaps (PDF pp.131–133; Book pp.94–96).

**Apex implication:** A target engine should rank:
1. nearest structural obstacle,
2. minimum pattern objective,
3. channel/measured target,
4. higher-timeframe level,
5. optional runner target.

No universal 10% target is supported.

### 5. Time horizon should be derived from timeframe and structure

The source emphasizes:
- three trend degrees,
- nesting of short, intermediate, and major trends,
- different chart horizons,
- and the need to align the analysis with the trading horizon (PDF pp.46–47, 82–83, 89–91; Book pp.9–10, 45–46, 52–54).

**Apex implication:** Setup expiry and expected holding time should be linked to:
- trigger timeframe,
- pattern width/duration,
- volatility,
- distance to objective,
- and whether the setup is minor, intermediate, or major.

### 6. Volume is confirmation, not a standalone direction engine

The source repeatedly treats volume as secondary but important confirmation:
- volume should generally expand in the trend direction (PDF p.64; Book p.27),
- tops may complete without strong volume expansion,
- bottoms usually require stronger buying volume (PDF pp.140–149; Book pp.103–112).

**Apex implication:** Volume should modify confidence and eligibility, not independently create a trade.

### 7. Failed breakouts and role reversals deserve first-class strategy handling

Covered material supports:
- support becoming resistance and vice versa after meaningful penetration (PDF pp.94–100; Book pp.57–63),
- failed trendline breaks and whipsaw filtering (PDF pp.107–109; Book pp.70–72),
- failed head-and-shoulders patterns when price recrosses the neckline (PDF p.150; Book p.113).

**Apex implication:** Add explicit states:
- `BREAKOUT_UNCONFIRMED`
- `BREAKOUT_CONFIRMED`
- `RETEST_PENDING`
- `FAILED_BREAKOUT`
- `PATTERN_FAILED`
- `INVALIDATED`

---

# 2. Core principles

## 2.1 Market action discounts available information

**Source:** Chapter 1, PDF pp.38–40, Book pp.1–3.

### Method
Price, volume, and open interest are treated as the observable market action. The author argues that known supply/demand influences are reflected in price.

### Apex interpretation
Apex may prioritize market-derived data for timing, but should not claim that all information is perfectly incorporated. The useful implementation principle is:

- price structure is the primary observable,
- volume and open interest are confirmation layers,
- external context may still be used as a risk modifier.

### Deterministic candidate
- **Directly supported:** price action is primary.
- **Operational interpretation:** do not reject a technically valid setup solely because no narrative catalyst is available.
- **Requires validation:** whether external news filters improve crypto results.

### Existing Apex mapping
Likely maps to the shared market-context and feature layers.

### Likely change
Ensure outputs explain the structure and evidence, not speculative stories.

### Tests
- Same candles produce same structure result regardless of missing news.
- External context changes risk/eligibility only through explicit rules.

---

## 2.2 Prices move in trends

**Source:** PDF pp.40–41, Book pp.3–4.

### Method
A trend is assumed more likely to persist than reverse until evidence of reversal appears.

### Market context
All directional markets.

### Long/short
- Long: rising peaks and troughs.
- Short: falling peaks and troughs.
- No trade/trend-following disabled: sideways structure.

### Confirmation
Persistence is not certainty. A reversal requires evidence.

### Apex change
Trend persistence should be the default prior, not an automatic entry signal.

### Tests
- An uptrend does not automatically create a long.
- A countertrend setup must meet stricter reversal evidence.
- Sideways markets route away from trend-following setups.

---

## 2.3 History repeats through recurring behavior

**Source:** PDF pp.41–42, Book pp.4–5.

### Method
Chart patterns are interpreted as recurring expressions of market psychology.

### Automation boundary
Pattern geometry can be measured. Psychological narrative cannot be verified directly.

### Apex change
Use objective geometry and confirmation; avoid wording such as “traders are definitely trapped” unless based on measurable position/flow evidence.

---

## 2.4 Analysis and timing are separate

**Source:** PDF pp.43–44, Book pp.6–7.

### Method
The decision process has two stages:
1. market analysis or directional view,
2. timing of entry/exit.

The author stresses timing because leverage makes small adverse moves consequential.

### Apex change
Create separate fields:
- `market_bias`
- `setup_eligibility`
- `entry_state`
- `execution_trigger`
- `risk_geometry`

A bullish bias must not equal `READY_NOW`.

### Tests
- Bullish structure + poor entry geometry => no trade or wait.
- Neutral structure + local trigger => no trade unless a range strategy is eligible.
- Good setup + excessive chase => missed entry.

---

## 2.5 Technical analysis is adaptable across markets and timeframes

**Source:** PDF pp.44–47, Book pp.7–10.

### Method
The same broad principles can be applied to different markets and time dimensions, but instrument characteristics matter.

### Apex implication
Shared core is appropriate for `apex scan` and `apex analyze SYMBOL`. Symbol selection differs; trade-analysis logic should not.

### Required market adaptation
Crypto-specific:
- perpetual funding,
- open interest,
- 24/7 sessions,
- liquidation cascades,
- venue liquidity,
- contract precision.

These are not provided by the book and must be added separately.

---

## 2.6 Subjectivity and self-correction

**Source:** PDF pp.52–55, Book pp.15–18.

### Method
Chart analysis contains subjectivity. The author notes that systems can become self-correcting when crowd behavior changes.

### Apex implication
- Avoid pretending confidence scores are objective truth.
- Preserve uncertainty.
- Backtest exact definitions.
- Monitor regime drift.

### Output wording
Prefer:
- “confirmed by X and Y”
- “provisional”
- “eligible but not triggered”
- “pattern candidate”
- “insufficient evidence”

Avoid:
- “guaranteed”
- “certain reversal”
- “must pump”
- “ready now” without execution basis.

---

# 3. Trend and market structure

## 3.1 Trend definition: peaks and troughs

**Source:** PDF pp.86–88, Book pp.49–51.

### Structure
- Uptrend: successively higher peaks and higher troughs.
- Downtrend: successively lower peaks and lower troughs.
- Sideways: roughly horizontal peaks and troughs.

### Objective measurements
Apex can calculate:
- swing highs/lows,
- higher-high count,
- higher-low count,
- lower-high count,
- lower-low count,
- slope of swing sequence,
- swing amplitude,
- swing recency,
- structural break.

### Subjective risks
Swing-point selection depends on sensitivity.

### Likely change
Trend classification should expose:
- timeframe,
- swing algorithm,
- confidence based on number/quality of swings,
- whether current structure is transitional.

### Tests
- Minimum swing count required.
- Noise sensitivity test.
- Same swing method used in scan and analyze.
- Sideways classification when neither sequence dominates.

---

## 3.2 Three directions and no-trade in sideways markets

**Source:** PDF pp.88–89, Book pp.51–52.

### Method
Markets move up, down, or sideways. Trend-following systems perform poorly in lateral markets.

### Apex routing
- Uptrend: trend pullback, breakout continuation.
- Downtrend: short trend pullback, downside breakout.
- Range: range mean reversion only.
- Sideways with weak boundaries: no trade.
- Compression: breakout watch, not early directional certainty.

### Rejection rule
Trend-following strategies prohibited when the measured market is sideways unless an expansion/breakout trigger is confirmed.

---

## 3.3 Three degrees of trend

**Source:** PDF pp.89–91, Book pp.52–54.

### Method
Major, intermediate, and near-term trends coexist and nest.

### Multi-timeframe implication
A near-term decline may be:
- a correction within an intermediate uptrend,
- which itself may sit within a major uptrend.

### Apex change
Do not collapse all timeframe signals into one average score. Represent:
- HTF regime,
- execution timeframe trend,
- trigger timeframe microstructure.

### Candidate logic
- HTF and execution TF aligned: primary setup.
- HTF conflict but local structure strong: secondary or reduced-risk.
- Strong HTF opposition: prohibit low-quality countertrend entries.
- Range on HTF + trend on LTF: short-horizon only, target bounded by HTF range.

### Tests
- Explicit conflict scenarios.
- No false “high confidence” when timeframes disagree.
- Holding horizon follows the setup timeframe.

---

## 3.4 Support and resistance are zones

**Source:** PDF pp.92–101, Book pp.55–64.

### Method
Support is an area where buying pressure can overcome selling pressure. Resistance is an area where selling pressure can overcome buying pressure.

### Importance factors
- amount of time spent,
- volume transacted,
- recency,
- number of prior tests,
- size of move away,
- significant penetration.

### Role reversal
- Broken resistance may become support.
- Broken support may become resistance.

### Long interpretation
- Buy/retest near confirmed support in an eligible bullish regime.
- Breakout above resistance may become a long only after decisive confirmation and acceptable entry geometry.

### Short interpretation
Mirror logic.

### Entry
- Aggressive: inside structural zone after evidence of rejection.
- Conservative: after close away from zone or breakout-and-retest.

### Stop
Beyond the structural invalidation, not exactly on a round number.

### No-use conditions
- weakly defined level,
- too many noisy crossings,
- insufficient separation between level and current price,
- poor reward to next obstacle,
- low liquidity,
- active candle only.

### Objective measurements
- zone width using ATR or swing dispersion,
- touch count,
- rejection count,
- volume at/near zone,
- recency decay,
- penetration depth,
- close acceptance beyond zone,
- reaction distance.

### Subjective elements
Exact zone boundaries and significance weighting.

### Apex change
Introduce a structural-level object:
- `zone_low`
- `zone_high`
- `role`
- `strength`
- `touches`
- `last_test`
- `volume_context`
- `broken`
- `retest_status`

### Tests
- Role reversal after meaningful close, not wick only.
- Old distant levels decay.
- Multiple exact touches are not required.
- Round-number stop clustering avoided.

---

## 3.5 Trendlines

**Source:** PDF pp.102–110, Book pp.65–73.

### Validity
- Two points draw a tentative line.
- A third test confirms validity.
- More tests, longer duration, and wider spacing increase significance.
- Trendlines should include the full price range, including highs/lows.
- Small penetrations require filters.

### Long interpretation
An uptrend line can provide:
- pullback entry reference,
- stop placement reference,
- warning on break,
- later resistance after role reversal.

### Short interpretation
Mirror logic.

### Confirmation and closed candles
A close beyond a trendline is more significant than intraday penetration.

### Filters discussed
- percentage penetration, commonly 3% in some contexts,
- one- or two-day time filters,
- Friday close for weekly confirmation.

The author also notes that one fixed filter does not fit every instrument.

### Apex interpretation
Use volatility-normalized filters rather than blindly hard-coding 3%.

### Entry
- Aggressive: reaction at line with local reversal evidence.
- Conservative: close confirming bounce, or break-and-retest after role reversal.

### Invalidation
- decisive close beyond the line,
- failure of retest,
- structural swing violation.

### Target
- next channel boundary,
- prior swing,
- measured implication after break.

### Failure patterns
- intraday whipsaw,
- overly steep unsustainable line,
- line fit to noise,
- line adjusted too frequently.

### Apex change
- tentative vs validated trendline states,
- line significance score,
- close-based break status,
- volatility-adjusted penetration,
- role reversal state.

### Tests
- wick-only break remains provisional.
- third touch increases confidence.
- steep line break is not automatically full trend reversal.
- adjusted trendline logic does not rewrite history.

---

## 3.6 Fan principle and multiple trendline breaks

**Source:** PDF pp.111–113, Book pp.74–76.

### Method
A trend may decelerate through a sequence of progressively flatter trendlines. Breaking the third line is presented as stronger reversal evidence.

### Apex use
Secondary reversal evidence, not standalone trade trigger.

### Objective measurements
- sequential line slopes,
- number of confirmed breaks,
- whether lines are drawn from a common origin,
- structure after each break.

### Automation label
- Reasonable operational interpretation.
- Requires empirical validation.

---

## 3.7 Trendline steepness and acceleration

**Source:** PDF pp.113–117, Book pp.76–80.

### Method
A roughly 45-degree slope is described as a useful visual benchmark, but chart scaling matters. Steeper trends are less sustainable; flatter trends may be weaker.

### Apex caution
Raw angle is not invariant across chart scaling. Do not use screen angle.

### Objective substitutes
- normalized slope in ATR per bar,
- log-return slope,
- rate of change,
- acceleration of swing slopes.

### Change
Replace any geometric screen-angle concept with scale-invariant metrics.

---

## 3.8 Channels

**Source:** PDF pp.117–122, Book pp.80–85.

### Method
A channel is formed by a trendline and a parallel return line.

### Uses
- entries near trendline,
- profit-taking near channel line,
- channel breakout as acceleration warning,
- failure to reach channel line as weakening warning,
- channel width as a measured objective after breakout.

### Long
- Buy near lower rising channel boundary with confirmation.
- Take profit or reduce near upper boundary.
- Break above upper boundary may signal acceleration.
- Failure to reach upper boundary warns of weakening.

### Short
Mirror logic.

### Target
After channel breakout, project channel width from breakout point.

### Apex change
Add:
- channel fit,
- boundary confidence,
- location percentile within channel,
- channel failure state,
- measured channel objective.

### Tests
- no entry when price is mid-channel with poor R:R.
- target clipped by nearer resistance.
- channel breakout requires close or setup-specific confirmation.

---

## 3.9 Percentage retracements

**Source:** PDF pp.122–124, Book pp.85–87.

### Method
Common retracements discussed:
- minimum near one-third,
- common near one-half,
- maximum around two-thirds,
- alternatives around 38%, 50%, 62%.

### Use
Potential pullback areas in an existing trend.

### Important limitation
These are reference zones, not standalone signals.

### Apex change
Treat retracement bands as confluence:
- 33–38%
- around 50%
- 62–66%

### Rejection
- no prior impulse,
- weak trend,
- no structural support/resistance,
- retracement exceeds invalidation,
- poor participation/confirmation.

### Tests
Validate bands by strategy and market; do not assume universal edge.

---

## 3.10 Speed resistance lines, Gann/Fibonacci fan lines, internal trendlines

**Source:** PDF pp.124–128, Book pp.87–91.

### Method
Alternative trend support/resistance methods:
- one-third/two-thirds speed lines,
- fan lines,
- internal trendlines through dense price action.

### Apex recommendation
Do not prioritize for first implementation. They are highly definition-sensitive and can duplicate clearer trendline/channel logic.

### Classification
- Objective geometry possible.
- Edge requires empirical validation.
- Internal trendline selection may be subjective.

---

## 3.11 Reversal days

**Source:** PDF pp.127–130, Book pp.90–93.

### Method
Top reversal day:
- new high,
- close below prior close,
- wider range and heavier volume increase significance.

Bottom reversal day:
- new low,
- close above prior close,
- wider range and heavier volume increase significance.

Weekly/monthly reversals carry greater significance.

### Entry
- Aggressive: near close after completed reversal bar in context.
- Conservative: break of reversal-bar high/low or follow-through close.

### Active-candle limitation
Cannot be confirmed before the candle closes because the close relation defines the pattern.

### Invalidation
Beyond reversal-bar extreme or structure level.

### Target
Not supplied by the pattern itself. Must come from structure.

### No-use
- no prior trend,
- tiny range,
- no volume/participation support,
- reversal bar inside noise,
- insufficient reward.

### Apex change
Pattern recognition must not auto-create a target.

---

## 3.12 Gaps

**Source:** PDF pp.131–134, Book pp.94–97.

### Types
1. Common gap
2. Breakaway gap
3. Runaway/measuring gap
4. Exhaustion gap
5. Island reversal

### Crypto limitation
Continuous 24/7 crypto markets do not exhibit session gaps in the same way as traditional markets. Exchange outages, illiquid books, or cross-venue jumps may create gap-like behavior, but direct transfer is limited.

### Apex use
- Mostly not applicable to continuous perpetual futures.
- Could be adapted to discontinuities or liquidity voids, but this would be an operational reinterpretation, not direct use.

### Must not do
Do not import stock/futures session-gap rules unchanged into 24/7 crypto.

---

# 4. Reversal setups

## 4.1 General requirements for major reversals

**Source:** PDF pp.136–140, Book pp.99–103.

### Preconditions
1. Prior trend must exist.
2. First warning is often a major trendline break.
3. Larger pattern implies larger subsequent move.
4. Top patterns tend to be shorter and more volatile than bottoms.
5. Bottoms tend to take longer and have smaller price ranges.
6. Volume is more important in upside completion.

### Pattern recognition vs approval
A shape alone is not enough. Approval requires prior trend, completion, risk geometry, and context.

### Apex change
Every reversal strategy should include:
- `prior_trend_required`
- `minimum_trend_age`
- `completion_trigger`
- `volume_requirement`
- `failure_condition`
- `target_method`

### Tests
Reject reversal pattern detected in a range without prior trend.

---

## 4.2 Head-and-shoulders top

**Source:** PDF pp.140–147, Book pp.103–110.

### Regime
Mature uptrend or topping transition.

### Structure
- left shoulder,
- higher head,
- right shoulder lower than head,
- neckline through reaction lows,
- weakening volume into later peaks,
- neckline break completes pattern.

### Confirmation
- Decisive close below neckline.
- Volume expansion on downside break is helpful but not essential at tops.
- Return move to neckline may occur; lower volume on retest is preferred.

### Long/short
- Short setup only after completion.
- Before completion it is a reversal candidate, not an approved short.
- Longs should be downgraded during pattern maturation but not automatically exited solely on shape.

### Entry
- Aggressive: short on confirmed close below neckline.
- Conservative: short failed retest of neckline from below.

### Active-candle limitation
Intrabar move below neckline is provisional.

### Invalidation
- close back above neckline after completed break,
- break above right shoulder,
- failure pattern discussed at PDF p.150 / Book p.113.

### Stop
- aggressive: above retest swing/high or neckline plus buffer,
- conservative: above right shoulder,
- exact choice depends on entry and volatility.

### Target
Measure vertical height from head to neckline and project downward from breakout.

### Target adjustment
Modify for:
- nearby support,
- retracement levels,
- prior lows,
- percentage retracement of prior advance,
- market context.

The measured objective is a minimum objective, not a guaranteed final target.

### Partials/trailing
Book does not provide a complete formal partial system here. Operationally:
- TP1 at nearest support,
- TP2 at measured objective,
- runner only if trend structure continues.

This is a reasonable operational interpretation, not directly specified as a full scale-out method.

### Expiry
Not explicitly quantified. Candidate expires if:
- neckline break fails,
- price reclaims pattern,
- too much time passes without follow-through relative to pattern timeframe.

### Failure patterns
- no prior uptrend,
- shoulders/head poorly defined,
- neckline not broken,
- right shoulder exceeds head,
- bullish reclaim after break,
- insufficient room to target.

### Data
OHLCV, swing points, trend state, ATR, support/resistance.

### Apex change
Create candidate/completed/failed states and avoid `READY_NOW` before neckline close.

### Tests
- wick below neckline does not confirm.
- measured target uses neckline at breakout point.
- retest entry not forced.
- target clipped or reprioritized at nearer support.
- failed reclaim invalidates short.

---

## 4.3 Inverse head-and-shoulders

**Source:** PDF pp.147–149, Book pp.110–112.

### Regime
Mature downtrend or bottoming transition.

### Structure
Mirror of top, but volume behavior differs.

### Confirmation
- Decisive neckline break.
- Strong volume expansion is more important at bottoms.
- Retest may occur and should ideally be lighter volume.

### Entry
- Aggressive: confirmed close above neckline with strong participation.
- Conservative: successful retest of neckline as support.

### Invalidation
- close back below neckline,
- loss of right-shoulder low,
- failure to expand on breakout may reduce confidence.

### Stop
Below retest low or right shoulder, with volatility buffer.

### Target
Head-to-neckline height projected upward.

### Key asymmetry
Bottoms generally require clearer evidence of buying pressure than tops require of selling pressure.

### Apex change
Do not use symmetric volume rules for bullish and bearish reversal patterns.

---

## 4.4 Complex head-and-shoulders and failed patterns

**Source:** PDF p.150, Book p.113.

### Complex pattern
May contain multiple shoulders or heads. The core principles remain similar, but geometry is more ambiguous.

### Automation
- Basic multi-peak detection is possible.
- Safe automatic classification is difficult.
- Prefer low confidence or manual-review label.

### Failed pattern
A completed head-and-shoulders pattern that later recrosses the neckline is identified as failed.

### Apex use
Explicit `PATTERN_FAILED` state. A failure may become a reversal in the opposite direction, but the uploaded PDF cuts off before the full discussion. Apex must not infer a complete opposite-side strategy from this truncated passage alone.

---

# 5. Continuation setups

The uploaded PDF does **not** reach the continuation-pattern chapter. The table of contents lists it, but the scan ends at Book p.113.

Therefore, the following cannot be derived from this PDF segment:
- triangles,
- flags,
- pennants,
- wedges,
- rectangles,
- measured moves,
- continuation head-and-shoulders,
- detailed continuation confirmation/divergence rules.

Apex should not claim book support for those methods based on this upload.

However, the covered material supports continuation concepts through:
- trend persistence,
- trendline pullbacks,
- channels,
- percentage retracements,
- support/resistance retests,
- Dow Theory continuation assumption.

---

# 6. Breakouts and failed breakouts

## 6.1 Decisive break principle

**Sources:** PDF pp.65–68, 94–100, 107–110, 143–150.

A breakout should be evaluated by:
- closing basis,
- penetration depth,
- time beyond the level,
- volume/participation,
- retest behavior,
- structural context.

### Aggressive entry
On confirmed close beyond the level.

### Conservative entry
On retest that holds the new role.

### Failed breakout
- price closes back through the level,
- retest fails,
- continuation does not develop,
- structure invalidates.

### Apex fields
- `breakout_level`
- `breakout_close_distance`
- `penetration_atr`
- `bars_accepted_beyond`
- `retest_status`
- `volume_ratio`
- `failure_status`

### Output wording
- “Testing resistance”
- “Intrabar break; unconfirmed”
- “Closed above resistance”
- “Retest pending”
- “Retest held”
- “Breakout failed”

---

# 7. Support, resistance, and polarity

## Core rule
A broken level can reverse role, but only after meaningful penetration. The source notes subjectivity and mentions 3% as one traditional criterion for major levels, while cautioning that fixed thresholds may not fit all markets.

### Apex operational rule candidate
- Use close beyond zone plus ATR-normalized penetration.
- Require at least one acceptance bar or retest depending on strategy.
- Score zone strength separately from breakout quality.

### Classification
- Close beyond prior level: directly supported.
- ATR-normalized replacement for fixed 3%: reasonable operational interpretation.
- Exact thresholds: empirical validation.

---

# 8. Candlestick interpretation

The uploaded PDF includes only introductory candlestick material in Chapter 3:
- candle body shows open-close relation,
- shadows show full range,
- white/positive and black/negative body convention,
- candles provide added visual information but use the same OHLC data.

**Source:** PDF pp.74–76, Book pp.37–39.

The detailed Japanese candlestick chapter is not included in the uploaded scan.

### Apex implication
Do not attribute detailed candlestick pattern rules to this PDF. The only directly supported implementation is accurate candle construction and cautious use of OHLC relationships.

---

# 9. Volume and participation

## 9.1 General principle

**Sources:** PDF pp.64, 78–81, 137–145.

Volume is secondary but important. It should generally expand in the direction of the prevailing trend.

### Trend confirmation
- Uptrend: stronger volume on advances, lighter on pullbacks.
- Downtrend: stronger volume on declines, lighter on rallies.

### Reversal asymmetry
- Top: volume confirmation useful but not always essential.
- Bottom: volume expansion is more important.

### Objective measurements
- relative volume,
- volume percentile,
- volume trend,
- impulse vs pullback volume ratio,
- breakout volume ratio,
- retest volume contraction,
- price-volume divergence.

### Required data
Exchange volume and, for perpetuals, preferably:
- quote volume,
- taker buy/sell volume,
- open interest,
- liquidation data.

Only basic volume/open-interest principles are directly from the source.

### Apex change
Volume should be:
- a confirmation multiplier,
- a rejection condition for some bullish breakouts,
- not a universal trigger.

---

# 10. Momentum and oscillators

The table of contents lists oscillators, RSI, stochastics, MACD, and related material, but the uploaded PDF does not reach those chapters.

### Consequence
This PDF segment cannot justify:
- RSI thresholds,
- MACD crossover rules,
- overbought/oversold entries,
- divergence rules,
- oscillator-derived targets.

Any Apex oscillator logic must be reviewed using another source or empirical evidence.

---

# 11. Moving averages and trend tools

The table of contents lists moving averages and Bollinger Bands, but those chapters are absent from the uploaded pages.

### Consequence
No detailed moving-average entry, crossover, band target, or volatility rule can be derived from this PDF segment.

---

# 12. Entry methodology

## 12.1 General entry framework supported by the PDF

A valid entry should be downstream of:

1. market regime,
2. prior trend requirement,
3. structure detection,
4. pattern completion,
5. close/confirmation rule,
6. acceptable position relative to support/resistance,
7. stop placement,
8. target and reward geometry.

### Aggressive entry classes
- confirmed breakout close,
- confirmed bounce at structural support/resistance,
- trendline reaction after validation,
- completed reversal bar in context.

### Conservative entry classes
- breakout retest,
- polarity retest,
- follow-through close,
- break of reversal-bar extreme.

### Active-candle restrictions
Use active candle only for:
- monitoring,
- approaching-entry state,
- provisional trigger.

Do not use it as final confirmation when the setup definition depends on closing price.

### Apex state model
- `WATCH`
- `APPROACHING_ENTRY`
- `TRIGGER_PROVISIONAL`
- `CONFIRMATION_PENDING_CLOSE`
- `READY_NOW`
- `RETEST_PENDING`
- `MISSED_ENTRY`
- `INVALIDATED`
- `NO_TRADE`

`READY_NOW` requires a completed trigger and valid geometry.

---

# 13. Stop-loss methodology

## Directly supported principles

### 13.1 Stops belong beyond structural invalidation
Support/resistance and trendline discussions imply stops beyond the level that disproves the setup.

### 13.2 Avoid obvious round-number clustering
**Source:** PDF pp.101–102, Book pp.64–65.

The author warns against placing stops exactly at obvious round numbers and suggests placing them beyond such levels.

### 13.3 Leverage increases timing and stop importance
**Source:** PDF pp.49–51, Book pp.12–14.

### Apex stop hierarchy
1. pattern invalidation,
2. swing invalidation,
3. zone invalidation,
4. volatility buffer,
5. liquidation safety check.

### Prohibited stop methods
- arbitrary fixed percent unrelated to structure,
- stop inside the entry zone,
- stop selected only to manufacture desired R:R,
- stop beyond liquidation,
- stop exactly at a crowded round number without buffer.

### Tests
- stop must be on invalid side of structure.
- liquidation buffer must remain positive.
- widening stop reduces size, not increases account risk.
- same setup produces same structural stop in scan and analyze.

---

# 14. Take-profit methodology

## 14.1 Structural target hierarchy

### Book-supported target methods
- prior support/resistance,
- trendline measurement,
- channel width,
- head-and-shoulders height,
- measuring gap where applicable,
- percentage retracement zones.

### Apex implementation
Targets should be candidate levels with labels:
- `structural_obstacle`
- `pattern_minimum_objective`
- `channel_objective`
- `htf_level`
- `runner_extension`

### Important rule
Pattern objective is a minimum estimate, not certainty.

### Target rejection
Reject trade if:
- nearest obstacle destroys minimum R:R,
- target depends on unsupported fixed percentage,
- target lies beyond unrealistic liquidity/volatility assumptions,
- target is derived from leverage return rather than price structure.

---

# 15. Trade-management methodology

The covered pages provide partial management guidance:
- use channel boundaries for profit-taking,
- use support/resistance as target/adjustment levels,
- retests can offer second entries,
- failed patterns require exit/reclassification,
- rising/falling channels can warn of acceleration or weakness.

### Operational trade management
1. Reduce at first meaningful obstacle.
2. Move stop only after new structure forms.
3. Trail behind confirmed swing structure or trendline.
4. Exit on pattern failure or decisive structural reclaim.
5. Preserve a runner only when continuation structure remains intact.

This full lifecycle is partly an operational interpretation and requires backtesting.

---

# 16. Setup expiry and time estimation

The source does not provide universal bar-count expiry rules in the covered pages.

### Supported principles
- Timeframe determines significance.
- Weekly/monthly signals carry more weight.
- Pattern size relates to potential movement.
- Short, intermediate, and major trends have different horizons.
- A setup that does not follow through may weaken or fail.

### Apex candidate expiry model
- Expiry measured in bars of the trigger timeframe.
- Pattern duration informs allowed follow-through window.
- Volatility and distance to target inform expected hold.
- Retest setups expire if price moves too far without retest.
- Breakout setups expire on acceptance back inside the prior range.
- Reversal setups expire if prior trend resumes.

### Classification
Reasonable operational interpretation; requires empirical validation.

---

# 17. Risk and loss avoidance

## Book-supported principles
- Timing errors are amplified by leverage.
- Market selection matters.
- Trend-following tools should not be forced in ranges.
- A pattern without prior trend is suspect.
- A warning is not the same as a completed reversal.
- Stops should be structurally placed.
- Fixed criteria may not suit every market.

### Apex no-trade filters
- insufficient liquidity,
- wide spread/slippage,
- conflicting higher timeframe without a defined countertrend strategy,
- poor R:R to first obstacle,
- unconfirmed active-candle trigger,
- no prior trend for reversal pattern,
- range regime for trend strategy,
- overextended chase,
- invalid stop geometry,
- liquidation too close,
- insufficient data.

---

# 18. Multi-timeframe analysis

## Supported framework
- Major trend: dominant context.
- Intermediate trend: tradable swing.
- Near-term trend: execution timing.

### Apex model
- Context timeframe determines regime.
- Setup timeframe determines pattern.
- Trigger timeframe determines entry.
- Risk timeframe determines structural stop.
- Target timeframe determines horizon.

### Conflict handling
- Aligned: enabled.
- Mild conflict: secondary/reduced confidence.
- Strong conflict: prohibit unless explicitly countertrend.
- Higher timeframe range: local trades target range boundaries.
- Higher timeframe breakout: avoid fading without failure confirmation.

---

# 19. Market and intermarket context

The uploaded pages contain only introductory references to broad economic forecasting and market adaptability. The detailed intermarket chapter is absent.

### What can be used
- market selection and relative opportunity matter,
- external markets can provide context,
- but no detailed deterministic intermarket rules are available from this scan.

### Apex implication
Do not claim book support for BTC dominance, DXY, equities, rates, or sector-rotation rules from this PDF segment.

---

# 20. Trade selection and ranking

## Ranking dimensions supported by the text

1. Regime fit
2. Prior trend quality
3. Pattern completeness
4. Confirmation quality
5. Level/trendline significance
6. Volume participation
7. Multi-timeframe alignment
8. Entry location
9. Stop validity
10. Target room
11. Failure risk
12. Liquidity and execution quality

### Confidence semantics
Confidence should describe evidence quality, not win probability unless calibrated.

Recommended labels:
- `LOW_EVIDENCE`
- `MODERATE_EVIDENCE`
- `STRONG_EVIDENCE`
- `PROVISIONAL`
- `CONFIRMED`
- `CONFLICTED`

Avoid presenting an uncalibrated numeric score as a probability.

---

# 21. No-trade conditions

Apex should return `NO_TRADE` when:

- no eligible strategy fits the regime,
- structure is ambiguous,
- signal exists only on active candle,
- breakout lacks acceptance,
- no prior trend exists for reversal,
- range midpoint offers poor geometry,
- entry is too far from invalidation,
- target is blocked by nearby structure,
- volume/data quality is inadequate,
- higher timeframe conflict is unresolved,
- liquidity is too low,
- stop would be inside noise,
- required data is missing,
- projected move is not meaningful after fees/slippage.

---

# 22. Output wording and confidence semantics

## Replace misleading wording

### Instead of
`READY_NOW — confidence 42`

### Prefer
`Confirmed short setup; entry valid only below the neckline retest zone. Evidence: completed neckline break, mature prior uptrend, weakening rally volume. Main risk: nearby support limits reward.`

### State definitions

- **WATCH:** Structure exists but price is not near a trigger.
- **APPROACHING_ENTRY:** Price is entering a relevant structural zone.
- **TRIGGER_PROVISIONAL:** Intrabar condition is present but close is required.
- **CONFIRMATION_PENDING_CLOSE:** Exact closing condition not complete.
- **READY_NOW:** Trigger completed; entry, stop, target, and risk constraints valid.
- **RETEST_PENDING:** Breakout confirmed, but strategy requires or prefers retest.
- **MISSED_ENTRY:** Price exceeded maximum chase or invalidated reward geometry.
- **INVALIDATED:** Structural condition failed.
- **NO_TRADE:** No eligible setup.

### Confidence
Report:
- evidence strength,
- data completeness,
- regime alignment,
- confirmation status,
- risk quality.

Do not equate confidence to expected profit.

---

# 23. Backtesting implications

## Required design

1. Chronological evaluation.
2. Closed-candle signals use only completed bars.
3. Active-candle states tracked separately.
4. No future swing-point leakage.
5. Pattern completion timestamp recorded.
6. Entry assumptions explicit.
7. Retest logic modeled without hindsight.
8. Fees, slippage, funding, and liquidation modeled.
9. Target hierarchy applied in order.
10. Failed breakouts and invalidations recorded.
11. Results segmented by regime and timeframe.
12. Numerical confidence calibrated against outcomes.

## Metrics
- expectancy,
- profit factor,
- max drawdown,
- hit rate by target,
- stop-out rate,
- breakout failure rate,
- missed-entry rate,
- average adverse excursion,
- average favorable excursion,
- time to target,
- time to invalidation,
- performance by evidence class,
- performance by HTF alignment,
- liquidation rate.

---

# 24. Strategy catalogue

| Setup | Regime | Direction | Preconditions | Trigger | Entry | Stop | Targets | Expiry | Rejection rules | Required data |
|---|---|---|---|---|---|---|---|---|---|---|
| Trend pullback to support | Uptrend | Long | Higher highs/lows; valid support | Rejection/close from support | Zone or confirmed bounce | Below zone/swing | Prior high, channel top | Structure-dependent | Range, weak support, poor R:R | OHLCV, swings, ATR |
| Trend rally to resistance | Downtrend | Short | Lower highs/lows; valid resistance | Rejection/close from resistance | Zone or confirmed rejection | Above zone/swing | Prior low, channel bottom | Structure-dependent | Range, weak resistance | OHLCV, swings, ATR |
| Trendline bounce | Trend | Both | Validated line, at least third test preferred | Close away from line | Aggressive at confirmed reaction; conservative follow-through | Beyond line/swing | Channel line, prior swing | Until line breaks or setup drifts | Tentative/noisy line | OHLCV, pivots |
| Trendline break | Mature trend | Opposite / warning | Significant validated line | Close beyond line plus filter | On close or retest | Beyond failed-break structure | Prior level / measured implication | Until reclaim | Wick-only break, no room | OHLCV, ATR |
| Support-resistance polarity retest | Breakout | Both | Meaningful break and role reversal | Retest holds | At zone after confirmation | Beyond zone | Next structure | Retest window | Break not accepted, immediate reclaim | OHLCV, volume |
| Channel boundary trade | Stable channel | Both | Parallel boundaries, repeated containment | Reaction at boundary | Near boundary | Outside channel | Opposite boundary | Until channel changes | Mid-channel, weak fit | OHLCV |
| Channel breakout | Expansion | Both | Established channel | Close outside channel | On close/retest | Back inside channel | Channel-width projection | Until re-entry | Wick-only break | OHLCV, ATR |
| Reversal day | Exhaustion | Both | Prior trend | New extreme and close reversal | Close or next-bar break | Beyond reversal extreme | Structural only | Short | No prior trend, tiny range | OHLCV, volume |
| Head-and-shoulders top | Mature uptrend | Short | Prior uptrend, complete geometry | Decisive close below neckline | Break or failed retest | Above retest/right shoulder | Pattern height, support | Until reclaim | No prior trend, no neckline break | OHLCV, swings |
| Inverse head-and-shoulders | Mature downtrend | Long | Prior downtrend, complete geometry | Decisive close above neckline, volume important | Break or successful retest | Below retest/right shoulder | Pattern height, resistance | Until reclaim | Weak participation, no completion | OHLCV, swings, volume |
| Failed breakout | Breakout failure | Opposite | Prior break beyond key level | Close back inside + failure evidence | Reclaim/retest | Beyond failed-break extreme | Opposite range boundary | Short/medium | No clear level, low liquidity | OHLCV, volume |
| Percentage retracement pullback | Trend | Both | Clear impulse | Reaction in 33–66% band with structure | Confirmed reaction | Beyond structural invalidation | Prior extreme / extension | Until retracement fails | No impulse, trend weak | OHLCV |
| Breakaway/runaway/exhaustion gap | Session market | Both | Session discontinuity | Gap classification | Context-specific | Gap invalidation | Structural/measured | Context-specific | 24/7 crypto without true gap | Session OHLCV |

---

# 25. Regime-to-strategy matrix

Legend: **E** enabled, **S** secondary, **P** prohibited.

| Strategy | Strong uptrend | Weak uptrend | Strong downtrend | Weak downtrend | Range | Compression | Expansion | Breakout | Failed breakout | Exhaustion | High vol | Low liquidity | Conflicting HTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Long trend pullback | E | E | P | P | P | S | S | S | P | S | S | P | S |
| Short trend pullback | P | P | E | E | P | S | S | S | P | S | S | P | S |
| Range mean reversion | P | S | P | S | E | S | P | P | S | S | S | P | S |
| Breakout continuation | S | S | S | S | P | S | E | E | P | P | S | P | S |
| Breakout retest | E | S | E | S | P | S | E | E | P | P | E | P | S |
| Failed breakout reversal | P | S | P | S | S | S | S | P | E | E | E | P | S |
| Head-and-shoulders top | P | S | P | P | P | S | S | S | E | E | S | P | S |
| Inverse head-and-shoulders | P | P | P | S | P | S | S | S | E | E | S | P | S |
| Trendline bounce | E | S | E | S | P | S | S | S | P | S | S | P | S |
| Channel boundary | S | E | S | E | S | S | P | P | S | S | S | P | S |
| Reversal day | S | S | S | S | S | P | S | S | S | E | E | P | S |

**Notes**
- “Conflicting HTF” is secondary unless the strategy is explicitly countertrend and tested.
- High volatility does not automatically prohibit trading; it requires wider structural stops and smaller size.
- Low liquidity is broadly prohibited because the book assumes executable market prices and does not address crypto microstructure hazards.

---

# 26. Apex gap analysis

## 26.1 What Apex already does correctly, based on supplied project context

- Separates scanner categories for normal markets and gainers.
- Has explicit entry-state concepts.
- Includes risk, leverage, liquidation, and margin planning.
- Uses deterministic, testable architecture.
- Supports multiple timeframes.
- Intends shared behavior between `scan` and `analyze`.
- Does not force every situation into a trade.

## 26.2 Incomplete

- Regime and setup eligibility are not yet sufficiently separated from entry state.
- Closed-candle requirements need setup-specific implementation.
- Structural zones need width and significance, not single prices.
- Target logic needs pattern/structure-derived objectives.
- Setup expiry needs timeframe-derived rules.
- Failed breakout/pattern states need first-class handling.
- Confidence needs evidence semantics and calibration.
- Multi-timeframe conflict should be explicit, not averaged away.

## 26.3 Incorrectly implemented or methodologically suspect

Based on the behavior described by the user:

- `READY_NOW` may be emitted too early.
- Low numeric confidence may coexist with an actionable label, creating contradiction.
- Single-price entry zones conflict with the source’s zone-based support/resistance concept.
- Active-candle-only signals may be treated as confirmed.
- Weak reward-to-risk may still produce actionable output.
- Targets may be too fixed or detached from structure.
- Short execution windows may be forced regardless of setup timeframe.

## 26.4 Misleading mainly in wording

- `READY_NOW` without stating close status.
- “Confidence” shown as a number without calibration.
- “Entry zone” when it is a single value.
- “Target” when it is only a projected objective.
- “Trend reversal” when only a warning exists.

## 26.5 Should be removed

- Universal fixed 10% target logic.
- Automatic target generation from candle pattern alone.
- Any rule equating market direction with immediate entry.
- Any implicit assumption that leverage return equals projected market move.
- Any fixed short expiry applied to all setups.

## 26.6 Should be added

- setup-specific close requirements,
- structural zones,
- breakout acceptance and retest states,
- pattern candidate/completed/failed states,
- target provenance,
- stop provenance,
- regime eligibility matrix,
- multi-timeframe conflict report,
- evidence-based confidence labels,
- explicit no-trade reasons,
- setup duration and expiry model.

## 26.7 Cannot be derived from this PDF

- RSI/MACD/stochastic rules,
- detailed moving-average strategies,
- full candlestick pattern library,
- continuation-pattern catalogue,
- detailed money-management formulas,
- modern crypto funding/OI/liquidation logic,
- intermarket crypto context,
- statistical profitability.

---

# 27. Deterministic rule candidates

| Candidate rule | Classification | Source |
|---|---|---|
| Uptrend requires higher highs and higher lows | Directly supported | PDF pp.86–88 |
| Downtrend requires lower highs and lower lows | Directly supported | PDF pp.86–88 |
| Sideways regime disables trend-following entries | Directly supported | PDF pp.88–89 |
| Reversal pattern requires prior trend | Directly supported | PDF pp.138–140 |
| Trendline needs two points to draw, third test to validate | Directly supported | PDF pp.102–104 |
| Close beyond trendline is stronger than intraday penetration | Directly supported | PDF p.108 |
| Use ATR-normalized penetration instead of fixed 3% | Reasonable operational interpretation | PDF pp.108, 100–101 |
| Broken resistance may become support | Directly supported | PDF pp.94–100 |
| Role reversal requires meaningful penetration | Directly supported | PDF pp.98–100 |
| Support/resistance strength increases with time, volume, recency | Directly supported | PDF pp.96–101 |
| Reversal day requires completed candle | Directly supported by definition | PDF pp.128–130 |
| H&S top completes only after neckline break | Directly supported | PDF pp.143–144 |
| Inverse H&S breakout volume should be stronger | Directly supported | PDF pp.147–149 |
| H&S target = head-to-neckline distance projected from break | Directly supported | PDF pp.145–147 |
| Pattern objective should be adjusted for nearby structure | Directly supported | PDF pp.146–147 |
| Channel breakout target = channel width | Directly supported | PDF p.122 |
| Retracement bands 33–38%, 50%, 62–66% are confluence only | Reasonable operational interpretation | PDF pp.122–124 |
| Expire retest setup after N trigger bars | Requires empirical validation | Not quantified |
| Confidence score as calibrated win probability | Requires empirical validation | Not provided |
| Complex H&S fully automated | Too subjective to automate safely | PDF p.150 |
| Internal trendline auto-selection | Too subjective to automate safely | PDF pp.127–128 |
| Screen-angle 45-degree trendline test | Too subjective / scale-dependent | PDF pp.113–114 |
| Gap strategies in 24/7 crypto | Requires adaptation and validation | PDF pp.131–134 |

---

# 28. Evidence ledger — complete PDF coverage

## Front matter and contents
- **PDF pp.1–7:** Blank/title/copyright/dedication pages. Covered; no trading rules.
- **PDF pp.8–25:** Table of contents. Covered. Important because it proves many listed chapters are absent from the scan.
- **PDF pp.26–29:** Author and contributor biographies. Covered; no implementation rules.
- **PDF pp.30–32:** Introduction. Covered. Notes revision scope and breadth.
- **PDF pp.33–35:** Blank/acknowledgments. Covered.
- **PDF pp.36–37:** Section title/blank. Covered.

## Chapter 1 — Philosophy of Technical Analysis
- **PDF pp.38–39 / Book pp.1–2:** Definition; market action includes price, volume, open interest.
- **PDF pp.39–40 / Book pp.2–3:** Market action discounts information.
- **PDF pp.40–41 / Book pp.3–4:** Prices move in trends.
- **PDF pp.41–42 / Book pp.4–5:** History repeats; psychology.
- **PDF pp.42–43 / Book pp.5–6:** Technical vs fundamental forecasting.
- **PDF pp.43–44 / Book pp.6–7:** Analysis versus timing.
- **PDF pp.44–45 / Book pp.7–8:** Flexibility and market selection.
- **PDF pp.45–47 / Book pp.8–10:** Different markets and time dimensions.
- **PDF pp.47–48 / Book pp.10–11:** Economic forecasting; technician/chartist.
- **PDF pp.48–50 / Book pp.11–13:** Quantitative systems; futures differences.
- **PDF pp.50–52 / Book pp.13–15:** Leverage, timing, indicators.
- **PDF pp.52–55 / Book pp.15–18:** Criticisms, subjectivity, self-fulfilling prophecy.
- **PDF pp.55–58 / Book pp.18–21:** Past data, random walk, efficient markets.
- **PDF pp.58–59 / Book pp.21–22:** Universal principles and chapter close.

## Chapter 2 — Dow Theory
- **PDF pp.60–61 / Book pp.23–24:** Introduction/history.
- **PDF pp.61–62 / Book pp.24–25:** Averages discount everything.
- **PDF pp.62–63 / Book pp.25–26:** Three trends.
- **PDF pp.63–64 / Book pp.26–27:** Three phases; averages confirm.
- **PDF pp.64–65 / Book pp.27–28:** Volume confirms; trend persists.
- **PDF pp.65–67 / Book pp.28–30:** Confirmation examples; failure swings.
- **PDF pp.67–68 / Book pp.30–31:** Closing prices and line concepts.
- **PDF pp.68–70 / Book pp.31–33:** Criticism, futures application, conclusion.

## Chapter 3 — Chart Construction
- **PDF pp.71–72:** Blank and chapter title.
- **PDF pp.72–76 / Book pp.35–39:** Chart types, bars, line charts, point-and-figure, candlestick basics.
- **PDF pp.76–78 / Book pp.39–41:** Arithmetic vs logarithmic scales; bar construction.
- **PDF pp.78–81 / Book pp.41–44:** Volume and open interest.
- **PDF pp.81–83 / Book pp.44–46:** Reporting delays; weekly/monthly charts.
- **PDF p.84 / Book p.47:** Conclusion and chart-reading subjectivity.
- **PDF p.85:** Blank.

## Chapter 4 — Basic Concepts of Trend
- **PDF pp.86–88 / Book pp.49–51:** Trend definition and three directions.
- **PDF pp.88–91 / Book pp.51–54:** Three classifications/degrees.
- **PDF pp.92–101 / Book pp.55–64:** Support/resistance, psychology, role reversal, significance, round numbers.
- **PDF pp.102–110 / Book pp.65–73:** Trendlines, validation, breaks, filters, role reversal.
- **PDF pp.111–113 / Book pp.74–76:** Fan principle, importance of three.
- **PDF pp.113–117 / Book pp.76–80:** Steepness and trendline adjustment.
- **PDF pp.117–122 / Book pp.80–85:** Channels and measuring implication.
- **PDF pp.122–124 / Book pp.85–87:** Percentage retracements.
- **PDF pp.124–127 / Book pp.87–90:** Speed lines, Gann/Fibonacci fans, internal trendlines.
- **PDF pp.127–130 / Book pp.90–93:** Reversal days.
- **PDF pp.131–134 / Book pp.94–97:** Gaps and island reversal.
- **PDF p.135 / Book p.98:** Conclusion.

## Chapter 5 — Major Reversal Patterns
- **PDF pp.136–140 / Book pp.99–103:** Pattern categories and general reversal principles.
- **PDF pp.140–144 / Book pp.103–107:** Head-and-shoulders top structure, neckline, retest.
- **PDF pp.145–147 / Book pp.108–110:** Volume and price objective.
- **PDF pp.147–149 / Book pp.110–112:** Inverse head-and-shoulders.
- **PDF p.150 / Book p.113:** Complex patterns, tactics, failed pattern introduction. Page ends mid-discussion.

## Coverage conclusion
All 150 PDF pages were reviewed. No pages were skipped. Several pages are intentionally blank or front matter. The scan is readable overall, but it is incomplete relative to the full book and ends mid-section.

---

# 29. Final phased implementation plan

## Phase 1 — Shared market-context layer

**Goal:** One analysis core for `apex scan` and `apex analyze SYMBOL`.

Add/standardize:
- swing structure,
- regime,
- trend degree,
- support/resistance zones,
- trendlines/channels,
- volatility,
- volume participation,
- data quality,
- HTF conflict.

Preserve existing architecture. Symbol selection remains outside the shared core.

### Validation
- identical symbol/timeframe inputs produce identical context in scan and analyze.
- no future-data leakage in swing detection.

---

## Phase 2 — Setup eligibility

Create explicit precondition evaluators:
- prior trend,
- regime allowed,
- structure mature,
- required data present,
- liquidity acceptable,
- projected room available.

Output:
- eligible,
- secondary,
- prohibited,
- with reasons.

---

## Phase 3 — Strategy routing

Route only eligible strategies:
- trend pullback,
- trendline/channel trade,
- breakout continuation,
- breakout retest,
- failed breakout,
- reversal day,
- H&S top/bottom.

Do not yet add absent-book strategies as “Murphy-derived.”

---

## Phase 4 — Entry logic

For every strategy define:
- setup candidate,
- trigger provisional,
- close-confirmed trigger,
- aggressive entry,
- conservative entry,
- maximum chase,
- missed entry,
- invalidation.

Active candles may create monitoring states, not false confirmation.

---

## Phase 5 — Stop logic

Compute stop from:
1. structural invalidation,
2. volatility buffer,
3. execution constraints,
4. liquidation buffer.

Position size must adapt to stop distance.

Record stop provenance in output.

---

## Phase 6 — Target logic

Build target candidates from:
- nearest support/resistance,
- prior swing,
- channel width,
- H&S height,
- trendline measurement,
- HTF level.

Rank targets and reject trades with insufficient net reward.

No fixed 10% requirement.

---

## Phase 7 — Timing and expiry

Estimate:
- setup timeframe,
- expected movement horizon,
- retest window,
- expiry bars,
- time-stop conditions.

Derive from pattern duration, volatility, and timeframe. Validate empirically.

---

## Phase 8 — Scoring and confidence

Separate:
- pattern quality,
- regime fit,
- confirmation quality,
- volume support,
- MTF alignment,
- risk quality,
- data completeness.

Do not call the resulting number a win probability until calibrated.

---

## Phase 9 — Output wording

Adopt evidence-oriented language:
- provisional vs confirmed,
- candidate vs completed,
- expected objective vs guaranteed target,
- bias vs entry,
- projected move vs leveraged return.

Each result should include:
- why eligible,
- why now/not now,
- what confirms,
- what invalidates,
- where stop comes from,
- where targets come from,
- estimated horizon,
- no-trade reason if rejected.

---

## Phase 10 — Backtesting and validation

Implement chronological tests for:
- close-only confirmation,
- active-candle false positives,
- breakout acceptance,
- retest success/failure,
- pattern failure,
- target hierarchy,
- regime routing,
- HTF conflict,
- expiry,
- fees/slippage/funding/liquidation.

Calibrate thresholds by market, timeframe, and strategy. Preserve walk-forward and out-of-sample evaluation.

---

# 30. Final coverage statement

**Fully covered in the uploaded PDF:**
- all 150 scanned pages,
- front matter and table of contents,
- Chapter 1,
- Chapter 2,
- Chapter 3,
- Chapter 4,
- Chapter 5 through printed page 113.

**Not present in the uploaded PDF:**
- the remainder of Chapter 5,
- continuation patterns,
- full volume/open-interest chapter,
- moving averages,
- oscillators,
- point-and-figure,
- detailed candlesticks,
- Elliott Wave,
- cycles,
- trading systems,
- money management,
- intermarket analysis,
- market indicators,
- checklist,
- advanced indicators,
- market profile,
- system-building appendix material.

**Unreadable or ambiguous pages:**
- No page was wholly unreadable.
- Some fine print and chart labels are small, but the principal rule and visual meaning were readable.
- The final page is incomplete because the PDF itself ends mid-discussion.
- Some traditional thresholds, especially trendline penetration and time filters, are presented as alternatives rather than universal rules; this ambiguity is preserved and should be resolved through instrument-specific testing.
