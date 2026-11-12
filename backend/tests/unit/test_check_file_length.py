import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_file_length.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_file_length", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


length = _load()


def _write(path: Path, lines: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x = 1\n" * lines, encoding="utf-8")
    return path


def test_source_file_over_limit_is_a_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """소스 파일이 제한 줄 수를 넘으면 위반이다."""
    # given: 301줄 파일과 300줄 파일이 있는 src 디렉터리
    monkeypatch.setattr(length, "SOURCE_DIR", tmp_path / "src")
    long_file = _write(tmp_path / "src" / "app" / "big.py", 301)
    _write(tmp_path / "src" / "app" / "ok.py", 300)

    # when: 300줄 기준으로 검사한다
    violations = length.find_violations([tmp_path / "src"], 300)

    # then: 301줄 파일만 위반이다
    assert violations == [(long_file, 301)]


def test_test_and_script_files_are_never_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """테스트·스크립트 파일은 길어도 검사하지 않는다."""
    # given: 500줄짜리 테스트·스크립트 파일
    monkeypatch.setattr(length, "SOURCE_DIR", tmp_path / "src")
    test_file = _write(tmp_path / "tests" / "unit" / "test_big.py", 500)
    script_file = _write(tmp_path / "scripts" / "big.py", 500)

    # when: 300줄 기준으로 검사한다
    violations = length.find_violations([tmp_path / "tests", test_file, script_file], 300)

    # then: 위반이 없다
    assert violations == []


def test_default_paths_cover_only_backend_src() -> None:
    """기본 검사 경로는 backend src뿐이다."""
    # when: 기본 경로마다 소스 여부를 판정한다
    flags = [length.is_source(p) for p in length.DEFAULT_PATHS]

    # then: 모두 소스다
    assert flags == [True]
