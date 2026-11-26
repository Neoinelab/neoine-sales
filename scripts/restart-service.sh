#!/usr/bin/env bash
set -euo pipefail

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
service=$1
port=$2
shift 2
signal=TERM
start_args=()

if [[ ${1:-} == now ]]; then
  signal=KILL
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$service:$1" in
    *:-h|*:--help)
      echo "사용: restart-$service.sh [now] [시작 옵션]"
      exec "$scripts_dir/start-$service.sh" --help
      ;;
    backend:--skip-migrate)
      start_args+=("$1")
      shift
      ;;
    backend:--port|backend:--profile|frontend:--host|frontend:--allow-host)
      if [[ $# -lt 2 || -z $2 || $2 == -* ]]; then
        echo "오류: $1 옵션의 값을 지정하세요." >&2
        exit 2
      fi
      case "$1" in
        --port)
          if [[ ! $2 =~ ^[0-9]{1,5}$ ]] || (( 10#$2 < 1 || 10#$2 > 65535 )); then
            echo "오류: 포트는 1~65535 사이여야 합니다." >&2
            exit 2
          fi
          port=$((10#$2))
          start_args+=("$1" "$port")
          shift 2
          continue
          ;;
        --profile)
          if [[ $2 != local && $2 != dev ]]; then
            echo "오류: --profile은 local 또는 dev만 지원합니다." >&2
            exit 2
          fi
          ;;
      esac
      start_args+=("$1" "$2")
      shift 2
      ;;
    *)
      echo "오류: 알 수 없는 옵션: $1" >&2
      exit 2
      ;;
  esac
done

if ! command -v lsof >/dev/null; then
  echo "오류: TCP 포트 확인에 lsof가 필요합니다." >&2
  exit 1
fi

listeners() {
  local output status=0
  output=$(lsof -nP -a -iTCP:"$port" -sTCP:LISTEN -t 2>&1) || status=$?
  if [[ $status == 1 && -z $output ]]; then
    return 0
  fi
  if [[ $status != 0 || ! $output =~ ^[0-9]+($'\n'[0-9]+)*$ ]]; then
    echo "오류: TCP $port 리스너를 확인하지 못했습니다." >&2
    return 1
  fi
  printf '%s\n' "$output"
}

pids=$(listeners)
tracked_pid=
pid_file="$scripts_dir/../logs/$service.pid"
if [[ -f $pid_file ]]; then
  tracked_pid=$(< "$pid_file")
  if [[ ! $tracked_pid =~ ^[1-9][0-9]*$ ]] || ! kill -0 "$tracked_pid" 2>/dev/null; then
    tracked_pid=
  elif [[ $'\n'$pids$'\n' != *$'\n'"$tracked_pid"$'\n'* ]]; then
    echo "오류: 기록된 $service 프로세스($tracked_pid)가 TCP $port 리스너에 없습니다." >&2
    exit 1
  fi
fi

while IFS= read -r pid; do
  [[ -n $pid ]] || continue
  echo "==> TCP $port PID $pid 종료 (SIG$signal)"
  if ! kill -s "$signal" "$pid" 2>/dev/null; then
    remaining=$(listeners)
    if [[ $'\n'$remaining$'\n' == *$'\n'"$pid"$'\n'* ]]; then
      echo "오류: PID $pid 에 종료 신호를 보내지 못했습니다." >&2
      exit 1
    fi
  fi
done <<< "$pids"

deadline=$((SECONDS + 60))
while true; do
  remaining=$(listeners)
  if [[ -z $remaining ]] && { [[ -z $tracked_pid ]] || ! kill -0 "$tracked_pid" 2>/dev/null; }; then
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "오류: 60초 안에 TCP $port 및 기존 $service 프로세스가 종료되지 않아 재시작을 중단합니다." >&2
    exit 1
  fi
  sleep 1
done

echo "==> TCP $port 종료 확인. $service 시작"
exec "$scripts_dir/start-$service.sh" ${start_args[@]+"${start_args[@]}"}
