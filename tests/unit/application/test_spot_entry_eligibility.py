from apex.application.spot_entry_eligibility import evaluate_spot_entry_eligibility
from apex.domain.spot import SpotMarketRegime
from apex.domain.spot_structure import (
    SpotExtensionState,
    SpotRegimeResult,
    SpotStructureResult,
    SpotTrendState,
)


def _structure(
    *,
    trend: SpotTrendState = SpotTrendState.UPTREND,
    extension: SpotExtensionState = SpotExtensionState.NORMAL,
) -> SpotStructureResult:
    return SpotStructureResult(
        trend=trend,
        extension=extension,
        timeframes=(),
        relative_strength_score=2.0,
        evidence=("fixture",),
    )


def _regime(
    *,
    regime: SpotMarketRegime = SpotMarketRegime.RISK_ON,
    allow_new_entries: bool = True,
) -> SpotRegimeResult:
    return SpotRegimeResult(
        regime=regime,
        allow_new_entries=allow_new_entries,
        evidence=("fixture",),
    )


def test_constructive_structure_and_regime_are_eligible() -> None:
    result = evaluate_spot_entry_eligibility(_structure(), _regime())

    assert result.eligible is True


def test_risk_off_regime_blocks_new_entry() -> None:
    result = evaluate_spot_entry_eligibility(
        _structure(),
        _regime(regime=SpotMarketRegime.RISK_OFF, allow_new_entries=False),
    )

    assert result.eligible is False
    assert any("RISK_OFF" in reason for reason in result.reasons)


def test_terminal_extension_blocks_chase_entry() -> None:
    result = evaluate_spot_entry_eligibility(
        _structure(extension=SpotExtensionState.TERMINAL),
        _regime(),
    )

    assert result.eligible is False
    assert any("terminal" in reason.lower() for reason in result.reasons)


def test_bearish_higher_timeframe_structure_blocks_entry() -> None:
    result = evaluate_spot_entry_eligibility(
        _structure(trend=SpotTrendState.STRONG_DOWNTREND),
        _regime(),
    )

    assert result.eligible is False
    assert any("bearish" in reason.lower() for reason in result.reasons)
