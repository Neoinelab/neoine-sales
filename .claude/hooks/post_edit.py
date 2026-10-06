"""PostToolUse: backend 파이썬 파일을 편집한 직후 자동 포맷·린트하고 파일 길이를 점검한다.

- ruff format + ruff check --fix 를 적용한다(결정적, 토큰 비용 없음).
- 자동으로 고치지 못한 린트 오류와 파일 길이 초과는 Claude에게 컨텍스트로 알려 바로 고치게 한다.
어떤 오류가 나도 편집 흐름을 막지 않는다(조용히 종료).
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_DIR / "backend"
WATCHED = ("src", "tests", "scripts")
MAX_OUTPUT_LINES = 15


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "--project", str(BACKEND_DIR), *args],  # noqa: S607
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )


def target_file(payload: dict[str, object]) -> Path | None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    raw = ""
    if isinstance(tool_input, dict):
        raw = str(tool_input.get("file_path", ""))
    if not raw and isinstance(tool_response, dict):
        raw = str(tool_response.get("filePath", ""))
    path = Path(raw)
    if path.suffix != ".py" or not path.is_file():
        return None
    try:
        relative = path.resolve().relative_to(BACKEND_DIR)
    except ValueError:
        return None
    return path if relative.parts and relative.parts[0] in WATCHED else None


def collect_messages(path: Path) -> list[str]:
    messages: list[str] = []
    run(["ruff", "format", str(path)])
    lint = run(["ruff", "check", "--fix", "--quiet", str(path)])
    if lint.returncode != 0:
        details = "\n".join((lint.stdout + lint.stderr).strip().splitlines()[:MAX_OUTPUT_LINES])
        messages.append(f"ruff가 자동으로 고치지 못한 오류가 있습니다:\n{details}")
    length = run(["python", "scripts/check_file_length.py", str(path)])
    if length.returncode != 0:
        messages.append(length.stdout.strip())
    return messages


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = target_file(payload)
        messages = collect_messages(path) if path else []
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0
    if messages:
        context = f"[harness] {path.name if path else ''} 점검 결과\n" + "\n\n".join(messages)
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
