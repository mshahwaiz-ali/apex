# Apex Trading Project - Japanese Candlestick Methodology Research

**Source:** Steve Nison, *Japanese Candlestick Charting Techniques*  
**Uploaded PDF:** 329 content pages reported by the document viewer; the local file contains 330 PDF objects including a trailing/blank object.  
**Repository status:** No repository files were changed. No code was written.

---

## 1. Research scope and interpretation policy

This report converts the complete uploaded book into implementation-oriented research for Apex. It is not a generic candlestick summary and it does not treat historical pattern descriptions as proven statistical edges.

### Evidence labels used throughout

- **Directly supported:** The rule is explicitly stated or repeatedly demonstrated in the book.
- **Reasonable operational interpretation:** A deterministic translation consistent with the book, but not stated as an exact formula.
- **Requires empirical validation:** A threshold, scoring weight, expiry window, or crypto adaptation that must be tested.
- **Too subjective to automate safely:** The book relies heavily on visual judgment, context, or flexible definitions.

### Page-reference convention

- **PDF p.X** means the uploaded PDF page.
- **Book p.Y** means the printed page number visible in the book.
- In the main text, Book p.1 begins at approximately PDF p.15.

### Controlling methodological constraints from the book

1. Candlestick patterns are **additional evidence**, not replacements for trend, support/resistance, volume, or other technical tools (PDF pp.18-22; Book pp.4-8).
2. Real examples need not match ideal drawings exactly; definitions contain subjectivity (PDF pp.19-21; Book pp.5-7).
3. A completed candle normally requires the close. Intrabar interpretation is provisional unless a lower timeframe independently confirms in the direction of the prevailing trend (PDF p.21; Book p.7).
4. Candlestick signals generally **do not provide price targets**. Targets must come from support/resistance, retracements, swing objectives, trendlines, moving averages, Elliott Wave, or other methods (PDF p.22; Book p.8).
5. A reversal signal means the prior trend may change, pause, or become lateral; it does not guarantee an immediate opposite trend (PDF pp.41-42; Book pp.27-28).
6. A countertrend candle signal should not automatically create an opposite-direction trade. Nison explicitly recommends placing new positions from reversal signals in the direction of the major trend; countertrend signals can instead justify reducing or exiting an existing position (PDF p.42; Book p.28).
7. Pattern importance increases when multiple independent techniques converge at the same area (Part Two, especially PDF pp.191-223; Book pp.177-208).

---

# 2. Executive findings for Apex

## 2.1 Candlesticks should be a timing and confirmation layer, not the trade-analysis core

The central implementation conclusion is that Apex should not route trades primarily from candle names. Nison repeatedly combines candles with trend direction, prior price action, support/resistance, retracements, moving averages, oscillators, volume/open interest, Elliott Wave, and market profile.

**Likely Apex change:**

- Keep the shared market-context layer authoritative.
- Add a `candlestick_evidence` component that can:
  - detect candidate patterns,
  - determine completion state,
  - score contextual relevance,
  - strengthen or weaken an already eligible setup,
  - help time entries or exits.
- Do not let a candle pattern bypass regime, reward-to-risk, liquidity, stop, or target rules.

## 2.2 `READY_NOW` must require a closed and context-valid pattern

The book treats the close as pivotal. A daily hammer, engulfing pattern, dark-cloud cover, piercing pattern, star, doji, or continuation pattern is not fully known until the candle closes. Nison allows anticipatory action only when a lower timeframe supplies an aligned signal and the prevailing trend supports the trade (PDF p.21; Book p.7).

**Apex implication:**

- `TRIGGER_PROVISIONAL`: active candle currently resembles the pattern.
- `CONFIRMATION_PENDING_CLOSE`: pattern definition depends on the close.
- `READY_NOW`: completed pattern, valid context, valid entry zone, acceptable stop and target geometry.
- Lower-timeframe confirmation must not be used to invent confirmation against a strong higher-timeframe trend.

## 2.3 Candle reversals are warnings of trend change, not automatic opposite trades

A bearish candle after an uptrend may mean:

- take profit on longs,
- tighten risk,
- expect a range,
- wait for further evidence,
- or, only in a larger downtrend, enter a short.

This directly addresses misleading Apex outputs. The output must distinguish:

- `BULLISH_BIAS_WEAKENING`
- `LONG_EXIT_WARNING`
- `BEARISH_REVERSAL_CANDIDATE`
- `CONFIRMED_SHORT_SETUP`

These are not interchangeable.

## 2.4 Candlesticks do not justify fixed targets

The book explicitly states that candlesticks do not provide price objectives (PDF p.22; Book p.8). Therefore:

- no candle pattern should generate a 10% target;
- no candle-body multiple should be treated as a book-derived target;
- target selection must use the structural target engine;
- expected movement must remain separate from leverage return.

## 2.5 Pattern quality must be contextual and continuous, not binary

The book accepts variations and repeatedly evaluates:

- body size,
- shadow length,
- penetration depth,
- gaps/windows,
- prior trend speed and duration,
- nearby resistance/support,
- confirmation candle,
- volume,
- and repeated signals.

Apex should detect both:

- `ideal_geometry_match`, and
- `contextual_variant_match`.

But variants must have lower evidence strength and require more confirmation.

## 2.6 Crypto requires explicit adaptation of gaps and opens

Many Japanese patterns depend on a session opening above or below the prior candle. Crypto trades continuously. On intraday crypto candles, the next candle open is usually equal or nearly equal to the prior close, so classical gaps are rare except during data discontinuities or illiquidity.

**Apex adaptation:**

- Preserve body-overlap and close-penetration logic.
- Treat gap requirements as:
  - strict for sessionized markets,
  - optional/contextual for continuous crypto,
  - never fabricated.
- Do not label ordinary non-overlapping bodies as true windows if high-low ranges overlap.
- Validate modified crypto definitions independently.

---

# 3. Core principles

## 3.1 Candles add evidence; they do not replace existing technical structure

**Source:** Chapter 1, PDF pp.18-22, Book pp.4-8.

### Market context
All markets and timeframes with reliable OHLC data.

### Implementation meaning
Candlestick interpretation should live alongside, not above:

- trend,
- support/resistance,
- moving averages,
- oscillators,
- volume,
- open interest,
- retracements,
- and broader context.

### Exact Apex change
Add a composable evidence object rather than a candle-only strategy router.

### Tests

- A bullish engulfing pattern in a strong higher-timeframe downtrend cannot independently become high-confidence long.
- A hammer at major support with trend/volume agreement receives more weight than the same hammer in the middle of noise.
- Removing candle evidence should not change market-regime classification.

---

## 3.2 Context before shape

**Source:** PDF pp.19-22, 41-48; Book pp.5-8, 27-34.

The identical candle can mean different things based on location. A long-lower-shadow candle is:

- a **hammer** only after a decline,
- a **hanging man** only after an advance,
- neither when no preceding trend exists.

### Objective Apex measurements

- preceding directional return,
- swing sequence,
- distance from recent high/low,
- trend age,
- acceleration,
- position inside range,
- proximity to structural support/resistance.

### Subjective element
What counts as “high-price area,” “low-price area,” “protracted,” or “fast” is not rigidly defined.

### Rule status

- Prior-trend requirement: **directly supported**.
- Exact lookback and thresholds: **requires empirical validation**.

---

## 3.3 The close normally completes the pattern

**Source:** PDF pp.20-22, 38-40; Book pp.6-8, 24-26.

The open and close are central to candlestick construction. A changing active candle may stop matching the pattern before close.

### Active-candle policy for Apex

- Active candle can trigger `PROVISIONAL` status.
- Closed-candle logic is the default.
- An anticipatory entry is permitted only when:
  1. the higher-timeframe pattern is still provisional,
  2. a lower-timeframe completed pattern confirms,
  3. the prevailing trend supports the direction,
  4. structural risk remains valid.

