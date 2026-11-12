"""feature 문서의 BDD 테스트 케이스 번호와 테스트 코드 주석을 대조한다 (2026-11-09).

확정된 `docs/features/<feature>.md`의 케이스(표 행 `| XX-001 | …`)마다 같은 번호의
`테스트 코드: XX-001` 주석을 가진 테스트가 있는지, 층(backend/frontend/both)에 맞는 쪽에
있는지, 테스트가 문서에 없는 번호나 폐기된 번호를 가리키지 않는지, "테스트 위치" 칸의
파일이 실제로 있는지 확인한다. 초안 문서는 건너뛴다(사용자 확인 전).

역방향 위치 검사(2026-11-11): 확정 문서의 폐기되지 않은 케이스마다 그 번호를 단 테스트
파일이 "테스트 위치" 칸에 모두 있어야 한다(칸에 "외 N건"이 있으면 빠진 파일 N개까지 허용).
functional test는 2026-11-12 삭제되어 예외가 없다. frontend 수집에는
`src/**/*.test.ts(x)`와 `src/gateway/contract/*.contract.ts`가 들어간다.

사용법: uv run python scripts/check_feature_trace.py [--repo-root PATH]
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE = r"[A-Z]{2,4}-\d{3}"
ROW_PATTERN = re.compile(rf"^\|\s*({CODE})\s*\|(.*)$")
HEADING_PATTERN = re.compile(rf"^###\s+({CODE})\b")
COMMENT_PATTERN = re.compile(rf"테스트 코드:\s*((?:{CODE})(?:\s*,\s*{CODE})*)")
CODE_PATTERN = re.compile(CODE)
LOCATION_PATTERN = re.compile(r"`([^`]+?\.(?:py|tsx?))(?:::| >|`)")
EXTRA_PATTERN = re.compile(r"외\s*(\d+)\s*건")
LAYERS = ("backend", "frontend", "both")


@dataclass
class Case:
    code: str
    layer: str
    retired: bool
    locations: list[str] = field(default_factory=list)
    extra: int = 0


@dataclass
class FeatureDoc:
    path: Path
    confirmed: bool
    cases: dict[str, Case]
    headings: set[str]


def parse_doc(path: Path) -> FeatureDoc:
    """문서에서 확정 여부, 케이스 표 행, 케이스 절 제목을 읽는다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    confirmed = bool(lines) and "상태: 확정" in lines[0]
    cases: dict[str, Case] = {}
    headings: set[str] = set()
    for line in lines:
        if heading := HEADING_PATTERN.match(line):
            headings.add(heading.group(1))
            continue
        row = ROW_PATTERN.match(line)
        if not row:
            continue
        cells = [c.strip() for c in row.group(2).split("|")]
        layer = next((c for c in cells if c in LAYERS), "")
        location_cell = cells[-2] if len(cells) >= 2 else ""  # noqa: PLR2004
        extra = EXTRA_PATTERN.search(location_cell)
        cases[row.group(1)] = Case(
            code=row.group(1),
            layer=layer,
            retired=bool(cells) and cells[0].lstrip("(~").startswith("폐기"),
            locations=LOCATION_PATTERN.findall(location_cell),
            extra=int(extra.group(1)) if extra else 0,
        )
    return FeatureDoc(path, confirmed, cases, headings)


def collect_test_codes(paths: list[Path]) -> dict[str, set[Path]]:
    """테스트 파일들에서 `테스트 코드:` 주석의 번호 -> 파일 집합을 모은다."""
    found: dict[str, set[Path]] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in COMMENT_PATTERN.finditer(text):
            for code in CODE_PATTERN.findall(match.group(1)):
                found.setdefault(code, set()).add(path)
    return found


def backend_tests(root: Path) -> list[Path]:
    return sorted((root / "backend" / "tests").rglob("test_*.py"))


def frontend_tests(root: Path) -> list[Path]:
    src = root / "frontend" / "src"
    tests = {p for p in src.rglob("*.test.ts*") if "node_modules" not in p.parts}
    tests.update((src / "gateway" / "contract").glob("*.contract.ts"))
    return sorted(tests)


