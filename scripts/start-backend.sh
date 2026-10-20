#!/usr/bin/env bash
# backend 개발 서버를 백그라운드(nohup)로 실행(http://localhost:8000, 코드 변경 시 자동 재시작).
# 터미널을 닫아도 계속 돌고, 출력은 logs/backend.log(이어 쓰기), PID는 logs/backend.pid에 남는다.
# 프로파일: local(기본, backend/.env) 또는 dev(backend/.env.dev). product는 서버 배포(deploy.sh)로만 띄운다.
# 시작 전에 그 프로파일의 DB 스키마를 최신으로 맞춘다(alembic upgrade head).
# 사용: ./scripts/start-backend.sh [--profile local|dev] [--skip-migrate] [--port 8000]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/backend.log"
PID_FILE="$LOG_DIR/backend.pid"
SKIP_MIGRATE=false
PORT=8000
PROFILE=local
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-migrate) SKIP_MIGRATE=true; shift ;;
    --port) PORT="${2:?--port 뒤에 포트 번호가 필요합니다}"; shift 2 ;;
    --profile) PROFILE="${2:?--profile 뒤에 local 또는 dev가 필요합니다}"; shift 2 ;;
    -h | --help) sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "오류: 'uv' 명령이 없습니다. 먼저 ./scripts/setup-ubuntu.sh(우분투)를 실행하세요." >&2
  exit 1
fi
case "$PROFILE" in
  local) ENV_FILE=.env ;;
  dev) ENV_FILE=.env.dev ;;
  product) echo "오류: product는 로컬에서 띄우지 않습니다(마이그레이션·배포는 서버의 deploy.sh로만)." >&2; exit 2 ;;
  *) echo "오류: 알 수 없는 프로파일 '$PROFILE' (local 또는 dev)" >&2; exit 2 ;;
esac
if [[ ! -d "$ROOT/backend/.venv" ]]; then
  echo "오류: backend/.venv가 없습니다. 먼저 ./scripts/setup-ubuntu.sh(우분투)를 실행하세요." >&2
  exit 1
fi
if [[ ! -f "$ROOT/backend/$ENV_FILE" ]]; then
  if [[ "$PROFILE" == local ]]; then
    echo "오류: backend/.env가 없습니다. 먼저 ./scripts/setup-ubuntu.sh(우분투)를 실행하세요." >&2
  else
    echo "오류: backend/${ENV_FILE} 파일이 없습니다. backend/.env.example을 복사해 APP_PROFILE=${PROFILE} 설정과 접속 정보를 넣으세요." >&2
  fi
  exit 1
fi
# alembic과 uvicorn이 같은 환경을 물려받는다. 환경변수가 파일 값보다 우선하므로 파일 안의 APP_PROFILE은 무시되고
# --profile 값이 쓰인다. 셸에 미리 export한 APP_* 값(예: APP_DATABASE_URL)도 파일보다 우선하니 주의한다.
export APP_PROFILE="$PROFILE" APP_ENV_FILE="$ENV_FILE"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "오류: backend가 이미 실행 중입니다(PID $(cat "$PID_FILE")). 종료: kill $(cat "$PID_FILE")" >&2
  exit 1
fi
mkdir -p "$LOG_DIR"

cd "$ROOT/backend"
if [[ "$SKIP_MIGRATE" != true ]]; then
  echo "==> DB 스키마 적용 (profile: $PROFILE, alembic upgrade head)"
  uv run alembic upgrade head
fi

printf '\n===== %s backend 시작 (profile: %s, port: %s) =====\n' "$(date '+%F %T')" "$PROFILE" "$PORT" >>"$LOG_FILE"
# uv run을 거치지 않고 .venv의 uvicorn을 직접 띄워 PID가 서버 프로세스를 가리키게 한다(kill로 바로 종료)
nohup .venv/bin/uvicorn app.main:app --reload --port "$PORT" --app-dir src >>"$LOG_FILE" 2>&1 </dev/null &
echo $! >"$PID_FILE"

sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "오류: backend가 시작 직후 종료되었습니다. 로그 끝부분:" >&2
  tail -n 20 "$LOG_FILE" >&2
  exit 1
fi
echo "==> backend 시작(profile: $PROFILE, $ENV_FILE): http://localhost:$PORT (API 문서 /docs, 상태 /readyz)"
echo "    PID $(cat "$PID_FILE") · 로그: tail -f logs/backend.log · 종료: kill \$(cat logs/backend.pid)"
