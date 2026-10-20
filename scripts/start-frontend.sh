#!/usr/bin/env bash
# frontend 개발 서버를 백그라운드(nohup)로 실행(Vite, 포트 5173). /api 요청은 localhost:8000의 backend로 전달된다.
# 기본은 모든 주소(0.0.0.0)에서 받아 외부에서 http://<서버 IP>:5173 으로 접속할 수 있다. --host localhost면 이 PC에서만.
# IP가 아닌 호스트 이름으로 접속하려면 --allow-host <이름>(쉼표로 여러 개)을 준다(Vite가 모르는 호스트 이름은 거부).
# 터미널을 닫아도 계속 돌고, 출력은 logs/frontend.log(이어 쓰기), PID는 logs/frontend.pid에 남는다.
# backend는 ./scripts/start-backend.sh로 따로 띄운다.
# 사용: ./scripts/start-frontend.sh [--host 0.0.0.0] [--allow-host 이름[,이름]]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/frontend.log"
PID_FILE="$LOG_DIR/frontend.pid"
HOST=0.0.0.0
ALLOW_HOSTS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:?--host 뒤에 주소가 필요합니다(예: 0.0.0.0, localhost)}"; shift 2 ;;
    --allow-host) ALLOW_HOSTS="${2:?--allow-host 뒤에 호스트 이름이 필요합니다}"; shift 2 ;;
    -h | --help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "오류: frontend가 이미 실행 중입니다(PID $(cat "$PID_FILE")). 종료: kill $(cat "$PID_FILE")" >&2
  exit 1
fi
if ! command -v corepack >/dev/null 2>&1; then
  echo "오류: 'corepack' 명령이 없습니다. Node.js를 설치하세요." >&2
  exit 1
fi
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo "오류: frontend/node_modules가 없습니다. 먼저 ./scripts/setup-ubuntu.sh(우분투)를 실행하세요." >&2
  exit 1
fi

# corepack 서명 오류(Cannot find matching keyid)가 나는 환경이면 검증 키 확인을 끄고 실행한다.
if ! corepack pnpm --version >/dev/null 2>&1; then
  export COREPACK_INTEGRITY_KEYS=0
fi

if ! curl -fsS -o /dev/null --max-time 2 http://localhost:8000/readyz 2>/dev/null; then
  echo "참고: backend(localhost:8000)가 응답하지 않습니다. ./scripts/start-backend.sh를 먼저 띄우세요."
fi

mkdir -p "$LOG_DIR"
printf '\n===== %s frontend 시작 =====\n' "$(date '+%F %T')" >>"$LOG_FILE"
# pnpm dev(= vite)를 거치지 않고 vite를 직접 띄워 PID가 서버 프로세스를 가리키게 한다(kill로 바로 종료)
# 호스트 이름 허용 목록은 Vite가 읽는 환경변수로 넘긴다(DNS rebinding 방지 때문에 전체 허용(true)은 쓰지 않는다)
if [[ -n "$ALLOW_HOSTS" ]]; then
  export __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS="$ALLOW_HOSTS"
fi
nohup ./node_modules/.bin/vite --host "$HOST" >>"$LOG_FILE" 2>&1 </dev/null &
echo $! >"$PID_FILE"

sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "오류: frontend가 시작 직후 종료되었습니다. 로그 끝부분:" >&2
  tail -n 20 "$LOG_FILE" >&2
  exit 1
fi
echo "==> frontend 시작(host: $HOST): http://localhost:5173"
if [[ "$HOST" != localhost && "$HOST" != 127.0.0.1 ]]; then
  echo "    외부 접속: http://<이 서버 IP>:5173 (주소 목록은 로그의 Network 줄, 방화벽에서 5173 허용 필요)"
fi
echo "    PID $(cat "$PID_FILE") · 로그: tail -f logs/frontend.log · 종료: kill \$(cat logs/frontend.pid)"
