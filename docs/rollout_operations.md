# Apex Controlled Rollout Operations

## Purpose

This runbook covers non-authoritative rollout diagnostics for the shared
multi-opportunity analysis model.

It does not authorize strategy tuning, live execution changes, or removal of
legacy compatibility paths.

## Safety properties

Rollout diagnostics:

- are disabled by default;
- do not alter opportunity generation;
- do not alter selection, ranking, scoring, actionability, or execution;
- use the same configuration switch for `scan` and `analyze`;
- remain explicitly marked `authoritative: false`;
- do not change command exit status based on diagnostic acceptance.

## Configuration

Default:

```yaml
rollout_diagnostics_enabled: false
```

Enable temporarily in the selected configuration directory:

```yaml
rollout_diagnostics_enabled: true
```

Do not leave diagnostics enabled unintentionally in a production profile.

## Generate an analyze report

```bash
apex analyze BTCUSDT   --output json   --rollout-report data/reports/rollout/analyze-btcusdt.json
```

The normal command output remains separate from the rollout artifact.

The report contains:

- schema version;
- command identity;
- non-authoritative interpretation;
- symbol comparison details.

## Generate a scan report

```bash
apex scan   --output json   --rollout-report data/reports/rollout/scan.json
```

The scan report contains:

- aggregate comparison summary;
- displayed per-symbol comparisons;
- acceptance result;
- compatibility-only and structural-regression counts.

## Acceptance interpretation

Diagnostic acceptance requires:

```text
regression_count == 0
```

Accepted:

- exact matches;
- documented compatibility-only differences.

Not accepted:

- strategy changes;
- direction changes;
- entry-zone changes;
- stop changes;
- target changes;
- rejection-reason changes;
- unexpected opportunity-count changes;
- any mixed report containing a structural difference.

Acceptance is evidence for review only. It is not a trading signal and does not
activate new output automatically.

## Required evidence bundle

Record the following before any authoritative rollout decision:

1. Commit SHA.
2. Configuration file and diagnostics-switch value.
3. Fixed fixture or symbol set.
4. Analyze rollout report.
5. Scan rollout report.
6. Difference counts by field.
7. Structural regression count.
8. Ruff output.
9. Mypy output.
10. Focused pytest output.
11. `git diff --check` output.
12. Reviewer decision and rationale.

## Immediate rollback

Set:

```yaml
rollout_diagnostics_enabled: false
```

Then rerun the affected command and confirm:

- rollout comparison fields are absent;
- no rollout report is written unless explicitly requested;
- normal output matches the pre-diagnostic contract.

## Rollback triggers

Rollback or stop rollout review when:

- any structural regression is unexplained;
- report generation changes normal output;
- scan and analyze use different switches or comparison rules;
- diagnostics affect ranking, scoring, actionability, or execution;
- output fields are presented as calibrated reliability without evidence;
- a compatibility difference hides geometry or strategy changes;
- validation evidence is incomplete.

## Compatibility-removal prerequisites

Do not delete the compatibility adapter or legacy single-winner path until all
of the following are true:

- fixed-fixture diagnostic acceptance is clean;
- representative scan and analyze reports are reviewed;
- normal disabled-mode output remains stable;
- migration documentation exists;
- rollback procedure is tested;
- README and command help are updated;
- deprecated configuration has a documented replacement;
- the removal is isolated from strategy and threshold changes.

## Cleanup sequence

1. Freeze a comparison fixture set.
2. Capture accepted rollout reports.
3. Update README and command help.
4. Document state and field semantics.
5. Remove dead compatibility code in a focused commit.
6. Run full validation.
7. Verify scan and analyze still use the shared core.
8. Retain a release note describing rollback and migration.

## Batch 12 cleanup-readiness audit

The final Batch 12 audit verifies that:

- diagnostics remain disabled by default;
- legacy public-output serializers remain available;
- enriched serializers remain opt-in;
- operator reports refuse payloads without diagnostics;
- acceptance remains non-authoritative and does not define an exit code;
- scan and analyze use explicit serialization helpers;
- scan-generated analysis records use the same diagnostics switch;
- rollout exports are available through the application facade;
- cleanup blockers remain documented.

Passing this audit means the controlled-rollout controls are complete. It does
not authorize compatibility removal. Compatibility deletion remains a separate
future change requiring approved evidence and an independently revertible
commit.
