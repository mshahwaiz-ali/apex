from pathlib import Path

FORBIDDEN_TERMS = (
    "order placement",
    "exchange execution",
    "historical replay",
    "paper trade",
    "signal lifecycle",
    "trailing stop",
)


def test_phase6_contains_no_future_phase_concepts() -> None:
    package = Path("src/apex/risk")
    source = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in sorted(package.glob("*.py"))
    )
    for forbidden in FORBIDDEN_TERMS:
        assert forbidden not in source


def test_phase6_does_not_import_future_phase_packages() -> None:
    package = Path("src/apex/risk")
    source = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in sorted(package.glob("*.py"))
    )
    for forbidden_import in (
        "apex.scanner",
        "apex.reporting",
        "apex.backtesting",
        "apex.paper_trading",
        "apex.execution",
        "apex.orders",
        "apex.trade_management",
    ):
        assert forbidden_import not in source