def location_paths(root: Path, location: str) -> list[Path]:
    """위치 칸 경로가 가리킬 수 있는 파일 후보(backend tests/unit·tests 기준, frontend src 기준)."""
    if location.endswith(".py"):
        tests = root / "backend" / "tests"
        return [tests / "unit" / location, tests / location]
    return [root / "frontend" / "src" / location]


def location_exists(root: Path, location: str) -> bool:
    """`application/x.py`·`unit/…`(backend tests/unit 기준) 또는 frontend src 기준 경로."""
    return any(p.exists() for p in location_paths(root, location))


def check(root: Path) -> list[str]:
    """위반 메시지 목록을 돌려준다(없으면 통과)."""
    problems: list[str] = []
    docs = [
        parse_doc(p)
        for p in sorted((root / "docs" / "features").glob("*.md"))
        if p.name != "README.md"
    ]
    backend = collect_test_codes(backend_tests(root))
    frontend = collect_test_codes(frontend_tests(root))
    known: dict[str, Case] = {}
    for doc in docs:
        known.update(doc.cases)
        if not doc.confirmed:
            continue
        problems += _check_doc(root, doc, backend, frontend)
        problems += _check_reverse(root, doc, backend, frontend)
    for code in sorted(set(backend) | set(frontend)):
        files = sorted(
            str(p.relative_to(root)) for p in backend.get(code, set()) | frontend.get(code, set())
        )
        if code not in known:
            problems.append(f"{code}: 문서에 없는 번호를 테스트가 가리킨다 ({', '.join(files)})")
        elif known[code].retired:
            problems.append(f"{code}: 폐기된 번호를 테스트가 가리킨다 ({', '.join(files)})")
    return problems


def _check_doc(
    root: Path, doc: FeatureDoc, backend: dict[str, set[Path]], frontend: dict[str, set[Path]]
) -> list[str]:
    name = doc.path.name
    problems: list[str] = []
    for code in sorted(set(doc.cases) ^ doc.headings):
        where = "표에만" if code in doc.cases else "절 제목에만"
        if code in doc.cases and doc.cases[code].retired:
            continue
        problems.append(f"{name} {code}: 케이스가 {where} 있다")
    for case in (c for c in doc.cases.values() if not c.retired):
        if case.layer not in LAYERS:
            problems.append(f"{name} {case.code}: 층 칸이 backend/frontend/both가 아니다")
            continue
        if case.layer in ("backend", "both") and case.code not in backend:
            problems.append(
                f"{name} {case.code}: backend 테스트에 `테스트 코드: {case.code}` 주석이 없다"
            )
        if case.layer in ("frontend", "both") and case.code not in frontend:
            problems.append(
                f"{name} {case.code}: frontend 테스트에 `테스트 코드: {case.code}` 주석이 없다"
            )
        if not case.locations:
            problems.append(f"{name} {case.code}: 테스트 위치 칸이 비어 있다")
        problems += [
            f"{name} {case.code}: 테스트 위치의 파일이 없다 ({loc})"
            for loc in case.locations
            if not location_exists(root, loc)
        ]
    return problems


def _check_reverse(
    root: Path, doc: FeatureDoc, backend: dict[str, set[Path]], frontend: dict[str, set[Path]]
) -> list[str]:
    """번호를 단 테스트 파일이 그 케이스의 위치 칸에 모두 있는지 본다.

    위치 칸이 비었거나 없는 파일을 가리키면 정방향 검사가 이미 지적하므로 건너뛴다.
    """
    problems: list[str] = []
    for case in (c for c in doc.cases.values() if not c.retired):
        if not case.locations or not all(location_exists(root, loc) for loc in case.locations):
            continue
        listed = {p.resolve() for loc in case.locations for p in location_paths(root, loc)}
        missing = sorted(
            str(p.relative_to(root))
            for p in backend.get(case.code, set()) | frontend.get(case.code, set())
            if p.resolve() not in listed
        )
        if len(missing) > case.extra:
            problems.append(
                f"{doc.path.name} {case.code}: 번호를 단 테스트 파일이 테스트 위치 칸에 없다"
                f" ({', '.join(missing)})"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="저장소 루트")
    args = parser.parse_args()
    problems = check(args.repo_root)
    for problem in problems:
        print(problem)
    print(f"feature trace: {'FAIL' if problems else 'PASS'} (위반 {len(problems)}건)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
