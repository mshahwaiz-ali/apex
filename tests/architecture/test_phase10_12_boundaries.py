from pathlib import Path


def _source(package: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8").lower() for path in sorted(Path(package).glob("*.py"))
    )


def test_optimization_does_not_mutate_runtime_config() -> None:
    source = _source("src/apex/optimization")

    assert "config/risk.yaml" not in source
    assert "config/strategies.yaml" not in source


def test_intelligence_does_not_execute_or_control_risk() -> None:
    source = _source("src/apex/intelligence")

    for forbidden in ("apex.execution", "submit", "order", "analyze_phase6"):
        assert forbidden not in source


def test_execution_remains_testnet_only_and_separate_from_strategy_engine() -> None:
    source = _source("src/apex/execution")

    for forbidden in (
        "api key",
        "secret",
        "real-money",
        "real_money",
        "apex.strategies.analysis",
        "apex.scoring",
        "apex.backtesting",
        "apex.paper_trading",
    ):
        assert forbidden not in source
    assert "testnet" in source
