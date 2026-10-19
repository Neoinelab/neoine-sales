#!/usr/bin/env bash
# frontend 개발 서버 실행(Vite, http://localhost:5173). /api 요청은 localhost:8000의 backend로 전달된다.
# backend는 ./scripts/start-backend.sh로 따로 띄운다.
# 사용: ./scripts/start-frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
  "") ;;
  -h | --help) sed -n '2,4p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
esac

if ! command -v corepack >/dev/null 2>&1; then
  echo "오류: 'corepack' 명령이 없습니다. Node.js를 설치하세요." >&2
  exit 1
fi
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo "오류: frontend/node_modules가 없습니다. 먼저 ./scripts/setup.sh를 실행하세요." >&2
  exit 1
fi

# corepack 서명 오류(Cannot find matching keyid)가 나는 환경이면 검증 키 확인을 끄고 실행한다.
if ! corepack pnpm --version >/dev/null 2>&1; then
  export COREPACK_INTEGRITY_KEYS=0
fi

if ! curl -fsS -o /dev/null --max-time 2 http://localhost:8000/readyz 2>/dev/null; then
  echo "참고: backend(localhost:8000)가 응답하지 않습니다. ./scripts/start-backend.sh를 먼저 띄우세요."
fi

echo "==> frontend 시작: http://localhost:5173 (종료 Ctrl+C)"
exec corepack pnpm dev
