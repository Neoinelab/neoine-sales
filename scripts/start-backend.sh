#!/usr/bin/env bash
# backend 개발 서버 실행(profile: local, http://localhost:8000, 코드 변경 시 자동 재시작).
# 시작 전에 DB 스키마를 최신으로 맞춘다(alembic upgrade head, local은 자동 적용 정책).
# 사용: ./scripts/start-backend.sh [--skip-migrate] [--port 8000]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_MIGRATE=false
PORT=8000
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-migrate) SKIP_MIGRATE=true; shift ;;
    --port) PORT="${2:?--port 뒤에 포트 번호가 필요합니다}"; shift 2 ;;
    -h | --help) sed -n '2,4p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "오류: 'uv' 명령이 없습니다. 먼저 ./scripts/setup.sh를 실행하세요." >&2
  exit 1
fi
if [[ ! -d "$ROOT/backend/.venv" || ! -f "$ROOT/backend/.env" ]]; then
  echo "오류: backend/.venv 또는 backend/.env가 없습니다. 먼저 ./scripts/setup.sh를 실행하세요." >&2
  exit 1
fi

cd "$ROOT/backend"
if [[ "$SKIP_MIGRATE" != true ]]; then
  echo "==> DB 스키마 적용 (alembic upgrade head)"
  uv run alembic upgrade head
fi

echo "==> backend 시작: http://localhost:$PORT (API 문서 /docs, 상태 /readyz, 종료 Ctrl+C)"
exec uv run uvicorn app.main:app --reload --port "$PORT" --app-dir src
