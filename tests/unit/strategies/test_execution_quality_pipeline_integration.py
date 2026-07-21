"""Guard canonical execution-quality integration ordering."""

from __future__ import annotations

import ast
from pathlib import Path

ORCHESTRATION = Path("src/apex/strategies/orchestration.py")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def test_strategy_orchestration_attaches_execution_quality_before_scoring() -> None:
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    normalize = _function(tree, "_normalize_candidate")

    calls = [
        node.func.id
        for node in ast.walk(normalize)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert "attach_candidate_execution_quality" in calls
    assert calls.index("replace") < calls.index("attach_candidate_execution_quality")


def test_generated_candidates_flow_through_context_aware_normalization() -> None:
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    analyze = _function(tree, "analyze_strategies")

    normalize_calls = [
        node
        for node in ast.walk(analyze)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_normalize_candidate"
    ]

    assert len(normalize_calls) == 1
    keywords = {keyword.arg for keyword in normalize_calls[0].keywords}
    assert "context" in keywords


def test_actionability_uses_execution_quality_enriched_candidates() -> None:
    source = ORCHESTRATION.read_text(encoding="utf-8")
    generation_index = source.index("_normalize_candidate(candidate, context=context)")
    actionability_index = source.index("actionability = tuple(")

    assert generation_index < actionability_index
