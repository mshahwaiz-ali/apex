from apex.cli_app import app
from apex.cli_overlay import command_name


def test_corrected_cli_exposes_explicit_simulation_and_backtest_commands() -> None:
    names = {command_name(command) for command in app.registered_commands}

    assert "analyze" in names
    assert "fetch" in names
    assert "ticker" in names
    assert "simulate-current-setup" in names
    assert "chronological-backtest" in names
    assert "backtest" not in names


def test_frozen_and_removed_workflows_are_not_registered() -> None:
    command_names = {
        command_name(command)
        for command in app.registered_commands
        if command_name(command) is not None
    }
    group_names = {
        group.name
        for group in app.registered_groups
        if group.name is not None and not group.hidden
    }

    assert {
        "spot-analyze",
        "spot-orchestrate",
        "spot-live",
        "spot-scan-live",
        "spot-plan",
    }.isdisjoint(command_names)

    assert {
        "spot",
        "optimize",
        "intelligence",
        "execute",
    }.isdisjoint(group_names)


def test_futures_scan_exposes_only_canonical_scanner_options() -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["futures", "scan", "--help"])

    assert result.exit_code == 0, result.output
    assert "--mode" not in result.output
    assert "gainers" not in result.output.lower()
    assert "text or json" in result.output.lower()
    assert "verbose" not in result.output.lower()
    assert "debug" not in result.output.lower()


def test_root_scan_exposes_only_canonical_scanner_options() -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["scan", "--help"])

    assert result.exit_code == 0, result.output
    assert "--mode" not in result.output
    assert "gainers" not in result.output.lower()
    assert "text or json" in result.output.lower()
    assert "verbose" not in result.output.lower()
    assert "debug" not in result.output.lower()


def test_futures_scan_rejects_removed_output_modes_before_bootstrap() -> None:
    from typer.testing import CliRunner

    for removed_mode in ("verbose", "debug"):
        result = CliRunner().invoke(
            app,
            ["futures", "scan", "--output", removed_mode],
        )

        assert result.exit_code != 0
        assert "scanner output must be one of: text, json" in result.output


def test_futures_scan_output_mode_is_case_insensitive() -> None:
    from apex.cli_commands.scanner import _normalize_scanner_output

    assert _normalize_scanner_output(" TEXT ") == "text"
    assert _normalize_scanner_output("JSON") == "json"

def test_root_and_futures_scan_share_canonical_callback() -> None:
    from apex.cli_overlay import command_name

    root_scan = next(
        command
        for command in app.registered_commands
        if command_name(command) == "scan"
    )
    futures_group = next(
        group
        for group in app.registered_groups
        if group.name == "futures"
    )
    futures_scan = next(
        command
        for command in futures_group.typer_instance.registered_commands
        if command_name(command) == "scan"
    )

    assert root_scan.callback is futures_scan.callback
    assert root_scan.callback.__module__ == "apex.cli_commands.scanner"


def test_legacy_cli_source_has_no_scan_implementation() -> None:
    import ast
    from pathlib import Path

    source_path = Path(__file__).parents[2] / "src" / "apex" / "cli.py"
    module = ast.parse(source_path.read_text())

    scan_functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "scan"
    ]

    assert scan_functions == []
