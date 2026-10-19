#!/usr/bin/env bash
# 개발 환경 최초 구성(profile: local). 여러 번 실행해도 안전하다.
#   1) backend: uv sync로 uv.lock의 의존성 설치 → backend/.venv (Python 3.14가 없으면 uv가 받아 온다)
#   2) frontend: corepack pnpm으로 의존성(pnpm-lock.yaml) 설치
#   3) backend/.env가 없으면 .env.example을 복사하고, DB 비밀번호를 넣으라고 안내한 뒤 멈춘다
#   4) DB 스키마 적용(alembic upgrade head)
# 사용: ./scripts/setup.sh [--skip-migrate]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_MIGRATE=false
for arg in "$@"; do
  case "$arg" in
    --skip-migrate) SKIP_MIGRATE=true ;;
    -h | --help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "오류: '$1' 명령이 없습니다. $2" >&2
    exit 1
  fi
}

need uv "설치: https://docs.astral.sh/uv/getting-started/installation/"
need node "Node.js를 설치하세요(corepack 포함)."
need corepack "Node.js에 포함된 corepack이 필요합니다."

step "backend: Python과 의존성 설치 (uv sync)"
(cd "$ROOT/backend" && uv sync --locked)

step "frontend: 의존성 설치 (pnpm install)"
# corepack 서명 오류(Cannot find matching keyid)가 나는 환경이면 검증 키 확인을 끄고 다시 시도한다.
if ! (cd "$ROOT/frontend" && corepack pnpm --version >/dev/null 2>&1); then
  export COREPACK_INTEGRITY_KEYS=0
fi
(cd "$ROOT/frontend" && corepack pnpm install --frozen-lockfile)

ENV_FILE="$ROOT/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  step "backend/.env 만들기"
  cp "$ROOT/backend/.env.example" "$ENV_FILE"
  echo "backend/.env를 만들었습니다. APP_DATABASE_URL의 CHANGE_ME를 로컬 DB 비밀번호로 바꾼 뒤"
  echo "이 스크립트를 다시 실행하세요(특수문자는 URL 인코딩: ! -> %21, @ -> %40)."
  exit 0
fi

if [[ "$SKIP_MIGRATE" == true ]]; then
  echo
  echo "DB 스키마 적용을 건너뛰었습니다(--skip-migrate)."
else
  step "DB 스키마 적용 (alembic upgrade head)"
  (cd "$ROOT/backend" && uv run alembic upgrade head)
fi

echo
echo "완료. 실행: ./scripts/start-backend.sh 와 ./scripts/start-frontend.sh (터미널 2개)"