### Tests

- Recompute provisional patterns on every update.
- Ensure no backtest uses final candle close before that close occurred.
- Track provisional-to-failed conversion rate.

---

## 3.4 Reversal means trend change, not guaranteed trend inversion

**Source:** Chapter 4, PDF pp.41-42, Book pp.27-28.

### Output semantics

A top reversal candle should produce one of:

- prior advance may be ending,
- long risk should be reduced,
- consolidation risk increased,
- bearish setup candidate,
- confirmed short only with larger bearish context.

### Apex change
Separate:

- pattern polarity,
- trend-change warning,
- trade direction,
- trade approval.

---

## 3.5 Multiple technical techniques

**Source:** Part Two, PDF pp.191-294, Book pp.177-280.

Nison’s strongest practical emphasis is confluence. Several candle signals at one area, or candles aligned with Western tools, create stronger evidence than an isolated candle.

### Apex confluence categories

- candle + structural level,
- candle + polarity retest,
- candle + retracement,
- candle + moving average,
- candle + oscillator divergence/extreme,
- candle + volume/open interest,
- candle + higher-timeframe candle,
- repeated candle signals at the same zone.

### Warning
Correlated indicators should not be counted as independent evidence. For example, RSI and stochastic can reflect similar momentum information.

---

# 4. Candlestick construction and measurable anatomy

**Source:** Chapter 3, PDF pp.35-40, Book pp.21-26.

## 4.1 Required market data

Minimum:

- open,
- high,
- low,
- close,
- timestamp,
- timeframe.

Optional but important:

- volume,
- open interest,
- taker volume,
- session boundary metadata,
- missing-data and exchange-outage flags.

## 4.2 Deterministic candle metrics

For each candle Apex can calculate:

- `range = high - low`
- `body = abs(close - open)`
- `upper_shadow = high - max(open, close)`
- `lower_shadow = min(open, close) - low`
- `body_to_range`
- `upper_shadow_to_body`
- `lower_shadow_to_body`
- close location within range,
- open location within range,
- body direction,
- ATR-normalized body/range,
- relative body percentile,
- relative volume percentile.

## 4.3 Line classifications

### Long white/black body
Directional session with relatively large body.

### Spinning top
Small real body; indicates balance/indecision. Neutral in a lateral range and more meaningful after directional movement.

### Doji
Open and close equal or very close. “Very close” must be instrument-specific.

### Shaven head/bottom
No or negligible upper/lower shadow.

### Implementation requirement
All definitions need volatility/tick-size normalization. Exact equality is unsafe for crypto and floating-point data.

---

# 5. Reversal setups

## 5.1 Hammer

**Source:** Chapter 4, PDF pp.42-48, Book pp.28-34.

### Regime and context
A decline or downtrend, including a minor downtrend. A hammer shape without a prior decline is not a hammer.

### Structure

- small real body near top of range,
- lower shadow ideally at least twice body height,
- little or no upper shadow,
- body color secondary; white is somewhat stronger.

### Interpretation
Selling drove price lower, but buyers recovered much of the session.

### Entry

- **Aggressive:** after hammer close when at strong support and broader trend permits.
- **Conservative:** after next candle closes above hammer close or breaks hammer high.

### Closed-candle requirement
Yes. Shape depends on final close.

### Invalidation and stop
Below hammer low plus volatility/tick buffer. A decisive close below the hammer/support invalidates the bottom signal.

### Target
Not supplied by the hammer. Use next resistance, prior swing, retracement objective, or other structural target.

### Failure conditions

- no prior decline,
- strong bearish momentum candle immediately before it without confirmation,
- break of major support without reclaim,
- weak follow-through,
- close below hammer low.

### Apex measurements

- shadow/body ratios,
- close location,
- prior return/trend,
- support proximity,
- confirmation close,
- volume reaction.

### Exact likely Apex change
Pattern detector returns `hammer_candidate`; setup router decides whether it is exit warning, bounce candidate, or approved long.

### Tests

- shape in range midpoint rejected as hammer trade.
- lower-shadow threshold configurable.
- contextual variant receives lower score.
- no target generated from candle alone.

---

## 5.2 Hanging man

**Source:** PDF pp.42-52, Book pp.28-38.

### Regime
After a rally/uptrend.

### Structure
Same basic anatomy as hammer.

### Confirmation
Nison stresses bearish confirmation:

- next open below hanging-man body,
- or next black candle closes below hanging-man close/body.

### Entry

- **Aggressive:** reduce longs at close in an overextended area.
- **Conservative short:** only after bearish confirmation and compatible major trend.

### Stop
Above hanging-man high or confirmation/retest high.

### No-trade condition
In a major uptrend, the pattern may justify long liquidation but not a new short.

### Target
External structural method only.

---

## 5.3 Bullish and bearish engulfing

**Source:** PDF pp.52-57, Book pp.38-43.

### Preconditions
Clearly defined prior trend, even if short term.

### Geometry

- two candles,
- second real body engulfs first real body,
- shadows need not be engulfed,
- colors normally opposite,
- exception where first body is nearly doji.

### Strengthening evidence

- first body small, second body large,
- protracted or fast prior move,
- heavy volume on second candle,
- second body engulfs multiple bodies.

### Entry

- Aggressive on completed second candle at meaningful structure.
- Conservative on break of pattern extreme or retest.

### Stop
Beyond two-candle pattern extreme.

### Invalidation
Close beyond the opposite extreme or strong counter-body reclaim.

### Failure/no-use

- no prior trend,
- pattern in random mid-range,
- second body only engulfs shadows but not body,
- nearby obstacle removes reward.

### Direction

- Bullish engulfing after decline.
- Bearish engulfing after advance.

### Apex automation
Direct geometry is automatable. “Clearly definable trend,” “protracted,” and “fast” require calibrated context metrics.

---

## 5.4 Dark-cloud cover

**Source:** PDF pp.57-62, Book pp.43-48.

### Regime
After an uptrend or at top of congestion with other bearish evidence.

### Geometry

- first candle strong white body,
- second opens above prior high in strict definition,
- second closes well into first white body,
- deeper penetration is more bearish,
- more than 50% penetration is a stronger/stricter criterion.

### Confirmation
If penetration is less than half, wait for further bearish confirmation.

### Strengthening evidence

- long directional bodies,
- failure above major resistance,
- heavy volume/open interest on failed high,
- deep penetration,
- confluence with polarity resistance.

### Entry

- Aggressive: reduce long on close.
- Conservative: short after close below midpoint/low or failed retest, only if strategy context permits.

### Stop
Above second candle high.

### Invalidation
Strong white close above pattern highs.

### Crypto adaptation
Strict open-above-high gap is uncommon. A modified “push above prior high followed by deep bearish close” may be tested, but must be labeled operational interpretation rather than classical dark-cloud cover.

---

## 5.5 Piercing pattern

**Source:** PDF pp.62-67, Book pp.48-53.

### Regime
Falling market/downtrend.

### Geometry

- first candle long black body,
- second opens below prior low in strict version,
- second closes more than halfway into prior black body.

### Key rule
Nison gives less flexibility than with dark-cloud cover. Less than halfway can be an on-neck, in-neck, or thrusting continuation signal rather than a bullish reversal.

### Entry

- Aggressive on completed piercing candle at support.
- Conservative on break of second candle high or successful retest.

### Stop
Below pattern low.

### Invalidation
Long black close below pattern lows suggests another down leg.

### Target
Structural only.

### Tests
Exact 50% boundary, gap adaptation, and context filters must be separately validated.

---

## 5.6 On-neck, in-neck, and thrusting patterns

**Source:** PDF pp.63-66, Book pp.49-52.

### Context
Usually bearish continuation during a decline when the white recovery candle fails to penetrate more than halfway into the prior black body.

### Interpretation

