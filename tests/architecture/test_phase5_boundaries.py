from pathlib import Path

FORBIDDEN_TERMS = (
    "exchange execution",
    "order placement",
    "leverage",
    "liquidation",
    "position sizing",
    "portfolio allocation",
    "trade management",
    "trailing stop",
)


def test_phase5_contains_no_future_phase_concepts() -> None:
    package = Path("src/apex/scoring")
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(package.glob("*.py"))
    )
    for forbidden in FORBIDDEN_TERMS:
        assert forbidden not in source


def test_phase5_does_not_import_future_phase_packages() -> None:
    package = Path("src/apex/scoring")
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(package.glob("*.py"))
    )
    for forbidden_import in (
        "apex.execution",
        "apex.orders",
        "apex.portfolio",
        "apex.risk.position",
        "apex.trade_management",
    ):
        assert forbidden_import not in source
