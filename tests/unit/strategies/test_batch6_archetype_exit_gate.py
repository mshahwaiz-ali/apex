from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from pathlib import Path

import apex.strategies.archetype_contract as archetype_contract
from apex.strategies.archetype_contract import ArchetypeFamily

EXPECTED_ADAPTERS: dict[str, ArchetypeFamily] = {
    "momentum_continuation_archetype_profile": ArchetypeFamily.MOMENTUM_CONTINUATION,
    "breakout_retest_archetype_profile": ArchetypeFamily.BREAKOUT_RETEST,
    "first_pullback_archetype_profile": ArchetypeFamily.FIRST_PULLBACK,
    "vwap_reclaim_rejection_archetype_profile": ArchetypeFamily.VWAP_RECLAIM_REJECTION,
    "liquidity_sweep_archetype_profile": ArchetypeFamily.LIQUIDITY_SWEEP,
    "failed_breakout_archetype_profile": ArchetypeFamily.FAILED_BREAKOUT,
    "compression_expansion_archetype_profile": ArchetypeFamily.COMPRESSION_EXPANSION,
    "exhaustion_reversal_archetype_profile": ArchetypeFamily.EXHAUSTION_REVERSAL,
}

FORBIDDEN_CALL_PREFIXES = (
    "generate_",
    "rank_",
    "select_",
    "score_",
    "deduplicate_",
    "resolve_collision",
    "classify_actionability",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "apex.application",
    "apex.cli",
    "apex.presentation",
)


def _module_path() -> Path:
    source = inspect.getsourcefile(archetype_contract)
    assert source is not None
    return Path(source)


def _module_tree() -> ast.Module:
    return ast.parse(_module_path().read_text(encoding="utf-8"))


def _function_nodes() -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in _module_tree().body if isinstance(node, ast.FunctionDef)}


def _call_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _root_name(node: ast.expr) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def test_all_eight_archetype_adapters_are_public_and_callable() -> None:
    exported = set(archetype_contract.__all__)

    assert set(EXPECTED_ADAPTERS) <= exported
    for name in EXPECTED_ADAPTERS:
        adapter = getattr(archetype_contract, name)
        assert isinstance(adapter, Callable)
        signature = inspect.signature(adapter)
        assert tuple(signature.parameters) == ("candidate",)


def test_all_eight_archetype_families_are_distinct() -> None:
    families = tuple(EXPECTED_ADAPTERS.values())

    assert len(families) == 8
    assert len(set(families)) == 8


def test_adapters_return_the_shared_profile_contract() -> None:
    functions = _function_nodes()

    for name in EXPECTED_ADAPTERS:
        function = functions[name]
        profile_calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and _call_name(node) == "StrategyArchetypeProfile"
        ]
        assert len(profile_calls) == 1, name


def test_adapters_do_not_call_generation_or_pipeline_decision_services() -> None:
    functions = _function_nodes()

    for name in EXPECTED_ADAPTERS:
        calls = {
            _call_name(node) for node in ast.walk(functions[name]) if isinstance(node, ast.Call)
        }
        forbidden = {
            call_name for call_name in calls if call_name.startswith(FORBIDDEN_CALL_PREFIXES)
        }
        assert forbidden == set(), (name, forbidden)


def test_adapters_do_not_mutate_trade_candidates() -> None:
    functions = _function_nodes()

    for name in EXPECTED_ADAPTERS:
        function = functions[name]
        candidate_mutations: list[ast.AST] = []

        for node in ast.walk(function):
            targets: tuple[ast.expr, ...] = ()
            if isinstance(node, ast.Assign):
                targets = tuple(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = (node.target,)

            candidate_mutations.extend(
                target
                for target in targets
                if isinstance(target, ast.Attribute) and _root_name(target) == "candidate"
            )

        assert candidate_mutations == [], name


def test_contract_module_has_no_application_cli_or_presentation_dependency() -> None:
    imported_modules: set[str] = set()

    for node in _module_tree().body:
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden = {
        module for module in imported_modules if module.startswith(FORBIDDEN_IMPORT_PREFIXES)
    }
    assert forbidden == set()


def test_exit_gate_is_diagnostic_only() -> None:
    source = _module_path().read_text(encoding="utf-8")

    assert "classify_actionability" not in source
    assert "resolve_collision" not in source
