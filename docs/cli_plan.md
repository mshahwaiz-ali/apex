Apex CLI Final Implementation Plan

Samajh gaya, Boss. Sab useful commands public rahengi because this is your personal tool. Lekin CLI sirf un capabilities ko expose karegi jo backend mein genuinely implemented aur usable hain.

Final scope sirf ye hai:

public command organization;
scan/analyze output;
backtest;
research campaign;
configuration/version;
obsolete persistence options cleanup;
help, errors, JSON, and tests.

No future execution, paper trading, account management, or unrelated features will enter this plan.

1. Verified current capabilities
apex scan

Backend currently:

Binance futures universe obtains karta hai;
symbols screen aur shortlist karta hai;
each symbol ko canonical shared analysis engine se analyze karta hai;
methodology gate apply karta hai;
opportunity portfolio produce karta hai;
scan results rank aur serialize karta hai;
per-symbol failures isolate karta hai.

Scan and analyze both pass the same core settings, including methodology_gate_mode.

Decision: Keep public and make it the primary command.

apex analyze SYMBOL

Backend currently:

one symbol ka full multi-timeframe context builds karta hai;
strategies run karta hai;
methodology candidate routing apply karta hai;
market environment and state derive karta hai;
candidate ranking performs karta hai;
canonical opportunity portfolio builds karta hai;
current, nearby, follow-up, and developing opportunities preserve kar sakta hai.

The serialized payload already includes the complete opportunity_portfolio, although the normal text renderer still shows mainly one compatibility setup.

Decision: Keep public and replace single-setup rendering with portfolio rendering.

apex backtest SYMBOL

The backend is real and sufficiently developed to keep.

It currently:

downloads/fetches historical closed candles;
creates multiple chronological decision points;
runs analyze_selected_symbol() at each historical point;
prevents future candle access through a replay provider;
turns selected setups into replay signals;
records no-trade decisions;
models funding;
executes historical trades;
calculates trade outcomes;
records MFE and MAE;
calculates metrics;
divides results into training, validation, and final-test partitions;
calculates overfitting-related statistics;
keeps dataset/config/code fingerprints.
Current issue

Its text output only shows a high-level summary:

trades;
win rate;
expectancy;
net P&L;
profit factor;
average win/loss;
drawdown;
robustness checks.

It does not show the full trade-by-trade replay record currently available in its payload.

Another important issue: the backtest historical call currently does not visibly forward methodology_gate_mode, while live scan/analyze do. It also reads analysis.assessment.setup, the legacy single selected setup, rather than evaluating the canonical retained portfolio.

Decision: Keep public, but fix canonical parity before calling its results authoritative.

Research campaign

The current backtest --campaign backend is also real. It can:

define a historical UTC month range;
use or construct a point-in-time symbol universe;
download missing Binance public datasets;
verify available and missing files;
build a campaign manifest;
optionally train models;
output campaign artifacts.

The current text renderer already has a distinct “Historical Research Campaign” report.

Decision: Split it into a dedicated public command:

apex research campaign

This is cleaner than mixing two unrelated workflows under:

apex backtest --campaign
2. Final public command tree
apex
├── scan
├── analyze
├── backtest
├── research
│   └── campaign
├── config-check
└── version

All commands will remain visible.

Help panels
Trading
  scan
  analyze

Evaluation
  backtest

Research
  research campaign

System
  config-check
  version

No useful command will be hidden merely because this is a personal application.

3. Persistence options decision
Current --record

--record writes every serialized scan or analysis result into an append-only JSONL file.

Its record includes:

stable analysis ID;
recorded timestamp;
source type;
subject/symbol;
configuration ID;
methodology version;
content hash;
complete serialized payload.
Assessment

It is a legacy/manual persistence route. It duplicates much of what the SQLite database does, but with weaker querying and no automatic outcome reconciliation.

Decision

Remove --record from scan and analyze.

Keep write_analysis_record() temporarily only if tests or internal migration code still use it. If source inspection confirms no remaining consumer after CLI removal, remove that function and its exports in the same cleanup batch.

Current --record-db

--record-db is significantly more useful.

It stores:

full analysis records;
registered opportunities;
direction;
entry region;
preferred entry;
stop;
targets;
waiting/filled/resolved state;
outcome;
fill time;
MFE;
MAE.

On later analyses, Apex reconciles previously pending opportunities against subsequent closed candles.

The CLI already automatically uses:

data/reports/analysis.db

when outcome_tracking_enabled is true.

Assessment

This is not useless. It is the backend foundation for:

outcome tracking;
historical calibration;
MFE/MAE evaluation;
checking whether previous Apex setups worked;
comparing future scans against past opportunities.
Decision
Keep automatic SQLite outcome tracking.
Remove manual --record-db from the normal CLI.
Configure its path through YAML only.
Keep persistence invisible during normal use.
Show a concise status under --explain, for example:
Outcome tracking: enabled
Database: data/reports/analysis.db
Required fix