- On-neck: close near prior low.
- In-neck: slight penetration.
- Thrusting: stronger recovery but still below midpoint.

### Trigger
Break below the white candle low.

### Exception
Thrusting can be bullish in a rising market and may be bullish when repeated twice within several days.

### Apex risk
Names are less important than penetration ratio and context. Implement as a `failed_bullish_recovery` feature rather than three rigid strategies initially.

---

## 5.7 Morning star and evening star

**Source:** Chapter 5, PDF pp.69-78, Book pp.55-64.

### Morning star

- downtrend,
- long black body,
- small body/star lower than first body,
- third white body closes well into first black body.

### Evening star
Mirror at top.

### Confirmation
Third candle completes the pattern. Second gap is ideal but not always necessary.

### Strengthening evidence

- gaps around star,
- deep third-candle penetration,
- lighter volume on first candle and heavier volume on third,
- support/resistance confluence.

### Entry

- Aggressive at completion close.
- Conservative beyond third-candle extreme or on retest.

### Stop
Beyond pattern extreme.

### Invalidation
Close beyond star/pattern extreme or strong resumption candle.

### Active-candle limitation
Three-candle pattern remains provisional until third close.

### Crypto adaptation
Body separation can be used, but strict session gaps require special handling.

---

## 5.8 Morning/evening doji star and abandoned baby

**Source:** PDF pp.78-83, Book pp.64-69.

### Doji star
A doji separated from the prior real body after a trend. It is a potent warning, but the next session should confirm.

### Negation

- Uptrend doji star negated if next candle is bullish and gaps higher.
- Downtrend doji star negated if next candle is bearish and gaps lower.

### Abandoned baby
Doji isolated by gaps before and after, including shadows. Extremely rare and considered a major reversal pattern.

### Apex recommendation

- Doji-star candidate is a warning state.
- Do not use abandoned-baby strategy in crypto unless true gaps exist.
- Require third-candle confirmation.

---

## 5.9 Shooting star and inverted hammer

**Source:** Chapter 5, approximately PDF pp.84-92, Book pp.70-78.

### Shared anatomy
Small real body near low of range, long upper shadow, little/no lower shadow.

### Shooting star
Appears after advance; bearish warning. Body gap from prior body strengthens classical form.

### Inverted hammer
Appears after decline; potential bullish reversal but requires bullish confirmation, because the upper shadow alone does not prove buyers retained control.

### Entry

- Shooting star: reduce longs; short only after confirmation and trend agreement.
- Inverted hammer: wait for next bullish open/close above body/high.

### Stops
Beyond pattern extreme.

### Target
Structural only.

---

## 5.10 Harami and harami cross

**Source:** Chapter 6, PDF pp.93-102, Book pp.79-88.

### Geometry
A large first body contains a smaller second body. It is the reverse of an engulfing pattern.

### Context

- Bearish harami after advance.
- Bullish harami after decline.
- Harami cross uses a doji as second candle and is more significant.

### Meaning
Prior directional momentum contracts; the market enters indecision.

### Confirmation
Because it often signals deceleration rather than immediate reversal, require break of the two-candle range or supporting evidence.

### Apex use
Good for `trend_weakening` and `compression_after_impulse`; weaker as direct trade trigger.

---

## 5.11 Tweezers tops and bottoms

**Source:** PDF pp.102-108, Book pp.88-94.

### Geometry
Two or more candles test approximately the same high or low.

### Context
At a prior trend extreme, especially when individual candles also form another reversal signal.

### Multi-timeframe note
The matching extreme need not occur on adjacent sessions on longer-term charts.

### Automation
Use tick/ATR tolerance, not exact equality.

### Entry
On confirmed rejection/break away from repeated extreme.

### Stop
Beyond tweezer extreme.

### Target
Structural.

---

## 5.12 Belt-hold lines

**Source:** PDF pp.108-112, Book pp.94-98.

### Bullish belt hold
Long white candle opening at/near low in low-price area.

### Bearish belt hold
Long black candle opening at/near high in high-price area.

### Strength
Longer body and absence of shadow at open increase relevance. Repeated testing of the belt-hold line weakens it.

### Apex use
Momentum/rejection evidence, not standalone target source.

---

## 5.13 Upside-gap two crows

**Source:** PDF pp.112-115, Book pp.98-101.

### Regime
Uptrend.

### Structure
Long white candle, then two black bodies above it; second black body engulfs first black body while both remain gapped above white body.

### Interpretation
Rare bearish reversal warning.

### Crypto applicability
Low because true windows are rare. Prohibit classical label without real high-low gap.

---

## 5.14 Three black crows

**Source:** PDF pp.115-119, Book pp.101-105.

### Structure
Three consecutive long black candles with progressively lower closes, usually opening within prior bodies and closing near lows.

### Context
After an uptrend or at a high-price area.

### Interpretation
Persistent selling and trend deterioration.

### Rejection
If already deeply extended down, pattern may be late and poor for new short entry.

### Apex use
Trend transition/continuation evidence; chase controls essential.

---

## 5.15 Counterattack lines

**Source:** PDF pp.119-123, Book pp.103-107.

### Structure
Opposite-colored long bodies in a trend, with second close approximately equal to prior close.

### Difference from piercing/dark cloud
Second body does not penetrate deeply; matching close is central.

### Automation
Close equality needs ATR/tick tolerance.

### Entry
Require next-candle confirmation because the pattern is a confrontation rather than decisive control.

---

## 5.16 Three mountains, three rivers, three Buddha

**Source:** PDF pp.123-127, Book pp.107-113.

### Three mountain top
Three tests of high area; central peak higher creates a three-Buddha/head-and-shoulders analogue.

### Three river bottom
Three low-area tests; middle low deepest creates inverted three-Buddha.

### Confirmation
Break of intervening reaction level, ideally with strong candle or gap.

### Apex mapping
These belong to market structure/pattern modules, with candle evidence helping confirmation. Avoid duplicate candle-only implementation.

---

## 5.17 Dumpling top, fry-pan bottom, tower top/bottom

**Source:** PDF pp.127-132, Book pp.113-118.

### Dumpling/fry-pan
Rounded top/bottom requiring a confirming downside/upside window.

### Tower
Long directional candle, lateral transition, then strong opposite directional candle(s).

### Crypto issue
Window requirement limits classical dumpling/fry-pan use. Tower patterns can be adapted as rounded distribution/accumulation with expansion confirmation.

### Automation risk
Rounded shape detection is subjective and should be secondary until validated.

---

# 6. Continuation setups

## 6.1 Windows

**Source:** Chapter 7, PDF pp.133-143, Book pp.119-129.

A window is a true price gap between one candle’s high/low and the next candle’s low/high. Windows are continuation evidence and future support/resistance.

### Rules

- Rising window: support.
- Falling window: resistance.
- Markets often return to test the window.
- A window is “closed” when price fully fills it; closure weakens the continuation implication.
- Three windows can signal move maturity/exhaustion in traditional interpretation.

### Crypto policy
True windows are rare. Do not convert ordinary body gaps into windows. Potential use only with:

- exchange reopenings,
- illiquid tokens,
- missing-session data excluded,
- or higher-timeframe composite/session candles.

---

## 6.2 Tasuki gaps

**Source:** PDF pp.143-145, Book pp.129-131.

### Bullish upward-gap tasuki
Rising window, then opposite-color pullback that partially fills but does not close window. Continuation expected.

### Bearish downward-gap tasuki
Mirror.

### Invalidation
Window closes.

### Applicability
Prohibited for standard continuous crypto unless genuine gap exists.

---

## 6.3 High-price and low-price gapping plays

**Source:** PDF pp.145-148, Book pp.131-134.

### Structure

- sharp directional move,
- small-body consolidation near extreme,
- continuation gap in trend direction.

### Apex adaptation
The underlying concept maps well to:

- impulse,
- tight consolidation,
- range compression,
- expansion breakout.

