# Apex Trading Agent — Final Redesign Report

## Status

The Final Simplification and Redesign was executed through 15 ordered steps.

The implementation now represents a futures-first Binance opportunity scanner and wallet-aware trade planner rather than a development roadmap, evidence ceremony, autonomous-learning system, or execution platform.

This report summarizes the resulting product and the work completed. The authoritative design specification remains `docs/new_plan.md`.

---

## Final Product

Apex now focuses on:

- dynamically discovering eligible Binance USDT perpetual contracts;
- screening the market before expensive analysis;
- finding actionable long and short opportunities near current price;
- evaluating relevant strategies from measurable market state;
- ranking candidates with separate opportunity, setup, timing, risk, and final scores;
- producing immediate and preferred entries;
- building Standard and Funded wallet plans;
- retaining deterministic backtesting, paper outcomes, and manual diagnostics;
- presenting analysis through text and JSON.

The active product does not place exchange orders and does not guarantee profitability.

---

## Completed Redesign Steps

### 1. Repository inventory

Mapped legacy modes, risk profiles, spot registrations, command surfaces, development-era terminology, presentation layers, optimization systems, configuration consumers, and persisted-schema dependencies.

### 2. Baseline lock

Recorded the existing command surface, scan payloads, futures behavior, test baseline, configuration files, and retained core modules before redesign changes.

### 3. Gainer-system removal

Removed separate gainer identity, routing, state, thresholds, duplicate analysis, serialization, commands, tests, and documentation.

Top movers are now represented as measurable opportunity features instead of a separate product mode.

### 4. Risk-profile simplification

Reduced the user-facing risk model to:

```text
STANDARD
FUNDED
```

Separated opportunity discovery from wallet feasibility and retained transparent risk failures without hiding valid market opportunities.

### 5. Spot freeze

Removed spot from the default command and documentation surface while preserving implementation required for potential later reuse through shared architecture.

### 6. Dynamic futures universe

Implemented current Binance contract discovery, eligibility filtering, metadata handling, blacklist support, precision validation, and optional static overrides.

### 7. Lightweight market screener

Added market-wide inexpensive screening, opportunity scoring, shortlist selection, and explainable selection reasons before deep analysis.

### 8. Detailed strategy analysis

Reworked detailed analysis around measurable market states, strategy applicability, multiple candidates per symbol, normalized evidence, and mode-independent routing.

### 9. Entry redesign

Introduced action-oriented statuses, immediate and preferred entries, chase boundaries, structural invalidation, warning-based sweep handling, and fewer wait-only outcomes.

### 10. Scoring and ranking

Separated:

```text
opportunity_score
setup_score
timing_score
risk_feasibility_score
final_rank_score
```

Updated ranking so opportunity quality remains visible even when sizing or timing is imperfect.

### 11. Presentation simplification

Retained active text and JSON output while removing redundant selectors and presentation-only compatibility layers.

### 12. Terminology cleanup

Removed development-stage labels, milestone terminology, obsolete field names, legacy headings, and roadmap-era identifiers from active code and output.

### 13. Logging and paper simplification

Retained:

- scan and analysis records;
- paper trades and outcomes;
- scheduler and lifecycle status;
- daily validation and history;
- forward-edge evaluation;
- funded readiness and planning;
- manual diagnostics.

Removed autonomous learning, automatic promotion, and unnecessary evidence ceremony.

### 14. Confirmed dead-code deletion

Deleted orphan CLI layers, obsolete artifact and verifier modules, dedicated dead tests, stale exports, duplicate registrations, and unused compatibility code only after reference inventories.

The final Step 14 inventory reported no stale exports in the inspected funded, paper, validation, and application packages.

The validated Step 14 code baseline reported:

```text
Ruff: passed
mypy: passed across 352 source files
pytest: 1533 passed
git diff --check: clean
```

### 15. Documentation closure

Removed obsolete archived documentation, rewrote the root README for the current product and command surface, and added this final redesign report.

The Step 15 documentation batch must still be validated locally before commit.

---

## Retained Product Inventory

### Core market analysis

- Binance provider integration;
- exchange metadata and contract discovery;
- candle normalization;
- ticker and order-book support;
- lightweight opportunity screening;
- multi-timeframe features;
- structure and liquidity analysis;
- market-state classification;
- strategy applicability;
- candidate scoring and ranking;
- immediate and preferred entry geometry;
- stop and target construction.

### Risk and funded planning

- Standard and Funded profiles;
- structural-stop-first position sizing;
- fee and slippage allowances;
- isolated-margin planning;
- leverage selection;
- liquidation estimation;
- funded limits and provider policies;
- funded plan generation, reporting, schema, package audit, and reproduction tooling.

### Research and paper tracking

- chronological backtesting;
- reproducible campaigns;
- historical comparisons;
- scan and analysis logs;
- paper trade persistence;
- paper lifecycle and scheduler;
- paper outcomes;
- lifecycle and health diagnostics;
- forward-edge and historical validation;
- manual review visibility.

### Active interfaces

- futures commands;
- paper commands;
- research commands;
- validation commands;
- system and configuration checks;
- text output;
- JSON output.

---

## Removed or Hidden Systems

- gainer scanner and routing;
- normal-versus-gainer duplicate analysis;
- aggressive and extreme risk profiles;
- active spot interface;
- testnet and exchange execution surfaces;
- autonomous optimization and threshold mutation;
- automatic strategy promotion;
- evidence-oriented CLI ceremony;
- artifact source-verification ceremony;
- roadmap and milestone terminology;
- duplicate command registrations;
- obsolete presentation and compatibility layers;
- confirmed orphan modules and tests;
- archived development documentation.

---

## Operating Principle

The final workflow is:

```text
Discover
→ screen
→ analyze
→ evaluate strategies
→ score and rank
→ construct entries
→ report cautions
→ calculate wallet plan
→ log the result
```

Risk planning no longer suppresses discovery.

Warnings no longer automatically cancel otherwise valid opportunities.

A candidate becomes invalid only when data, structure, geometry, liquidity, or exchange constraints make the thesis or order genuinely unusable.

---

## Quality Standard

Every implementation batch follows:

```bash
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests --fix
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests
git diff --check
git status --short
```

Validation is considered complete only from actual terminal output.

---

## Final Outcome

Apex is now designed as:

> A practical, aggressive but controlled Binance futures opportunity scanner and trade planner—not a reporting platform, not a roadmap archive, not an autonomous-learning system, and not a trade-rejection machine.
