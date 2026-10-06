"""소스 파일 길이 제한 검사 (기본 300줄).

파일이 커지면 단일 책임·응집도 원칙이 깨질 가능성이 높으므로 길이를 제한한다.
사용법: python scripts/check_file_length.py [--max-lines 300] [PATH ...]
"""

import argparse
import sys
from pathlib import Path

DEFAULT_MAX_LINES = 300
DEFAULT_PATHS = ("src", "tests")


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def find_violations(paths: list[Path], max_lines: int) -> list[tuple[Path, int]]:
    violations: list[tuple[Path, int]] = []
    for root in paths:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for file in files:
            lines = count_lines(file)
            if lines > max_lines:
                violations.append((file, lines))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_PATHS])
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    args = parser.parse_args()

    violations = find_violations([p for p in args.paths if p.exists()], args.max_lines)
    for file, lines in violations:
        print(f"{file}: {lines}줄 (최대 {args.max_lines}줄) - 책임별로 모듈을 분리하세요")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