The strict gap is not necessary for a crypto operational variant, but this variant requires empirical validation and should not retain the classical name without a gap.

---

## 6.4 Gapping side-by-side white lines

**Source:** PDF pp.148-149, Book pp.134-135.

Rare continuation patterns involving a window and two similar white candles. Direction depends on gap direction and context.

### Apex recommendation
Do not prioritize. Rare, gap-dependent, and likely low sample size.

---

## 6.5 Rising and falling three methods

**Source:** PDF pp.149-157, Book pp.135-143.

### Rising three methods

- long white impulse candle,
- several small bodies, usually black, contained within first candle range,
- final strong white candle closes at a new high.

### Falling three methods
Mirror.

### Meaning
A controlled pause within an established trend, followed by resumption.

### Entry

- Aggressive on final candle close.
- Conservative on breakout/retest of consolidation high/low.

### Stop
Beyond consolidation or first impulse candle invalidation depending strategy.

### Target
External structural method.

### Apex relevance
High. This is a strong candidate for a deterministic continuation setup because it does not require a true gap.

### Tests

- contained-body tolerance,
- number of pause candles,
- volume contraction/expansion,
- maximum pullback depth,
- breakout close quality.

---

## 6.6 Three advancing white soldiers and stalled/advance-block variants

**Source:** PDF pp.157-162, Book pp.143-148.

### Three soldiers
Three strong white candles with successively higher closes, usually opening within prior bodies.

### Context
After decline or at low-price area, it can mark strong bullish reversal/advance.

### Warnings

- Advance block: bodies shrink and/or upper shadows grow, showing weakening.
- Stalled pattern: third candle small near top of prior long white candle.

### Apex implication
Three bullish candles are not automatically a buy. Location and chase distance matter. Advance-block/stalled variants should reduce continuation score and may trigger profit-taking.

---

## 6.7 Separating lines

**Source:** PDF pp.162-163, Book pp.147-148.

Opposite-colored candles share the same opening level, with second candle resuming the prevailing trend.

### Automation
Open equality needs tolerance. In crypto, exact consecutive opens are common, so the pattern may be overly frequent and require strong body/context filters.

---

# 7. Doji methodology

**Source:** Chapter 8, PDF pp.163-178, Book pp.149-164.

## 7.1 General doji rule

A doji reflects balance/indecision and is most important after a mature directional move. In a sideways range, doji are common and often insignificant.

### Doji threshold
Instrument-specific tolerance based on:

- tick size,
- body/range ratio,
- ATR,
- typical body size.

## 7.2 Doji at tops

Nison gives doji at tops greater reversal weight than doji at bottoms because markets can fall under their own weight, while bottoms often need evidence of buying force.

### Apex asymmetry
Bearish doji warning after extended rally can reduce long confidence. Bullish doji after decline should normally require stronger confirmation.

## 7.3 Doji after long white candle

A doji after a long white candle indicates sudden loss of bullish momentum and can be a warning, especially near resistance or after an extended run.

## 7.4 Long-legged doji and rickshaw man

Long upper and lower shadows show extreme indecision/volatility. Context and subsequent confirmation are essential.

## 7.5 Gravestone doji

Open/close near low with long upper shadow, important after an advance; signals rejection of higher prices.

## 7.6 Doji as support/resistance

The doji session’s area can later act as a reference zone.

## 7.7 Tri-star

Three doji arranged like a morning/evening star. Extremely rare and considered major reversal evidence.

### Apex recommendation
Doji should primarily affect evidence and risk states. Avoid direct doji-only entries unless combined with structure and confirmation.

---

# 8. Confluence, support, resistance, polarity, and breakouts

## 8.1 Confluence of candlesticks

**Source:** Chapter 10, PDF pp.191-199, Book pp.177-184.

Multiple candlestick patterns at the same area increase the significance of that zone. The zone, not just the candle name, becomes important.

### Apex implementation
Create `evidence_cluster` with:

- price zone,
- pattern list,
- timestamps,
- independent evidence types,
- decay,
- number of successful tests,
- failure/close-through status.

Avoid double-counting multiple labels on the same candle geometry.

## 8.2 Candlesticks with trendlines

**Source:** Chapter 11, PDF pp.199-223, Book pp.185-208.

### Use cases

- candle reversal at trendline,
- trendline break confirmed by candle,
- false break/spring/upthrust,
- old support becoming resistance and vice versa.

### Springs and upthrusts

- Spring: temporary break below support followed by recovery back above.
- Upthrust: temporary break above resistance followed by failure back below.

Candles can reveal rejection and time entries.

### Entry

- Aggressive after recovery close back through level.
- Conservative on retest of reclaimed/lost level.

### Stop
Beyond spring/upthrust extreme.

### Target
Opposite range boundary, next structural level, or broader setup objective.

### Polarity
Broken resistance can become support; broken support can become resistance. Candlestick confirmation at the retest strengthens the setup.

### Protective stops
Nison explicitly emphasizes placing protective stops and adjusting them to pattern/structure rather than using candles without risk control.

---

# 9. Retracement methodology

**Source:** Chapter 12, PDF pp.223-230, Book pp.209-214.

Candlestick reversal evidence at common retracement levels can time entries in the direction of the prevailing trend.

### Relevant levels
The chapter uses common Western retracement concepts, particularly 38%, 50%, and 62% areas.

### Apex rule
Retracement level alone is not entry. Require:

- valid impulse leg,
- eligible trend,
- retracement band,
- candle confirmation,
- structural stop,
- room to target.

### Aggressive vs conservative

- Aggressive: completed reversal candle in retracement zone.
- Conservative: break of reversal-pattern extreme or retest.

### Tests
Validate level bands, impulse selection, and pattern combinations by timeframe.

---

# 10. Moving averages and trend tools

**Source:** Chapter 13, PDF pp.231-242, Book pp.215-226.

## 10.1 Moving-average roles

- dynamic support/resistance,
- trend direction,
- crossover confirmation,
- timing confluence with candle patterns.

## 10.2 Types covered

- simple moving average,
- weighted moving average,
- exponential moving average,
- MACD,
- dual moving averages.

## 10.3 Book methodology

Candlestick signals become more useful when they appear at a moving average or when moving-average direction agrees. A candle can help obtain earlier timing than waiting for a lagging crossover.

### Apex implementation

- MA is context, not an unconditional entry.
- Candle signal at rising MA in uptrend can enable pullback continuation.
- Bearish candle at falling MA can enable short continuation.
- Countertrend candle against strongly sloped MA is secondary/exit warning.

### Objective metrics

- slope,
- price distance in ATR,
- touch/rejection count,
- crossover state,
- MA stack,
- candle close relative to MA.

### Subjective/validation issues
Exact periods and MA type are not universally prescribed and must be tested.

---

# 11. Momentum and oscillators

**Source:** Chapter 14, PDF pp.243-256, Book pp.227-240.

## 11.1 Oscillator role

Oscillators identify overbought/oversold conditions and divergences, but can remain extreme in strong trends. Candlestick patterns can provide timing after an oscillator warning.

## 11.2 RSI

Covered use includes:

- extreme readings,
- divergence,
- confirmation with candle reversal patterns.

## 11.3 Stochastics

Similarly used for extremes, crossovers, and divergence, with candles helping pinpoint action.

## 11.4 Momentum

Momentum loss or divergence can support a candle reversal.

### Apex rule
Oscillator extreme is not a trade. Require:

- regime-aware interpretation,
- price structure,
- completed candle trigger,
- acceptable geometry.

### Strong trend warning
Do not short merely because RSI is overbought or buy merely because it is oversold.

### Deterministic candidates

- divergence detection: operational interpretation requiring validation,
- oscillator extreme plus reversal candle at structure: directly consistent with book,
- exact RSI/stochastic thresholds: requires validation.

---

# 12. Volume and participation

