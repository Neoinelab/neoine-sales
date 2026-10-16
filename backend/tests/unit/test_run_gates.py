import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_gates.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_gates", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gates = _load()


def test_owners_for_maps_paths_to_layer_owners() -> None:
    output = (
        "src/app/domain/order.py:10: error: bad\n"
        "src/app/infra/db/uow.py:3: error: bad\n"
        "tests/unit/test_x.py:1: error: bad\n"
    )

    assert gates.owners_for(output) == ["core-engineer", "infra-engineer", "test-engineer"]


def test_owners_for_normalizes_windows_separators() -> None:
    assert gates.owners_for("src\\app\\web\\routers\\a.py:1: error") == ["web-engineer"]


def test_owners_for_maps_import_linter_modules() -> None:
    output = "app.application.use_case -> app.infra.db (l.3)"

    assert gates.owners_for(output) == ["core-engineer", "infra-engineer"]


def test_owners_for_returns_empty_when_nothing_matches() -> None:
    assert gates.owners_for("everything is fine") == []


def test_render_report_shows_verdict_and_failure_details() -> None:
    results = [
        gates.GateResult("ruff-check", True, 0.5, ""),
        gates.GateResult("mypy", False, 1.2, "src/app/web/a.py:1: error: x", ["web-engineer"]),
    ]

    report = gates.render_report(results)

    assert "**FAIL** (1/2 통과)" in report
    assert "| mypy | 실패 | 1.2 | web-engineer |" in report
    assert "## 실패 상세: mypy" in report


def test_render_report_all_passed() -> None:
    report = gates.render_report([gates.GateResult("pytest", True, 0.1, "")])

    assert "**PASS**" in report
    assert "실패 상세" not in report


def test_select_gates_runs_only_unit_tests_by_default() -> None:
    pytest_gate = next(g for g in gates.select_gates(None, full=False) if g.name == "pytest")

    assert pytest_gate.command == ("uv", "run", "pytest", "-q", "tests/unit")


def test_select_gates_full_runs_every_test() -> None:
    pytest_gate = next(g for g in gates.select_gates(None, full=True) if g.name == "pytest")

    assert pytest_gate.command == ("uv", "run", "pytest", "-q")


def test_select_gates_only_keeps_requested_gates_and_full_flag() -> None:
    selected = gates.select_gates(["mypy", "pytest"], full=True)

    assert [g.name for g in selected] == ["mypy", "pytest"]
    assert selected[1].command == ("uv", "run", "pytest", "-q")


def test_gate_commands_cover_ci_quality_steps() -> None:
    names = [g.name for g in gates.GATES]

    assert names == ["ruff-check", "ruff-format", "mypy", "import-linter", "file-length", "pytest"]
