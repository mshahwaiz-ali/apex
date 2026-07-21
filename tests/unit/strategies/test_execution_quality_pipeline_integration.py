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
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    analyze = _function(tree, "analyze_strategies")

    normalize_calls = [
        node
        for node in ast.walk(analyze)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_normalize_candidate"
    ]
    actionability_assignments = [
        node
        for node in analyze.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "actionability" for target in node.targets
        )
    ]

    assert len(normalize_calls) == 1
    assert len(actionability_assignments) == 1
    assert normalize_calls[0].lineno < actionability_assignments[0].lineno