**Source:** Chapter 15, PDF pp.257-268, Book pp.241-252.

## 12.1 Volume with candles

Volume can confirm the force behind candle signals. High volume on reversal or breakout candles may strengthen them, but volume must be interpreted in context.

## 12.2 On-balance volume

OBV trend/divergence can corroborate candle patterns.

## 12.3 Tick volume

Used where actual volume is unavailable, especially foreign exchange. For crypto, actual exchange volume is available but fragmented by venue.

## 12.4 Open interest

Open interest changes help distinguish new participation from liquidation/short covering in futures.

### Crypto translation
Use:

- exchange volume,
- aggregated volume if available,
- open interest,
- funding,
- taker imbalance,
- liquidation data.

Only volume/OI concepts are directly book-supported; funding and liquidation adaptation are external operational additions.

### Apex evidence examples

- bullish reversal + rising volume + rising OI: stronger new-long participation candidate,
- rally + falling OI: possible short covering rather than durable demand,
- bearish break + rising OI: stronger new-short participation candidate,
- reversal candle on weak volume: lower confidence.

These interpretations require careful crypto validation.

---

# 13. Multi-timeframe analysis

The book applies candlesticks from intraday through monthly charts and explicitly allows a lower timeframe to help anticipate a higher-timeframe close when aligned with prevailing trend (PDF pp.20-21; Book pp.6-7).

## Apex hierarchy

1. **Context timeframe:** major regime and structural boundaries.
2. **Setup timeframe:** candle formation and setup eligibility.
3. **Trigger timeframe:** execution confirmation.
4. **Management timeframe:** stop/trailing updates.

## Rules

- Higher-timeframe candle must remain provisional until close.
- Lower-timeframe confirmation may accelerate entry only when it supports higher-timeframe regime.
- A lower-timeframe opposite candle can warn of pullback but should not automatically reverse the higher-timeframe bias.
- Weekly/monthly patterns imply longer horizons than intraday patterns.

---

# 14. Entry methodology

## 14.1 Pattern recognition is not trade approval

Apex should apply this sequence:

1. identify context and regime,
2. detect candidate candle pattern,
3. verify prior-trend/location requirement,
4. wait for completion/confirmation,
5. check confluence,
6. determine structural entry zone,
7. determine invalidation and stop,
8. calculate structural targets,
9. reject poor reward-to-risk,
10. select state and wording.

## 14.2 Aggressive entries

Permitted when:

- candle closed,
- pattern is high quality,
- major trend supports direction,
- pattern occurs at strong structure,
- stop is close and logical,
- no chase.

Examples:

- hammer close at major support in uptrend pullback,
- bullish engulfing close at retracement support,
- spring recovery close with bullish candle,
- rising-three-method completion.

## 14.3 Conservative entries

- next-candle break of pattern high/low,
- breakout close plus retest,
- polarity retest,
- follow-through candle,
- lower-timeframe confirmation after higher-timeframe pattern completes.

## 14.4 Missed-entry logic

A valid pattern becomes `MISSED_ENTRY` when:

- price moves beyond maximum chase,
- reward to nearest target falls below threshold,
- stop distance expands excessively,
- retest never occurs for a retest-only strategy.

---

# 15. Stop-loss methodology

Candlesticks are useful for defining local invalidation, but risk control must be structural.

## Stop hierarchy

1. pattern extreme,
2. support/resistance zone boundary,
3. swing invalidation,
4. ATR/tick buffer,
5. liquidation safety requirement.

## Examples

- Hammer long: below hammer low.
- Hanging-man short: above pattern/confirmation high.
- Engulfing: beyond two-candle extreme.
- Star: beyond star/pattern extreme.
- Spring: below false-break low.
- Upthrust: above false-break high.
- Rising three methods: below consolidation/impulse invalidation.

## Prohibited stop behavior

- stop chosen only to manufacture R:R,
- fixed percentage unrelated to structure,
- stop inside candle noise,
- stop beyond liquidation price,
- no stop because candle “should work.”

---

# 16. Take-profit methodology

**Direct book rule:** Candlesticks do not provide price targets (PDF p.22; Book p.8).

## Apex target sources

- prior support/resistance,
- polarity level,
- range boundary,
- retracement/extension,
- trendline/channel,
- moving average,
- swing objective,
- Elliott Wave objective,
- market-profile reference where available.

## Target hierarchy

1. nearest structural obstacle,
2. setup objective,
3. higher-timeframe objective,
4. runner target if structure remains intact.

## Required output
Every target must carry provenance, for example:

- `TP1: prior 15m resistance`
- `TP2: 1h range high`
- `Runner: 4h extension only if breakout holds`

Never label a candle-derived percentage as a book target.

---

# 17. Trade-management methodology

## Book-supported ideas

- Countertrend reversal signals can justify reducing/closing an existing position.
- Some practitioners stay in a trade until an opposite candle signal appears.
- Candlestick evidence should be combined with other tools.
- Protective stops remain essential.

## Apex operational lifecycle

- partial at first structural obstacle,
- retain position only if trend and participation remain valid,
- trail behind confirmed swing or polarity level,
- tighten risk on strong opposite candle at target/resistance,
- exit on confirmed pattern failure or invalidation,
- do not reverse automatically after exit warning.

This precise lifecycle is a reasonable operational interpretation and must be backtested.

---

# 18. Setup expiry and time estimation

The book does not provide universal bar-count expiry. Horizon follows the timeframe of the pattern and surrounding structure.

## Apex candidate rules

- One-candle reversal setup: confirmation expected within 1-3 trigger bars.
- Multi-candle pattern: follow-through window scaled to pattern duration.
- Retest setup: expires if price reaches target area without retest or if reward collapses.
- Continuation setup: expires if consolidation breaks opposite direction or lasts beyond tested duration.
- Higher-timeframe pattern: longer expected holding period.

All exact numbers require empirical validation.

## Output
Report:

- trigger timeframe,
- expected horizon band,
- expiry condition,
- not a forced universal short window.

---

# 19. Risk and loss avoidance

## No-trade conditions directly implied by the book

- pattern lacks required prior trend,
- active candle not closed,
- reversal signal is against major trend without a tested countertrend strategy,
- pattern appears in noisy lateral action where it is not meaningful,
- candle has no support from structure/other evidence,
- target cannot be defined independently,
- confirmation failed,
- pattern invalidated,
- gap-dependent pattern appears without a true gap,
- pattern is already too extended to enter.

## Additional Apex risk filters

- insufficient liquidity,
- spread/slippage too high,
- data gaps/outages,
- liquidation buffer inadequate,
- funding/OI risk extreme,
- weak net reward after fees.

These crypto-specific filters are not from Nison but are required for safe implementation.

---

# 20. Trade-selection and ranking

## Evidence dimensions

1. Major-trend alignment
2. Pattern location
3. Geometry quality
4. Closed/confirmed state
5. Structural confluence
6. Multi-timeframe agreement
7. Participation/volume
8. Stop quality
9. Target room
10. Liquidity/data quality
11. Pattern rarity/sample reliability
12. Chase distance

## Confidence semantics

Confidence must mean **strength and completeness of evidence**, not win probability unless calibrated.

Recommended fields:

- `pattern_quality`
- `context_quality`
- `confirmation_quality`
- `risk_quality`
- `data_quality`
- `overall_evidence = weak/moderate/strong`

Avoid contradictory output such as `READY_NOW` with low confidence and poor R:R.

---

# 21. Output wording

## State vocabulary

- **WATCH:** Relevant context exists; no completed trigger.
- **APPROACHING_ENTRY:** Price is near structural area.
- **TRIGGER_PROVISIONAL:** Active candle currently resembles pattern.
- **CONFIRMATION_PENDING_CLOSE:** Final close is required.
- **REVERSAL_WARNING:** Prior trend may pause/change; opposite trade not approved.
- **EXIT_WARNING:** Manage existing position.
- **READY_NOW:** Completed, context-valid trigger with approved geometry.
- **RETEST_PENDING:** Completion occurred; selected entry method waits for retest.
- **MISSED_ENTRY:** Entry is too far/chased or R:R degraded.
- **INVALIDATED:** Pattern/structure failed.
- **NO_TRADE:** No eligible trade.