The opportunity registration code currently iterates only:

setup
developing_setup

rather than every canonical portfolio opportunity.

It must be migrated to register all retained portfolio opportunities, otherwise outcome tracking remains partially legacy.

Current scan --report

The hidden scan --report writes the complete scan payload as formatted JSON to a file. The backend function is only a basic JSON writer.

This can already be achieved with:

apex scan --output json > scan.json
Decision

Remove scan --report.

It is redundant with JSON output and adds another output path to maintain.

Backtest --report

Backtest report output is different: a large historical study may need to be saved for inspection.

Decision

Keep it but rename consistently:

--report-file PATH

It should save the complete backtest payload, including:

configuration;
decisions;
no-trade records;
signals;
trades;
metrics;
partitions;
robustness statistics;
fingerprints.

Research campaign should use the same option name:

--report-file PATH
4. Locked output rule: every analyzed symbol gets a Setup Plan

“Setup must be present” will mean:

Every visible symbol must have a concrete operator plan, but Apex must not invent invalid trade geometry.

There will be four valid outcomes.

A. Executable setup

Includes:

direction;
strategy;
CMP;
entry zone;
preferred entry;
maximum chase;
stop;
TP1–TP3;
percentage movement;
RR;
risks.
B. Nearby or confirmation setup

Includes:

intended direction;
strategy;
entry region;
distance from CMP;
activation condition;
invalidation;
stop;
targets;
expiry.
C. Developing/follow-up setup

Includes:

expected setup type;
direction;
required market event;
intended area;
activation;
invalidation;
expiry;
do-not-enter condition.
D. No structurally valid setup yet

Still produces a Setup Plan, but without fabricated entry/TP values:

Setup Plan
Status          No valid setup yet
Current state   Mid-range / conflicting structure
Long trigger    Reclaim 118,900 and hold retest
Short trigger   Lose 117,600 and reject retest
Invalid while   Price remains inside the current range
Main risk       No clear target room

This satisfies the requirement that output should never be empty or useless while preserving “do not force trades.”

5. apex scan final design
Purpose
Discover liquid Binance USDT perpetual markets, shortlist viable symbols,
and run the shared multi-timeframe opportunity engine.
Options
--results INTEGER
--shortlist INTEGER
--direction [long|short|both]
--candles INTEGER
--explain
--output [text|json]
--symbols-file PATH
--config-dir PATH

Removed:

--record
--record-db
--report
Normal output structure
Apex Market Scan

Scan Summary

Enter at CMP

Confirmation Entry

Nearby Entry

Developing / Follow-up

No Current Trade — Setup Plans
Scan summary
Markets discovered
Markets screened
Symbols shortlisted
Symbols analyzed
Symbols failed
Opportunities retained
Opportunities displayed
Executable now
Confirmation entries
Nearby entries
Developing/follow-up
No current trade
Direction filter
Methodology gate

Counts must distinguish symbols and opportunities.

Opportunity card
BTCUSDT — ENTER LONG

Action          Enter now
Strategy        Breakout retest
State           Execute now
Methodology     Allowed
CMP             118,420
Entry zone      118,250–118,500
Preferred       118,340
Entry distance  -0.07%
Maximum chase   118,680
Stop            117,760 (-0.49%)
TP1             119,180 (+0.71%, 1.45R)
TP2             120,050 (+1.44%, 2.95R)
TP3             121,400 (+2.59%, 5.29R)
Quality         Setup 82 · Execution 78 · Target 74
Main risk       1h resistance above TP2
Developing card
ETHUSDT — DEVELOPING SHORT

Strategy        Failed breakout reversal
CMP             3,840
Expected area   3,885–3,910
Distance        +1.43%
Activation      Sweep above 3,900 then 3m close below 3,885
Invalidation    3m acceptance above 3,925
Expiry          Cancel after range structure changes
Do not enter    Before rejection is confirmed
6. apex analyze SYMBOL final design
Purpose
Run the same shared multi-timeframe analysis used by scan for one symbol.
Show every retained current, nearby, follow-up, or developing opportunity.
Normal structure
Apex Analysis — BTCUSDT

Market Snapshot

Best Current Opportunity

Alternative Current Opportunity

Nearby Opportunity

Follow-up Opportunity

Developing Opportunity

Market Context

Risk and Invalidation

Only empty optional sections disappear.

Important implementation rule

The renderer must consume:

opportunity_portfolio

directly.

It must stop treating:

setup
developing_setup

as the full public truth.

Those compatibility fields can remain in JSON temporarily, but normal text output must show every retained canonical opportunity.

7. --explain final structure

