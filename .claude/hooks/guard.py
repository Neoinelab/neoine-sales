"""PreToolUse 가드: 하네스가 강제하는 안전 규칙 (표준 라이브러리만 사용, 맥/Windows 공통).

stdin으로 받은 훅 입력(JSON)을 검사해 위험한 도구 호출을 차단하거나 사람 확인을 요구한다.
  deny : .env* 읽기/쓰기, uv.lock 직접 편집, pip install / venv 사용,
         product 대상 alembic 명령(마이그레이션은 승인된 product 배포의 deploy.sh만 실행한다)
  ask  : Bash에서 .env 언급
  allow: local·dev 대상 alembic 명령(upgrade/revision/downgrade/stamp 등). 마이그레이션은 local과 dev에서 자동 적용이 정책이다.
         (dev는 main 머지 시 Jenkins 배포의 deploy.sh가 자동 실행)
통과 시 아무것도 출력하지 않고 종료한다.
"""

import json
import os
import re
import sys

ENV_FILE = re.compile(r"(?:^|/)\.env(?:\.(?!example$)[\w.-]+)?$")
ENV_IN_COMMAND = re.compile(r"(?<![\w-])\.env(?!\.example)(?:\.[\w.-]+)?(?![\w-])")
ALEMBIC = re.compile(r"\balembic\b")
INLINE_PRODUCT = re.compile(r"APP_PROFILE=['\"]?product(?![\w-])")
PIP_OR_VENV = re.compile(r"(?:^|[\s;&|])(?:pip3?\s+install|python3?\s+-m\s+venv|virtualenv)\b")
FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
WRITE_TOOLS = FILE_TOOLS - {"Read"}


def _targets_product(command: str, active_profile: str | None) -> bool:
    return (active_profile or "").strip().lower() == "product" or bool(
        INLINE_PRODUCT.search(command)
    )


def decide(
    tool_name: str, tool_input: dict[str, object], *, active_profile: str | None = None
) -> tuple[str, str] | None:
    """(결정, 사유)를 돌려준다. 결정은 'deny' 또는 'ask'. 문제없으면 None."""
    if tool_name in FILE_TOOLS:
        path = str(tool_input.get("file_path", "")).replace("\\", "/")
        if ENV_FILE.search(path):
            return "deny", "비밀이 든 .env* 파일은 AI가 읽거나 쓰지 않습니다. 변수 이름은 .env.example 참고."
        if tool_name in WRITE_TOOLS and path.endswith("uv.lock"):
            return "deny", "uv.lock은 직접 편집하지 않습니다. 의존성 변경은 승인 후 uv add/remove로 하세요."
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if PIP_OR_VENV.search(command):
            return "deny", "이 프로젝트는 uv만 사용합니다. pip install/venv 대신 uv add, uv sync, uv run을 쓰세요."
        if ALEMBIC.search(command) and _targets_product(command, active_profile):
            return "deny", "product 마이그레이션은 승인된 product 배포(deploy.sh)에서만 실행합니다."
        if ENV_IN_COMMAND.search(command):
            return "ask", ".env* 파일을 다루는 명령입니다. 비밀 값이 출력되거나 변경되지 않는지 확인하세요."
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
