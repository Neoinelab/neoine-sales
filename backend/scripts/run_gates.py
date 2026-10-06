"""품질 게이트 실행기 (결정적 검증, 맥/Windows/Linux 공통).

모든 게이트를 끝까지 실행한 뒤 항목별 통과/실패와 실패 담당자를 요약한다.
Jenkins Quality 단계와 같은 명령 목록을 쓰므로 로컬 게이트와 CI가 어긋나지 않게 유지한다.

사용법:
    uv run python scripts/run_gates.py                  # 전체 게이트
    uv run python scripts/run_gates.py --only mypy      # 일부만 (여러 번 지정 가능)
    uv run python scripts/run_gates.py --report ../artifacts/30-review/gate.md
    uv run python scripts/run_gates.py --json           # 기계 판독용 출력
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
TAIL_LINES = 40


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]


GATES: tuple[Gate, ...] = (
    Gate("ruff-check", ("uv", "run", "ruff", "check", ".")),
    Gate("ruff-format", ("uv", "run", "ruff", "format", "--check", ".")),
    Gate("mypy", ("uv", "run", "mypy", "src", "scripts", "tests")),
    Gate("import-linter", ("uv", "run", "lint-imports")),
    Gate("file-length", ("uv", "run", "python", "scripts/check_file_length.py")),
    Gate("pytest", ("uv", "run", "pytest", "-q")),
)

# 경로(접두어) -> 수정 담당. 먼저 일치하는 항목이 우선한다.
OWNER_BY_PATH: tuple[tuple[str, str], ...] = (
    ("src/app/domain/", "core-engineer"),
    ("src/app/application/", "core-engineer"),
    ("src/app/config/", "core-engineer"),
    ("src/app/infra/", "infra-engineer"),
    ("src/app/web/", "web-engineer"),
    ("tests/", "test-engineer"),
    ("scripts/", "사람(하네스/도구)"),
)
OWNER_BY_LAYER = {
    "domain": "core-engineer",
    "application": "core-engineer",
    "config": "core-engineer",
    "infra": "infra-engineer",
    "web": "web-engineer",
}
PATH_PATTERN = re.compile(r"(?:src|tests|scripts)/[\w./-]+\.py")
MODULE_PATTERN = re.compile(r"\bapp\.(domain|application|config|infra|web)\b")


@dataclass
class GateResult:
    name: str
    passed: bool
    seconds: float
    output_tail: str
    owners: list[str] = field(default_factory=list)


def owners_for(output: str) -> list[str]:
    """실패 출력에서 파일 경로/모듈명을 찾아 수정 담당 목록을 만든다."""
    owners: set[str] = set()
    for raw in PATH_PATTERN.findall(output.replace("\\", "/")):
        for prefix, owner in OWNER_BY_PATH:
            if raw.startswith(prefix):
                owners.add(owner)
                break
    for layer in MODULE_PATTERN.findall(output):
        owners.add(OWNER_BY_LAYER[layer])
    return sorted(owners)


def run_gate(gate: Gate) -> GateResult:
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603
        gate.command,
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    seconds = time.monotonic() - started
    combined = (completed.stdout + completed.stderr).strip()
    passed = completed.returncode == 0
    tail = "\n".join(combined.splitlines()[-TAIL_LINES:])
    owners = [] if passed else owners_for(combined)
    return GateResult(gate.name, passed, round(seconds, 1), tail, owners)


def render_report(results: list[GateResult]) -> str:
    verdict = "PASS" if all(r.passed for r in results) else "FAIL"
    lines = [
        "# Gate Report",
        "",
        f"- 결과: **{verdict}** ({sum(r.passed for r in results)}/{len(results)} 통과)",
        "",
        "| 게이트 | 결과 | 시간(초) | 수정 담당 |",
        "| --- | --- | --- | --- |",
    ]
    for r in results:
        mark = "통과" if r.passed else "실패"
        lines.append(f"| {r.name} | {mark} | {r.seconds} | {', '.join(r.owners) or '-'} |")
    for r in (x for x in results if not x.passed):
        lines += ["", f"## 실패 상세: {r.name}", "", "```text", r.output_tail, "```"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--only", action="append", choices=[g.name for g in GATES], help="실행할 게이트"
    )
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    parser.add_argument("--report", type=Path, help="마크다운 리포트 저장 경로")
    args = parser.parse_args()

    selected = [g for g in GATES if not args.only or g.name in args.only]
    results = [run_gate(g) for g in selected]

    report = render_report(results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    print(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)
        if args.json
        else report
    )
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