## Example

Instead of:

> READY_NOW - bearish hanging man - confidence 45

Use:

> **Long-exit warning, not yet a confirmed short.** A completed hanging-man candle formed after a 15m advance, but the 1h trend remains bullish. A short becomes eligible only after a close below the pattern low or a failed retest, with room to the next support.

---

# 22. Strategy catalogue

| Setup | Regime | Direction | Preconditions | Trigger | Entry | Stop | Targets | Expiry | Rejection rules | Required data |
|---|---|---|---|---|---|---|---|---|---|---|
| Hammer reversal | Decline / bullish HTF pullback | Long | Prior decline, support preferred | Completed hammer; optional bullish follow-through | Close or break/retest high | Below hammer low | Structural resistance | 1-3 trigger bars candidate | No decline, active candle, strong support loss | OHLCV, swings, ATR |
| Hanging man | Mature rally | Exit long / conditional short | Prior advance | Bearish next-candle confirmation | Confirmation close/retest | Above pattern high | Structural support | Short | Major trend strongly up, no confirmation | OHLCV, trend |
| Bullish engulfing | Decline | Long | Defined down move, low/support | Second body engulfs first | Close or break high | Pattern low | Resistance/swing | Prompt follow-through | No prior decline | OHLCV |
| Bearish engulfing | Advance | Exit long / short | Defined rise, high/resistance | Second body engulfs first | Close or break low | Pattern high | Support/swing | Prompt | No prior rise | OHLCV |
| Dark-cloud cover | Uptrend/top range | Bearish warning/short | Strong white candle, failed high | Deep bearish close into prior body | Close or confirmation | Second high | Support | Short | Shallow penetration, no resistance | OHLCV, volume |
| Piercing pattern | Downtrend | Long | Long black candle, low area | White close >50% into prior body | Close or break high | Pattern low | Resistance | Short | Penetration below midpoint | OHLCV |
| Morning star | Downtrend | Long | Long black, star, bullish third candle | Third candle closes into first body | Third close or retest | Pattern low | Resistance | 1-3 bars | Incomplete third candle | OHLCV |
| Evening star | Uptrend | Exit/short | Long white, star, bearish third | Third closes into first | Third close or retest | Pattern high | Support | 1-3 bars | Incomplete or no prior rise | OHLCV |
| Morning/evening doji star | Mature trend | Both | Doji star after trend | Strong third-candle confirmation | Confirmation | Pattern extreme | Structural | 1-2 bars | Next candle negates | OHLCV |
| Shooting star | Advance | Exit/conditional short | Prior rise | Completed rejection; bearish confirm preferred | Confirm/retest | Above high | Support | Short | No rise | OHLCV |
| Inverted hammer | Decline | Long | Prior fall | Bullish next-candle confirmation | Confirmation | Below low | Resistance | Short | No confirmation | OHLCV |
| Harami / harami cross | Mature move | Warning | Large body then contained small body/doji | Range break or confluence | Conservative | Pattern extreme | Structural | Few bars | Range context without edge | OHLCV |
| Tweezers | Trend extreme | Both | Repeated high/low at structure | Rejection away | Confirmed close | Beyond shared extreme | Structural | Few bars | Tolerance too wide/no context | OHLCV, tick/ATR |
| Three black crows | Top/transition | Short/exit | Prior rise | Three lower strong closes | Third close only if not chased; retest preferred | Above pattern swing | Support | Immediate | Already oversold/extended | OHLCV |
| Three soldiers | Bottom/transition | Long | Prior decline/low area | Three higher strong closes | Third close or pullback | Below structure | Resistance | Immediate | Already extended into resistance | OHLCV |
| Rising three methods | Uptrend | Long continuation | Strong impulse, contained pause | Final close to new high | Completion/retest | Below pause | Structural | Until opposite break | Pause not contained | OHLCV |
| Falling three methods | Downtrend | Short continuation | Strong impulse, contained pause | Final close to new low | Completion/retest | Above pause | Structural | Until opposite break | Pause not contained | OHLCV |
| Spring + candle | Range/support | Long | False break below support | Close back above + bullish candle | Reclaim/retest | Below spring low | Range high/levels | Prompt | Acceptance below support | OHLCV, zones |
| Upthrust + candle | Range/resistance | Short | False break above resistance | Close back below + bearish candle | Reclaim/retest | Above high | Range low/levels | Prompt | Acceptance above resistance | OHLCV, zones |
| Polarity retest candle | Breakout | Both | Confirmed level break | Reversal candle at retest | Close/retest | Beyond zone | Next level | Retest window | Breakout not accepted | OHLCV, zones |
| Retracement + candle | Trend | Both | Clear impulse/trend | Reversal candle in 38-62% area | Close/break | Structural | Prior extreme/next level | Setup-dependent | No impulse/trend | OHLCV, swings |
| Window/tasuki | Session gap market | Both | Genuine high-low gap | Hold or partial fill | Context-specific | Beyond window | Structural | Until window closes | Continuous crypto/no gap | Session OHLCV |

---

# 23. Regime-to-strategy matrix

Legend: **E** enabled, **S** secondary, **P** prohibited.

| Strategy | Strong uptrend | Weak uptrend | Strong downtrend | Weak downtrend | Range | Compression | Expansion | Breakout | Failed breakout | Exhaustion | High volatility | Low liquidity | Conflicting HTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish pullback candle | E | E | P | S | S | S | S | E | S | S | S | P | S |
| Bearish pullback candle | P | S | E | E | S | S | S | E | S | S | S | P | S |
| Countertrend reversal candle | P | S | P | S | S | S | S | S | E | E | S | P | S |
| Rising/falling three methods | E | S | E | S | P | S | E | E | P | P | S | P | S |
| Spring/upthrust | P | S | P | S | E | E | S | P | E | E | E | P | S |
| Polarity retest candle | E | S | E | S | P | S | E | E | P | P | E | P | S |
| Doji warning | S | S | S | S | P | S | S | S | S | E | S | P | S |
| Three soldiers/crows | S | S | S | S | P | P | E | S | S | E | S | P | S |
| Gap/window pattern | S | S | S | S | P | S | E | E | S | E | S | P | S |
| Candle-only trade without confluence | P | P | P | P | P | P | P | P | P | P | P | P | P |

### Matrix interpretation

- Strong trend favors continuation and pullback entries in trend direction.
- Countertrend candles in strong trends are primarily exit/warning signals.
- Range enables spring/upthrust and boundary rejection, not midpoint candle trading.
- Compression favors monitoring; approval waits for expansion or failed break.
- Low liquidity broadly prohibits candle-based execution because wick/body geometry becomes unreliable.

---

# 24. Apex gap analysis

## 24.1 What Apex already does correctly

Based on the supplied project context:

- multi-timeframe analysis exists,
- explicit entry states exist,
- risk/leverage/liquidation are modeled,
- scanner categories are separated,
- deterministic and testable architecture is a priority,
- shared scan/analyze core is already a project goal,
- no-trade is an accepted outcome.

## 24.2 Incomplete

- candle pattern completion and closed-candle semantics,
- prior-trend/location eligibility,
- candle-as-warning versus candle-as-entry distinction,
- confluence clustering,
- classical gap versus crypto-adapted pattern handling,
- candle-specific invalidation and stop provenance,
- explicit pattern failure/negation,
- multi-timeframe anticipatory confirmation,
- target provenance independent of candles.

## 24.3 Incorrect or methodologically suspect

