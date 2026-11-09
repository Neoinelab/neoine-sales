import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_feature_trace.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_feature_trace", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trace = _load()
# 이 파일 자체가 대조 대상이 되지 않도록 주석 표식을 나눠 조합한다
MARK = "테스트 " + "코드:"

HEADER = "| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |\n| --- | --- | --- | --- | --- |\n"


def _repo(
    tmp_path: Path, rows: str, sections: str, *, status: str = "확정(2026-11-09 사용자 확인)"
) -> Path:
    features = tmp_path / "docs" / "features"
    features.mkdir(parents=True)
    (features / "README.md").write_text("| XX-001 | 예시 | | backend | |\n", encoding="utf-8")
    (features / "sample.md").write_text(
        f"# 샘플   (feature 코드: SM, 상태: {status})\n\n{HEADER}{rows}\n{sections}",
        encoding="utf-8",
    )
    (tmp_path / "backend" / "tests" / "unit" / "application").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "features").mkdir(parents=True)
    return tmp_path


def _backend_test(root: Path, body: str) -> None:
    path = root / "backend" / "tests" / "unit" / "application" / "test_sample.py"
    path.write_text(body, encoding="utf-8")


def _frontend_test(root: Path, body: str) -> None:
    path = root / "frontend" / "src" / "features" / "Sample.test.tsx"
    path.write_text(body, encoding="utf-8")


BACKEND_ROW = "| SM-001 | 저장한다 | SM-R1 | backend | `application/test_sample.py::test_a` |\n"
FRONT_ROW = "| SM-002 | 보인다 | SM-R2 | frontend | `features/Sample.test.tsx > 보인다` |\n"
BOTH_ROW = (
    "| SM-003 | 계산한다 | SM-R3 | both | "
    "`application/test_sample.py::test_b`<br>`features/Sample.test.tsx > 계산` |\n"
)


def test_check_passes_when_every_case_has_a_test_in_its_layer(tmp_path: Path) -> None:
    """모든 케이스가 층에 맞는 쪽 테스트 주석과 실제 위치를 가지면 위반이 없다."""
    # given: backend·frontend·both 케이스와 각 번호를 단 테스트
    root = _repo(
        tmp_path, BACKEND_ROW + FRONT_ROW + BOTH_ROW, "### SM-001 a\n### SM-002 b\n### SM-003 c\n"
    )
    _backend_test(root, f'"""{MARK} SM-001"""\n"""{MARK} SM-003"""\n')
    _frontend_test(root, f"// {MARK} SM-002, SM-003\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: 위반 0건
    assert problems == []


def test_check_reports_a_case_without_a_test_comment(tmp_path: Path) -> None:
    """확정 문서의 케이스에 번호 주석을 단 테스트가 없으면 위반이다."""
    # given: SM-001 케이스와 번호 주석이 없는 테스트 파일
    root = _repo(tmp_path, BACKEND_ROW, "### SM-001 a\n")
    _backend_test(root, "def test_a() -> None: ...\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: backend 주석 누락 1건
    assert problems == [f"sample.md SM-001: backend 테스트에 `{MARK} SM-001` 주석이 없다"]


def test_check_reports_a_both_case_missing_the_frontend_side(tmp_path: Path) -> None:
    """층이 both인데 frontend 테스트에 번호가 없으면 위반이다."""
    # given: both 케이스, backend 테스트에만 번호
    root = _repo(tmp_path, BOTH_ROW, "### SM-003 c\n")
    _backend_test(root, f"# {MARK} SM-003\n")
    _frontend_test(root, "it('계산', () => {})\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: frontend 쪽 누락 1건
    assert problems == [f"sample.md SM-003: frontend 테스트에 `{MARK} SM-003` 주석이 없다"]


def test_check_reports_test_codes_unknown_to_every_doc(tmp_path: Path) -> None:
    """테스트가 어느 문서에도 없는 번호를 가리키면 위반이다."""
    # given: SM-001만 있는 문서와 SM-009를 가리키는 테스트
    root = _repo(tmp_path, BACKEND_ROW, "### SM-001 a\n")
    _backend_test(root, f"# {MARK} SM-001, SM-009\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: SM-009 하나만 지적
    assert len(problems) == 1
    assert problems[0].startswith("SM-009: 문서에 없는 번호")


def test_check_reports_tests_pointing_at_a_retired_case(tmp_path: Path) -> None:
    """폐기된 케이스 번호를 테스트가 가리키면 위반이고, 폐기 케이스 자체는 테스트가 없어도 된다."""
    # given: 폐기 표시된 SM-004 행(절 제목 없음)과 그 번호를 단 테스트
    root = _repo(tmp_path, "| SM-004 | (폐기) | | backend | |\n", "")
    _backend_test(root, f"# {MARK} SM-004\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: 폐기 번호 참조 1건만
    assert len(problems) == 1
    assert problems[0].startswith("SM-004: 폐기된 번호")


def test_check_reports_a_location_whose_file_does_not_exist(tmp_path: Path) -> None:
    """테스트 위치 칸의 파일이 없으면 위반이다."""
    # given: 위치 칸이 없는 파일을 가리키는 케이스
    row = "| SM-001 | 저장한다 | SM-R1 | backend | `application/test_gone.py::test_a` |\n"
    root = _repo(tmp_path, row, "### SM-001 a\n")
    _backend_test(root, f"# {MARK} SM-001\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: 위치 파일 없음 1건
    assert problems == ["sample.md SM-001: 테스트 위치의 파일이 없다 (application/test_gone.py)"]


def test_check_reports_a_case_present_only_in_the_table(tmp_path: Path) -> None:
    """표에는 있는데 Given/When/Then 절이 없는 케이스는 위반이다."""
    # given: 절 제목이 없는 SM-001 행
    root = _repo(tmp_path, BACKEND_ROW, "")
    _backend_test(root, f"# {MARK} SM-001\n")
    # when: 대조한다
    problems = trace.check(root)
    # then: 표에만 있음 1건
    assert problems == ["sample.md SM-001: 케이스가 표에만 있다"]


def test_check_skips_draft_docs(tmp_path: Path) -> None:
    """초안 문서는 사용자 확인 전이라 케이스 누락을 검사하지 않는다."""
    # given: 테스트가 하나도 없는 초안 문서
    root = _repo(tmp_path, BACKEND_ROW, "### SM-001 a\n", status="초안")
    # when: 대조한다
    problems = trace.check(root)
    # then: 위반 없음
    assert problems == []
