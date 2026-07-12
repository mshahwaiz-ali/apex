from pathlib import Path

_STRATEGY_ROOT = Path("src/apex/strategies")
_FORBIDDEN_TERMS = (
    "position_size",
    "position sizing",
    "leverage",
    "liquidation",
    "portfolio allocation",
    "execute_order",
    "place_order",
    "winner",
    "winning candidate",
    "final selection",
)


def test_strategy_layer_does_not_leak_future_phase_responsibilities() -> None:
    violations: list[str] = []
    for path in sorted(_STRATEGY_ROOT.glob("*.py")):
        source = path.read_text(encoding="utf-8").lower()
        for term in _FORBIDDEN_TERMS:
            if term in source:
                violations.append(f"{path}:{term}")

    assert violations == []


def test_orchestration_contains_no_candidate_sorting_or_selection_api() -> None:
    source = (_STRATEGY_ROOT / "analysis.py").read_text(encoding="utf-8")

    assert "sorted(candidates" not in source
    assert "max(candidates" not in source
    assert "min(candidates" not in source
    assert "best_candidate" not in source
    assert "selected_candidate" not in source