- treating an active candle as completed,
- using candle shape without prior trend,
- generating targets directly from a candle pattern,
- using a bearish reversal candle in a major uptrend as automatic short,
- calling a single price an entry “zone,”
- allowing weak R:R to remain actionable,
- fixed target percentages unrelated to structure,
- interpreting every reversal signal as immediate opposite trend.

## 24.4 Misleading mainly in wording

- `READY_NOW` before candle close,
- numeric “confidence” not statistically calibrated,
- “reversal” without saying it may only mean pause/lateral transition,
- “target” without target method,
- “confirmed” when only a wick/intrabar condition exists.

## 24.5 Remove

- candle-only trade approval,
- universal 10% candle target,
- forced short holding windows,
- gap pattern labels where no true gap exists,
- automatic opposite trade from reversal warning.

## 24.6 Add

- candle anatomy feature layer,
- contextual pattern detector,
- strict and variant definitions,
- completion/negation states,
- warning vs approval semantics,
- confluence evidence clustering,
- candle stop/invalidation references,
- gap applicability flag,
- pattern sample/calibration metadata.

## 24.7 Cannot be derived from this book

- statistical profitability of each pattern in crypto,
- optimal crypto thresholds,
- funding/liquidation-based rules,
- exact setup expiry bar counts,
- exchange-specific execution behavior,
- calibrated win probabilities,
- ideal leverage.

---

# 25. Deterministic rule candidates

| Rule candidate | Classification | Source |
|---|---|---|
| A hammer requires a prior decline | Directly supported | PDF pp.42-48 |
| Hanging man requires prior advance and bearish confirmation | Directly supported | PDF pp.43-52 |
| Engulfing second body must engulf first body, not necessarily shadows | Directly supported | PDF pp.52-53 |
| Pattern relevance increases after fast/protracted move | Directly supported concept; threshold requires validation | PDF p.53 |
| Dark-cloud penetration depth increases bearish significance | Directly supported | PDF pp.58-59 |
| Piercing candle should close beyond 50% of prior black body | Directly supported | PDF pp.63-64 |
| Morning/evening star requires third-candle completion | Directly supported | PDF pp.70-78 |
| Doji star requires next-session confirmation | Directly supported | PDF pp.78-80 |
| Doji in range is lower significance than doji after trend | Directly supported | PDF pp.163-178 |
| Reversal signal against major trend is exit warning, not new countertrend position | Directly supported | PDF p.42 |
| Candle patterns do not provide targets | Directly supported | PDF p.22 |
| Lower-timeframe completed candle may anticipate higher-timeframe close when trend aligned | Directly supported | PDF p.21 |
| Use ATR/tick tolerance for doji and equal highs/lows | Reasonable operational interpretation | Pattern definitions are flexible |
| Use ATR-normalized gap/penetration in crypto variants | Requires empirical validation | Crypto adaptation |
| Rising-three-method contained pause can be deterministic continuation setup | Directly supported geometry; thresholds need validation | PDF pp.149-157 |
| Candle plus support/resistance gets higher evidence score | Directly supported | Chapters 10-12 |
| Numeric confidence equals win probability | Requires calibration; not supported directly | Not provided |
| Rounded dumpling/fry-pan pattern fully automated | Too subjective to automate safely initially | PDF pp.127-132 |
| Elliott wave count automated as candle strategy | Too subjective without separate validated wave module | PDF pp.269-276 |
| Market-profile candle confluence automatic without profile-quality data | Requires specialized data/validation | PDF pp.277-282 |

---

# 26. Backtesting implications

## 26.1 Mandatory controls

1. Evaluate patterns only with data available at that timestamp.
2. Closed-candle patterns cannot enter before close unless explicitly testing lower-timeframe anticipation.
3. Record provisional patterns that disappear by close.
4. Use prior-trend calculations without future swing confirmation leakage.
5. Separate strict classical definitions from crypto variants.
6. Model entry type: close, next-bar break, retest, limit zone.
7. Model fees, slippage, funding, and liquidation.
8. Derive targets independently.
9. Log rejection reasons.
10. Segment by regime, timeframe, liquidity, and pattern location.

## 26.2 Required metrics

- pattern frequency,
- completion rate,
- provisional failure rate,
- confirmation rate,
- invalidation rate,
- expectancy,
- profit factor,
- max drawdown,
- MFE/MAE,
- time to target,
- time to stop,
- performance with/without confluence,
- strict versus variant definition performance,
- HTF-aligned versus countertrend performance,
- chase penalty,
- liquidity sensitivity,
- long/short asymmetry.

## 26.3 Test families

- candle geometry unit tests,
- prior-trend eligibility tests,
- closed/active candle state tests,
- crypto gap handling tests,
- confluence deduplication tests,
- target independence tests,
- scan/analyze parity tests,
- chronological integration tests,
- walk-forward calibration.

---

# 27. Implementation mapping to Apex

## Shared core

`apex scan` and `apex analyze SYMBOL` should call the same pipeline:

1. market data validation,
2. market context,
3. structural levels,
4. candle features,
5. pattern candidates,
6. setup eligibility,
7. strategy routing,
8. entry state,
9. stop/target geometry,
10. scoring and output.

Only symbol selection differs.

## Existing strategy/module mapping

| Book concept | Apex area | Likely focused change |
|---|---|---|
| Prior-trend requirement | Regime/structure | Expose trend context to pattern detector |
| Candle anatomy | Feature engine | Add normalized body/shadow/gap features |
| Reversal warning | Entry-state engine | Add warning state separate from trade approval |
| Continuation candles | Strategy candidates | Add rising/falling three-method candidates |
| Springs/upthrusts | Failed breakout/reclaim strategy | Add candle confirmation to existing structure logic |
| Confluence | Scoring | Deduplicate correlated evidence and score independent agreement |
| Closed-candle rule | Signal timing | Explicit confirmation basis per setup |
| Candle invalidation | Risk engine | Stop provenance from pattern extreme + structure |
| No candle targets | Target engine | Enforce target provenance outside candle layer |
| Multi-timeframe anticipation | MTF layer | Allow lower-TF confirmation under strict alignment rules |
| Volume/OI confirmation | Participation layer | Add pattern-specific volume/OI evidence |
| Crypto gap limitation | Data/pattern layer | Classical-vs-adapted applicability flags |

---

# 28. Final phased implementation plan

## Phase 1 - Shared market-context layer

Preserve architecture and standardize outputs for:

- trend and regime,
- swing structure,
- support/resistance,
- volatility,
- liquidity,
- MTF alignment,
- data quality.

Candlestick patterns consume this context but do not define it.

## Phase 2 - Setup eligibility

For every candle setup define:

- required prior trend,
- valid location,
- strict/variant geometry,
- confirmation requirement,
- gap applicability,
- prohibited regimes,
- required data.

## Phase 3 - Strategy routing

Route candles into existing strategy families:

- trend pullback,
- reversal warning,
- failed breakout/reclaim,
- breakout retest,
- continuation,
- range boundary.

Do not create dozens of isolated candle strategies unless testing proves value.

## Phase 4 - Entry logic

Add:

- candidate,
- provisional,
- pending close,
- confirmed,
- retest pending,
- missed,
- invalidated.

Define aggressive and conservative entries per setup.

## Phase 5 - Stop logic

Use pattern extreme only when it also represents meaningful invalidation. Add volatility and liquidation buffers. Record stop provenance.

## Phase 6 - Target logic

Enforce the rule that candle patterns cannot create targets. Use structural target candidates and reject poor R:R.

## Phase 7 - Timing and expiry

Derive horizon from:

- trigger timeframe,
- pattern duration,
- regime,
- volatility,
- structural target distance.

Calibrate expiry empirically.

## Phase 8 - Scoring and confidence

Score separately:

- geometry,
- context,
- completion,
- confluence,
- participation,
- MTF alignment,
- risk quality,
- data quality.

