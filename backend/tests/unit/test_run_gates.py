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
    """오류 출력의 경로를 계층별 담당 Agent로 대응시킨다."""
    # given: domain·infra·tests 경로의 오류 출력
    output = (
        "src/app/domain/order.py:10: error: bad\n"
        "src/app/infra/db/uow.py:3: error: bad\n"
        "tests/unit/test_x.py:1: error: bad\n"
    )

    # when: 담당자를 찾는다
    owners = gates.owners_for(output)

    # then: 세 담당자가 나온다
    assert owners == ["core-engineer", "infra-engineer", "test-engineer"]


def test_owners_for_normalizes_windows_separators() -> None:
    """윈도 경로 구분자도 정규화해 담당자를 찾는다."""
    # when: 역슬래시 경로의 오류로 담당자를 찾는다
    owners = gates.owners_for("src\\app\\web\\routers\\a.py:1: error")

    # then: web-engineer다
    assert owners == ["web-engineer"]


def test_owners_for_maps_import_linter_modules() -> None:
    """import-linter가 보고한 모듈 이름도 담당자로 대응시킨다."""
    # given: application에서 infra로 향하는 의존 출력
    output = "app.application.use_case -> app.infra.db (l.3)"

    # when: 담당자를 찾는다
    owners = gates.owners_for(output)

    # then: core와 infra 담당자다
    assert owners == ["core-engineer", "infra-engineer"]


def test_owners_for_returns_empty_when_nothing_matches() -> None:
    """대응하는 경로가 없으면 담당자는 비어 있다."""
    # when: 오류가 없는 출력으로 담당자를 찾는다
    owners = gates.owners_for("everything is fine")

    # then: 비어 있다
    assert owners == []


def test_render_report_shows_verdict_and_failure_details() -> None:
    """보고서는 판정과 실패 상세를 보여 준다."""
    # given: 통과한 게이트와 실패한 게이트
    results = [
        gates.GateResult("ruff-check", True, 0.5, ""),
        gates.GateResult("mypy", False, 1.2, "src/app/web/a.py:1: error: x", ["web-engineer"]),
    ]

    # when: 보고서를 만든다
    report = gates.render_report(results)

    # then: FAIL 판정, 실패 행, 실패 상세가 있다
    assert "**FAIL** (1/2 통과)" in report
    assert "| mypy | 실패 | 1.2 | web-engineer |" in report
    assert "## 실패 상세: mypy" in report


def test_render_report_all_passed() -> None:
    """모두 통과하면 PASS이고 실패 상세가 없다."""
    # when: 통과한 게이트만으로 보고서를 만든다
    report = gates.render_report([gates.GateResult("pytest", True, 0.1, "")])

    # then: PASS이고 실패 상세가 없다
    assert "**PASS**" in report
    assert "실패 상세" not in report


def test_select_gates_runs_only_unit_tests_by_default() -> None:
    """기본은 단위 테스트(tests/unit)만 실행하는 pytest 게이트다."""
    # when: 기본 옵션으로 게이트를 고른다
    pytest_gate = next(g for g in gates.select_gates(None, full=False) if g.name == "pytest")

    # then: tests/unit만 대상으로 한다
    assert pytest_gate.command == ("uv", "run", "pytest", "-q", "tests/unit")


def test_select_gates_full_runs_every_test() -> None:
    """full이면 모든 테스트를 실행하는 pytest 게이트다."""
    # when: full 옵션으로 게이트를 고른다
    pytest_gate = next(g for g in gates.select_gates(None, full=True) if g.name == "pytest")

    # then: 경로 제한이 없다
    assert pytest_gate.command == ("uv", "run", "pytest", "-q")


def test_select_gates_only_keeps_requested_gates_and_full_flag() -> None:
    """only를 주면 요청한 게이트만 남고 full 옵션이 반영된다."""
    # when: mypy와 pytest만 full로 고른다
    selected = gates.select_gates(["mypy", "pytest"], full=True)

    # then: 두 게이트뿐이고 pytest는 전체 실행이다
    assert [g.name for g in selected] == ["mypy", "pytest"]
    assert selected[1].command == ("uv", "run", "pytest", "-q")


def test_gate_commands_cover_ci_quality_steps() -> None:
    """게이트 목록은 CI 품질 단계를 모두 포함한다."""
    # when: 게이트 이름을 모은다
    names = [g.name for g in gates.GATES]

    # then: 정해진 일곱 단계가 순서대로 있다
    assert names == [
        "ruff-check",
        "ruff-format",
        "mypy",
        "import-linter",
        "file-length",
        "feature-trace",
        "pytest",
    ]