The normal Setup Plan remains first.

Then explain mode appends:

Methodology Enforcement
Opportunity Portfolio
Multi-Timeframe Evidence
Entry and Chase Rationale
Stop Rationale
Target Rationale
Supporting Evidence
Contradictions
Missing Evidence
Collision and Sequence
Rejected and Suppressed Candidates
Data Quality
Outcome-Tracking Status
Historical Calibration
Methodology section
Gate mode             Enforce
Candidates evaluated  8
Allowed                3
Deferred               2
Suppressed             1
Unavailable            2

Each displayed opportunity should show its own verdict.

Explain truncation

Text may remain readable, but it must state when not everything is displayed:

Showing 8 of 21 rejected candidates.
Use --output json for the complete structured record.
8. apex backtest SYMBOL final design
First backend correction

Before redesigning output:

pass methodology_gate_mode exactly as live scan/analyze do;
use the canonical opportunity portfolio;
define which opportunity roles are eligible for simulated execution;
do not blindly use only analysis.assessment.setup;
preserve no-trade and developing decisions accurately;
include fees, slippage, and funding assumptions clearly;
avoid future leakage;
preserve chronological decision points.
Proposed command
apex backtest SYMBOL [OPTIONS]

Options:

--candles INTEGER
--replay-timeframe TIMEFRAME
--replay-candles INTEGER
--decision-points INTEGER
--funding-pct FLOAT
--report-file PATH
--explain
--output [text|json]
--config-dir PATH

Remove campaign-specific options from this command:

--campaign
--start
--end
--symbols-file
--dataset-dir
--download-missing
--train-model

These move under research campaign.

Backtest normal output
Apex Backtest — BTCUSDT

Test Configuration

Performance Summary

Outcome Distribution

Risk and Excursion

Partition Performance

Trade Record

No-Trade Decisions

Robustness
Test configuration
Symbol
Historical period
Replay timeframe
Analysis timeframes
Decision points
Holding window
Methodology gate
Fee model
Slippage model
Funding model
Dataset fingerprint
Configuration fingerprint
Code fingerprint
Performance summary
Decision points
Signals generated
Trades executed
No-trade decisions
Wins
Losses
Breakeven
Win rate
Expectancy
Net P&L
Profit factor
Average win
Average loss
Average R
Maximum drawdown
Risk and excursion
Average MFE
Average MAE
Best MFE
Worst MAE
TP1 hit rate
TP2 hit rate
TP3 hit rate
Stop rate
Missed-entry count
Expired-setup count

Fields that the current backend does not yet aggregate will be derived strictly from existing trade records. No metric will be fabricated.

Partition performance
Training
Validation
Final test

For each:

trades
win rate
expectancy
profit factor
drawdown
Full trade record

Every simulated trade:

Trade 1 — BTCUSDT LONG

Decision time    2026-06-01 12:00 UTC
Strategy         Breakout retest
Entry state      Execute now
Methodology      Allowed
Entry            104,250
Stop             103,600
TP1              105,200
TP2              106,150
TP3              107,800
Outcome           TP2 then exit
Realized R        +2.10R
Net P&L           +...
MFE               +2.76R
MAE               -0.31R
Partition         Final test

Normal output may show all trades because this is your personal CLI. For very large studies:

--output json

and --report-file preserve the complete record.

No-trade decisions

Show decision time and concise primary reason:

2026-06-01 14:00 UTC — No target room
2026-06-01 16:00 UTC — Entry already missed

Under --explain, include detailed diagnostics.

9. apex research campaign final design
Command
apex research campaign [OPTIONS]

Options:

--start YYYY-MM
--end YYYY-MM
--symbols-file PATH
--dataset-dir PATH
--download-missing
--train-model
--report-file PATH
--output [text|json]
--config-dir PATH
Output
Apex Historical Research Campaign

Campaign Configuration

Dataset Coverage

Universe Summary

Missing Data

Manifest

Model Training

Artifacts

This command does not claim strategy profitability. It prepares and verifies research data and optionally trains models.

10. Help and errors
Root help
Apex discovers, analyzes, and evaluates Binance USDT perpetual-futures opportunities.

Use `apex scan` to discover markets.
Use `apex analyze SYMBOL` for one market.
Use `apex backtest SYMBOL` to replay historical decisions.
Consistent errors

Create one shared CLI error mapper for:

invalid symbol;
unavailable market;
Binance timeout;
rate limit;
network failure;
stale required candles;
missing configuration;
invalid output mode;
invalid direction;
invalid limits;
incomplete historical data.

Per-symbol scan failures should appear in a compact failures section rather than silently disappearing.

