"""소스 파일 길이 제한 검사 (기본 300줄).

파일이 커지면 단일 책임·응집도 원칙이 깨질 가능성이 높으므로 길이를 제한한다.
로직을 담은 소스(backend/src)에만 적용한다. tests·scripts는 경로로 넘겨도 검사하지 않는다
(사용자 결정 2026-10-21).
사용법: python scripts/check_file_length.py [--max-lines 300] [PATH ...]
"""

import argparse
import sys
from pathlib import Path

DEFAULT_MAX_LINES = 300
BACKEND_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = BACKEND_DIR / "src"
DEFAULT_PATHS = (Path("src"),)  # backend/ 에서 실행(run_gates·Jenkins), 출력은 상대 경로


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def is_source(path: Path) -> bool:
    return path.resolve().is_relative_to(SOURCE_DIR)


def find_violations(paths: list[Path], max_lines: int) -> list[tuple[Path, int]]:
    violations: list[tuple[Path, int]] = []
    for root in paths:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for file in filter(is_source, files):
            lines = count_lines(file)
            if lines > max_lines:
                violations.append((file, lines))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_PATHS))
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    args = parser.parse_args()

    violations = find_violations([p for p in args.paths if p.exists()], args.max_lines)
    for file, lines in violations:
        print(f"{file}: {lines}줄 (최대 {args.max_lines}줄) - 책임별로 모듈을 분리하세요")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
