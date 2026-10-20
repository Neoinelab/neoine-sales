#!/usr/bin/env bash
# frontend 개발 서버를 백그라운드(nohup)로 실행(Vite, http://localhost:5173). /api 요청은 localhost:8000의 backend로 전달된다.
# 터미널을 닫아도 계속 돌고, 출력은 logs/frontend.log(이어 쓰기), PID는 logs/frontend.pid에 남는다.
# backend는 ./scripts/start-backend.sh로 따로 띄운다.
# 사용: ./scripts/start-frontend.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/frontend.log"
PID_FILE="$LOG_DIR/frontend.pid"
case "${1:-}" in
  "") ;;
  -h | --help) sed -n '2,5p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
esac

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
nohup ./node_modules/.bin/vite >>"$LOG_FILE" 2>&1 </dev/null &
echo $! >"$PID_FILE"

sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "오류: frontend가 시작 직후 종료되었습니다. 로그 끝부분:" >&2
  tail -n 20 "$LOG_FILE" >&2
  exit 1
fi
echo "==> frontend 시작: http://localhost:5173"
echo "    PID $(cat "$PID_FILE") · 로그: tail -f logs/frontend.log · 종료: kill \$(cat logs/frontend.pid)"
