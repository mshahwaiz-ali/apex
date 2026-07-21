"""Guard Batch 10 shadow decomposition pipeline integration."""

from __future__ import annotations

import ast
from pathlib import Path

ORCHESTRATION = Path("src/apex/strategies/orchestration.py")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def test_quality_decomposition_runs_after_execution_quality() -> None:
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    normalize = _function(tree, "_normalize_candidate")
    calls = [
        node.func.id
        for node in ast.walk(normalize)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert "attach_candidate_execution_quality" in calls
    assert "attach_candidate_quality_components_for_candidate" in calls
    assert calls.index("attach_candidate_execution_quality") < calls.index(
        "attach_candidate_quality_components_for_candidate"
    )


def test_shadow_quality_attachment_remains_before_actionability_collection() -> None:
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    analyze = _function(tree, "analyze_strategies")

    candidate_assignment_index = next(
        index
        for index, node in enumerate(analyze.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "candidates" for target in node.targets
        )
    )
    actionability_assignment_index = next(
        index
        for index, node in enumerate(analyze.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "actionability" for target in node.targets
        )
    )

    assert candidate_assignment_index < actionability_assignment_index


def test_quality_component_import_is_local_to_avoid_package_cycle() -> None:
    tree = ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))
    normalize = _function(tree, "_normalize_candidate")

    local_imports = [
        node
        for node in normalize.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "apex.scoring.candidate_quality_components"
    ]

    assert len(local_imports) == 1
    assert all(
        not (
            isinstance(node, ast.ImportFrom)
            and node.module == "apex.scoring.candidate_quality_components"
        )
        for node in tree.body
    )