11. Exact implementation batches
Batch 1 — Command and persistence cleanup
Changes
remove scan/analyze --record;
remove scan/analyze --record-db;
remove scan --report;
retain automatic SQLite outcome tracking;
rename backtest --report to --report-file;
add research Typer group;
move campaign behavior to research campaign;
keep all commands visible;
rewrite root and command help.
Likely files
src/apex/cli.py
src/apex/cli_app.py
src/apex/cli_help.py
src/apex/cli_navigation.py
src/apex/cli_commands/__init__.py
src/apex/cli_commands/analysis.py
src/apex/cli_commands/scanner.py
src/apex/cli_commands/backtesting.py
src/apex/cli_commands/research.py
Batch 2 — Canonical CLI serialization contract
Changes
explicit opportunity category;
explicit methodology verdict;
explicit sequence role;
complete portfolio serialization;
symbol/opportunity count separation;
Setup Plan representation for no-valid-setup;
remove renderer dependence on strategy-name heuristics.
Likely files
src/apex/application/enriched_public_output.py
src/apex/application/discovery_analysis.py
src/apex/application/decision_analysis.py
src/apex/application/opportunity_portfolio.py
src/apex/presentation/cli_information_architecture.py
src/apex/presentation/scan_groups.py
Batch 3 — Analyze portfolio renderer
Changes
market snapshot;
all current opportunities;
nearby opportunity;
follow-up opportunity;
developing opportunity;
mandatory Setup Plan;
market context;
risk and invalidation;
concise normal output.
Likely files
src/apex/presentation/operator_output.py
src/apex/presentation/methodology_selected_entry_output.py
Batch 4 — Scan renderer
Changes
accurate summary counts;
correct group ordering;
complete cards;
CMP distance;
maximum chase;
stop percentage;
TP percentages;
RR;
quality dimensions;
methodology verdict;
no-current-trade Setup Plans;
explicit truncation count;
scan failures section.
Batch 5 — Explain mode
Changes
methodology enforcement;
full portfolio map;
rationale;
evidence;
contradictions;
missing evidence;
collisions;
sequence;
rejected/suppressed candidates;
data diagnostics;
outcome database status;
calibration honesty.
Batch 6 — Outcome tracking canonicalization
Changes
register every retained portfolio opportunity in SQLite;
stop registering only legacy setup/developing_setup;
preserve stable opportunity IDs;
reconcile each opportunity independently;
ensure scan and analyze records do not duplicate improperly;
add outcome metadata required by backtest/calibration.
Likely files
src/apex/application/analysis_records.py
src/apex/application/methodology_analysis_records.py
src/apex/application/enriched_public_output.py
Batch 7 — Backtest canonical alignment
Changes
forward methodology_gate_mode;
use canonical opportunity portfolio;
define simulation eligibility by actionability;
model developing/missed/expired plans correctly;
preserve chronological behavior;
verify costs and funding;
produce complete trade records;
aggregate TP, stop, MFE, MAE, and partition metrics.
Likely files
src/apex/cli_commands/backtesting.py
src/apex/backtesting/discovery_signal.py
src/apex/backtesting/engine.py
src/apex/backtesting/contracts.py
src/apex/presentation/backtest_output.py
Batch 8 — Research campaign renderer and documentation
Changes
final research campaign help;
dataset coverage output;
manifest output;
missing-file output;
model-training status;
report-file behavior;
README CLI reference.
12. Required tests
Command tree
apex --help
apex scan --help
apex analyze --help
apex backtest --help
apex research --help
apex research campaign --help
apex config-check --help
apex version --help
Removed options

Tests must confirm these are no longer accepted:

scan --record
scan --record-db
scan --report
analyze --record
analyze --record-db
Scan/analyze
same canonical opportunity serialized consistently;
all portfolio opportunities remain visible;
nearby setup survives current setup;
follow-up setup survives current setup;
no current trade still produces Setup Plan;
no fabricated geometry;
direction only filters display;
explain adds diagnostics without changing decisions.
Outcome database
all portfolio opportunities registered;
same opportunity is not duplicated;
pending setup reconciliation;
filled setup reconciliation;
MFE/MAE update;
expired setup resolution.
Backtest
methodology gate parity;
no future leakage;
chronological decisions;
portfolio opportunity eligibility;
fees/funding handling;
full trade output;
no-trade record output;
partition metrics;
JSON/text consistency.
13. Final locked decisions
Item	Decision
scan	Public
analyze	Public
backtest	Public and expanded
research campaign	Public dedicated command
config-check	Public
version	Public
--record	Remove
manual --record-db	Remove
automatic SQLite outcome tracking	Keep and fix
scan --report	Remove
backtest/research report file	Keep as --report-file
setup in every output	Mandatory Setup Plan
fake trade geometry	Never
normal output	Compact but complete
--explain	Detailed diagnostics
JSON	Complete structured authority
strategy changes	Out of scope