# Phase D Scoring, Entry, And Lifecycle Slice

This note records the first Phase D hardening slice.

## Added

- Entry zones now expose:
  - `max_chase_price`
  - `expires_after_seconds`
- Trade candidates now get a deterministic default lifecycle with:
  - active status
  - cooldown key
  - expiry seconds
  - invalidation price and reason
- Scoring configuration now exposes a stable SHA-256 fingerprint for
  reproducible reports.
- Phase 5 result metadata now includes:
  - `config_hash`
  - duplicate thesis cluster count
  - decision regime
  - eligible and skipped strategy counts

## Compatibility

- Existing strategy constructors remain compatible because lifecycle and entry
  additions have defaults.
- Existing Phase 5 result contracts keep `configuration_id`; `config_hash` is
  additive metadata.

## Coverage

- Entry tests cover chase-price and expiry output.
- Strategy contract tests cover lifecycle defaults and invalidated lifecycle
  validation.
- Phase 5 tests cover config hash stability and duplicate-cluster metadata.
