# Verified Funded-Provider Limits

## Purpose

R1 funded-account readiness must use current provider rules rather than generic or remembered values.

Apex therefore stores provider rules in a schema-versioned registry. Each provider and challenge-phase preset records:

- normalized provider ID;
- provider display name;
- challenge phase;
- external verification date;
- source reference;
- drawdown model;
- external daily and total drawdown limits;
- maximum trades per day;
- weekend, overnight, and news permissions;
- verification status;
- deterministic preset SHA-256.

The registry contains operator-supplied evidence. Apex does not scrape, infer, or fabricate provider rules.

## Registry example

```yaml
schema_version: 1
maximum_verification_age_days: 30
presets:
  - provider_id: EXAMPLE
    provider_name: Example Funded
    challenge_phase: PHASE_1
    verified_on: "2026-07-01"
    source_reference: https://provider.example/rules
    drawdown_model: STATIC
    external_daily_drawdown_limit_pct: 5.0
    external_total_drawdown_limit_pct: 10.0
    maximum_trades_per_day: 3
    weekend_trading_allowed: false
    overnight_holding_allowed: true
    news_trading_allowed: false
    limits_verified: true
```

Supported drawdown models:

```text
STATIC
TRAILING
END_OF_DAY_TRAILING
```

## Normalize and verify the registry

```bash
apex funded-provider-registry-normalize \
  --registry config/funded_provider_limits.yaml \
  --output data/funded_provider_limits.json
```

The command:

- validates every preset;
- rejects duplicate provider/phase identities;
- verifies any stored preset hash;
- writes deterministic normalized JSON;
- reloads and revalidates the completed output;
- rejects an existing output unless `--force` is supplied.

## Account-policy compatibility

The selected account policy must be `FUNDED` and must not contradict the provider preset.

Apex rejects preparation when:

- provider names differ;
- challenge phases differ;
- an attached preset SHA-256 differs;
- daily or total external drawdown limits differ;
- the account policy permits more daily trades than the provider;
- the account policy permits weekend trading when the provider forbids it;
- the account policy permits overnight holding when the provider forbids it;
- the account policy permits news-event trading when the provider forbids it.

Internal risk limits may remain stricter than provider limits.

## Provider-policy binding

`funded-provider-prepare` emits a typed, path-independent `provider_policy_binding` snapshot. It records:

- provider ID and display name;
- challenge phase;
- deterministic preset SHA-256;
- provider verification date;
- drawdown model;
- weekend, overnight, and news permissions;
- compatibility status and stable reasons;
- `execution_authorized: false`.

Both funded-readiness review paths consume this binding. An otherwise approved account-policy decision cannot become funded-ready when the binding is missing, incompatible, stale, authorizing, or inconsistent with the canonical provider name and verification date.

Stable readiness blockers include:

```text
PROVIDER_POLICY_BINDING_REQUIRED
PROVIDER_POLICY_MISMATCH
PROVIDER_LIMITS_STALE
```

## Prepare a funded-readiness input

Start from an R1 input template containing the operator-reviewed fields such as account policy decision, lockout checks, checklists, kill-switch state, and risk mode.

```bash
apex funded-provider-prepare \
  --registry data/funded_provider_limits.json \
  --provider-id EXAMPLE \
  --challenge-phase PHASE_1 \
  --as-of 2026-07-16 \
  --account-policies config/account_policies.yaml \
  --policy FUNDED_EXAMPLE \
  --template data/reports/funded-readiness-template.json \
  --output data/reports/funded-readiness-input.json
```

The command requires a fresh, verified preset. A verification date is rejected when it is:

- later than `--as-of`;
- older than `maximum_verification_age_days`;
- marked unverified.

The prepared input contains canonical `provider_limits`, `provider_verification`, and `provider_policy_binding` blocks. The selected provider identity, challenge phase, permissions, verification date, and preset SHA-256 remain attached to the subsequent review decision.

## Follow-on review

The prepared file can be used with either readiness path:

```bash
apex funded-readiness-review \
  data/reports/funded-readiness-input.json \
  --report data/reports/funded-readiness-report.json \
  --output json
```

or:

```bash
apex funded-readiness-from-history \
  data/reports/funded-readiness-input.json \
  --history-review data/reports/p1-history-review.json \
  --report data/reports/funded-history-readiness-report.json \
  --output json
```

The resulting evidence can then be sealed using the existing funded-readiness artifact commands.

## Safety boundary

Registry validation, provider-policy binding, and readiness-input preparation do not authorize trading.

Every prepared input and provider-policy binding contains:

```json
{
  "execution_authorized": false
}
```

A valid provider preset, compatible binding, or a `ready: true` review does not authorize:

- autonomous order placement;
- funded-account execution;
- production trading;
- real-money execution;
- bypassing provider rules;
- bypassing manual pre-trade and post-trade review.
