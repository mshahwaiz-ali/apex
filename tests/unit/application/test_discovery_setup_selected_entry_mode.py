from types import SimpleNamespace

from apex.application.discovery_setup import _entry_source
from apex.strategies.contracts import EntryMode


def _candidate(primary_mode: EntryMode, strategy: str = "breakout_continuation"):
    return SimpleNamespace(
        entry=SimpleNamespace(mode=primary_mode),
        strategy=SimpleNamespace(value=strategy),
    )


def test_selected_retest_mode_overrides_primary_market_mode() -> None:
    candidate = _candidate(EntryMode.MARKET_NEAR)

    assert (
        _entry_source(candidate, entry_mode=EntryMode.RETEST)
        == "strategy_generated_broken_level_retest"
    )


def test_selected_sweep_recovery_mode_overrides_primary_retest_mode() -> None:
    candidate = _candidate(EntryMode.RETEST)

    assert (
        _entry_source(candidate, entry_mode=EntryMode.SWEEP_RECOVERY)
        == "strategy_generated_liquidity_boundary_recovery"
    )


def test_primary_mode_remains_fallback_for_legacy_callers() -> None:
    candidate = _candidate(EntryMode.PULLBACK)

    assert _entry_source(candidate) == "strategy_generated_pullback_reference"