Use evidence labels until probability calibration exists.

## Phase 9 - Output wording

Clearly distinguish:

- warning,
- candidate,
- completed pattern,
- approved trade,
- exit signal,
- expected move,
- leveraged return.

Every output should state what confirms, what invalidates, and where stop/targets come from.

## Phase 10 - Backtesting and validation

Backtest strict classical patterns and crypto adaptations separately. Require chronological, cost-aware, liquidation-aware, regime-segmented validation before enabling any pattern in live/paper execution.

---

# 29. Evidence ledger - complete PDF coverage

## Front matter

- **PDF pp.1-4:** Title, subtitle, publication/copyright. Covered; no trading rules.
- **PDF pp.5-8:** Acknowledgements and source history. Covered.
- **PDF pp.9-10:** Preface; candlesticks as complementary technique and no omniscience claim. Covered.
- **PDF pp.11-14:** Complete table of contents. Covered.

## Chapter 1 - Introduction

- **PDF pp.15-18 / Book pp.1-4:** Research background and flexibility.
- **PDF pp.19-22 / Book pp.5-8:** Subjectivity, variable definitions, close requirement, limitations, no candle targets.
- **PDF pp.23-25 / Book pp.9-11:** Psychology, discipline, risk/reward, technical analysis rationale and notes.
- **PDF p.26:** Blank transition page.

## Chapter 2 - Historical background

- **PDF pp.27-31 / Book pp.13-17:** Japanese market history, Homma, rice futures, notes. Covered.
- **PDF pp.32-34:** Section artwork/Part One transition and blank page. Covered.

## Chapter 3 - Constructing candlesticks

- **PDF pp.35-40 / Book pp.21-26:** OHLC construction, bodies, shadows, spinning tops, doji, open/close significance. Covered including diagrams.

## Chapter 4 - Reversal patterns

- **PDF pp.41-42 / Book pp.27-28:** Reversal as trend-change warning and major-trend direction rule.
- **PDF pp.42-52 / Book pp.28-38:** Hammer and hanging man, confirmations and examples.
- **PDF pp.52-57 / Book pp.38-43:** Engulfing patterns, criteria, context and examples.
- **PDF pp.57-62 / Book pp.43-48:** Dark-cloud cover, penetration, resistance/volume confluence.
- **PDF pp.62-67 / Book pp.48-53:** Piercing pattern, on/in-neck and thrusting distinctions.
- **PDF p.68:** Blank transition.

## Chapter 5 - Stars

- **PDF pp.69-73 / Book pp.55-59:** Star concept and morning star.
- **PDF pp.73-78 / Book pp.59-64:** Evening star and strengthening factors.
- **PDF pp.78-83 / Book pp.64-69:** Doji stars and abandoned babies.
- **PDF pp.84-92 / Book pp.70-78:** Shooting star, inverted hammer, confirmation and examples.

## Chapter 6 - More reversal formations

- **PDF pp.93-102 / Book pp.79-88:** Harami and harami cross.
- **PDF pp.102-108 / Book pp.88-94:** Tweezers.
- **PDF pp.108-112 / Book pp.94-98:** Belt holds.
- **PDF pp.112-115 / Book pp.98-101:** Upside-gap two crows.
- **PDF pp.115-119 / Book pp.101-105:** Three black crows.
- **PDF pp.119-123 / Book pp.103-107:** Counterattack lines.
- **PDF pp.123-127 / Book pp.107-113:** Three mountains/rivers and number three.
- **PDF pp.127-132 / Book pp.113-118:** Dumpling/fry-pan and tower patterns.

## Chapter 7 - Continuation patterns

- **PDF pp.133-143 / Book pp.119-129:** Windows, support/resistance implications, three windows.
- **PDF pp.143-149 / Book pp.129-135:** Tasuki, gapping plays, side-by-side lines.
- **PDF pp.149-157 / Book pp.135-143:** Rising/falling three methods.
- **PDF pp.157-162 / Book pp.143-148:** Three soldiers, advance block, stalled pattern, separating lines.

## Chapter 8 - The magic doji

- **PDF pp.163-178 / Book pp.149-164:** Doji significance, tops, long white candle, long-legged/rickshaw, gravestone, doji levels, tri-star. Covered including diagrams and examples.

## Chapter 9 - Putting it all together

- **PDF pp.179-190 / Book pp.165-176:** Integrated chart exercises and pattern review. All examples reviewed as synthesis, not new standalone rules.

## Chapter 10 - Confluence

- **PDF pp.191-198 / Book pp.177-184:** Clusters of candle signals and zone significance.

## Chapter 11 - Candlesticks with trendlines

- **PDF pp.199-206 / Book pp.185-192:** Trendline support/resistance with candle confirmation.
- **PDF pp.207-215 / Book pp.193-201:** Springs and upthrusts.
- **PDF pp.215-223 / Book pp.201-208:** Polarity/change of role and protective stops.

## Chapter 12 - Retracement levels

- **PDF pp.223-230 / Book pp.209-214:** Candles at retracement areas and timing confluence.

## Chapter 13 - Moving averages

- **PDF pp.231-242 / Book pp.215-226:** SMA, WMA, EMA, MACD, use of averages, dual averages and candle timing.

## Chapter 14 - Oscillators

- **PDF pp.243-256 / Book pp.227-240:** Oscillator principles, RSI, stochastics, momentum, divergence and candle confirmation.

## Chapter 15 - Volume and open interest

- **PDF pp.257-268 / Book pp.241-252:** Volume, OBV, tick volume, open interest and candle combinations.

## Chapter 16 - Elliott Wave

- **PDF pp.269-276 / Book pp.253-258:** Wave basics and candlestick confirmation. Covered; wave counts treated as external/subjective structure.

## Chapter 17 - Market Profile

- **PDF pp.277-282 / Book pp.259-266:** Market Profile concepts with candle confirmation. Covered; implementation requires specialized profile data.

## Chapter 18 - Options

- **PDF pp.283-290 / Book pp.267-274:** Option basics and use of candles for underlying/timing. Covered; not central to Apex perpetual-futures strategy.

## Chapter 19 - Hedging

- **PDF pp.291-294 / Book pp.275-280:** Hedging applications. Covered; useful mainly as risk-context material.

## Chapter 20 - How the author used candlesticks

- **PDF pp.295-300 / Book pp.281-286:** Practical trade examples combining candles with context and risk. Covered.

## Conclusion and reference material

- **PDF pp.301-302 / Book pp.287-288:** Conclusion and limitations. Covered.
- **PDF pp.303-315 / Book pp.289-301:** Candlestick glossary and visual dictionary. Covered; used to cross-check definitions.
- **PDF pp.316-321 / Book pp.302-307:** Western technical glossary. Covered.
- **PDF pp.322-329:** Bibliography and index. Covered for source/coverage verification; no new trading rules.
- **Local PDF object p.330:** Trailing blank/technical page if exposed by local parser; no content.

---

# 30. Final coverage and ambiguity statement

### Fully covered

The full uploaded PDF was inspected from front matter through index, including:

- all chapters,
- pattern diagrams,
- chart examples,
- historical notes,
- footnotes/notes,
- glossaries,
- bibliography,
- index,
- and blank/transition pages.

### Readability

- The principal text and diagrams were readable.
- Some scanned chart labels and legacy market-price annotations are small or faint, but the pattern labels and methodological conclusions were readable.
- OCR contains occasional typographical artifacts, so page images and repeated definitions were used to resolve meaning.

### Ambiguities retained rather than silently resolved

- strict versus flexible pattern definitions,
- how close is “close enough” for doji/equal closes,
- what constitutes a high/low price area,
- how long a trend must be,
- whether gaps are mandatory in non-session markets,
- exact confirmation thresholds,
- exact oscillator/MA parameters,
- expiry timing.

These require explicit configuration and empirical validation in Apex rather than undocumented judgment.
