"""PreToolUse 가드: 하네스가 강제하는 안전 규칙 (표준 라이브러리만 사용, 맥/Windows 공통).

stdin으로 받은 훅 입력(JSON)을 검사해 위험한 도구 호출을 차단하거나 사람 확인을 요구한다.
  deny : .env* 내용을 대화로 읽기(Read 도구, cat/head/tail/less/grep 출력, 리다이렉트 없는 sed/awk),
         uv.lock 직접 편집, pip install / venv 사용,
         product 대상 alembic 명령(마이그레이션은 승인된 product 배포의 deploy.sh만 실행한다)
  allow: .env* 수정·생성(편집 도구, 값을 출력하지 않는 셸 명령. 2026-10-20 사용자 결정),
         local·dev 대상 alembic 명령(upgrade/revision/downgrade/stamp 등). 마이그레이션은 local과 dev에서 자동 적용이 정책이다
         (dev DB는 로컬 start-backend.sh --profile dev가 적용)
통과 시 아무것도 출력하지 않고 종료한다.
"""

import json
import os
import re
import shlex
import sys

ENV_FILE = re.compile(r"(?:^|/)\.env(?:\.(?!example$)[\w.-]+)?$")
ALEMBIC = re.compile(r"\balembic\b")
INLINE_PRODUCT = re.compile(r"APP_PROFILE=['\"]?product(?![\w-])")
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
ASSIGNMENT = re.compile(r"^\w+=\S*$")
PRINTERS = {"cat", "less", "more", "head", "tail", "bat", "nl", "od", "xxd", "hexdump", "strings"}
SEARCHERS = {"grep", "egrep", "fgrep", "rg"}
QUIET_FLAGS = re.compile(r"(?:^|\s)-(?:[a-zA-Z]*[qclL][a-zA-Z]*|-quiet|-count|-files-with-matches)\b")
EDITORS = {"sed", "awk"}
IN_PLACE = re.compile(r"(?:^|\s)-i\b")
PIP_OR_VENV = re.compile(r"(?:^|[\s;&|])(?:pip3?\s+install|python3?\s+-m\s+venv|virtualenv)\b")
FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
WRITE_TOOLS = FILE_TOOLS - {"Read"}


def _targets_product(command: str, active_profile: str | None) -> bool:
    return (active_profile or "").strip().lower() == "product" or bool(
        INLINE_PRODUCT.search(command)
    )


def _prints_env_file(command: str) -> bool:
    """명령의 어느 단계든 .env* 파일 내용을 표준 출력으로 내보내면 True."""
    for segment in SEGMENT_SPLIT.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        words = [w for w in words if not ASSIGNMENT.match(w)]
        if not words:
            continue
        program, args = words[0].rsplit("/", 1)[-1], words[1:]
        if program in SEARCHERS:
            # 첫 번째 비옵션 인자는 검색어이므로 파일로 보지 않는다
            operands = [a for a in args if not a.startswith("-")][1:]
            if any(ENV_FILE.search(a) for a in operands) and not QUIET_FLAGS.search(segment):
                return True
            continue
        if not any(ENV_FILE.search(a) for a in args):
            continue
        if program in PRINTERS:
            return True
        if program in EDITORS and ">" not in segment and not IN_PLACE.search(segment):
            return True
    return False


def decide(
    tool_name: str, tool_input: dict[str, object], *, active_profile: str | None = None
) -> tuple[str, str] | None:
    """(결정, 사유)를 돌려준다. 결정은 'deny'. 문제없으면 None."""
    if tool_name in FILE_TOOLS:
        path = str(tool_input.get("file_path", "")).replace("\\", "/")
        if tool_name == "Read" and ENV_FILE.search(path):
            return "deny", "비밀이 든 .env* 파일 내용은 대화로 읽지 않습니다. 변수 이름은 .env.example 참고."
        if tool_name in WRITE_TOOLS and path.endswith("uv.lock"):
            return "deny", "uv.lock은 직접 편집하지 않습니다. 의존성 변경은 승인 후 uv add/remove로 하세요."
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if PIP_OR_VENV.search(command):
            return "deny", "이 프로젝트는 uv만 사용합니다. pip install/venv 대신 uv add, uv sync, uv run을 쓰세요."
        if ALEMBIC.search(command) and _targets_product(command, active_profile):
            return "deny", "product 마이그레이션은 승인된 product 배포(deploy.sh)에서만 실행합니다."
        if _prints_env_file(command):
            return "deny", ".env* 파일 내용을 출력하는 명령입니다. 값을 보지 않는 방식(sed -i, 리다이렉트, grep -q)으로 수정하세요."
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        decision = decide(
            str(payload.get("tool_name", "")),
            dict(payload.get("tool_input") or {}),
            active_profile=os.environ.get("APP_PROFILE"),
        )
    except (ValueError, TypeError):
        return 0  # 입력을 해석할 수 없으면 가드가 흐름을 막지 않는다
    if decision is None:
        return 0
    verdict, reason = decision
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict,
            "permissionDecisionReason": f"[harness] {reason}",
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
