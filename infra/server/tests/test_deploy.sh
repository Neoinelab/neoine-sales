#!/usr/bin/env bash
# deploy.sh 동작 테스트. 실제 서버·네트워크 없이 임시 디렉터리와 가짜 명령(uv, curl, sudo)으로 검증한다.
#   실행: bash infra/server/tests/test_deploy.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEPLOY="$HERE/../deploy.sh"
FAILURES=0
CASES=0

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { # check <설명> <명령...>  (명령이 성공해야 통과)
  local what="$1"; shift
  if "$@"; then ok "$what"; else fail "$what"; fi
}

# 케이스마다 새 서버 디렉터리와 가짜 명령 모음을 만든다
new_case() {
  CASES=$((CASES + 1))
  TMP="$(mktemp -d)"
  APP="$TMP/app"
  BIN="$TMP/bin"
  LOG="$TMP/calls.log"
  mkdir -p "$APP/incoming" "$APP/releases" "$APP/shared" "$BIN"
  : > "$LOG"
  echo "APP_PROFILE=dev" > "$APP/.env"

  # 가짜 uv: sync하면 .venv/bin/{python,alembic,uvicorn} 가짜를 만든다(FAKE_*로 실패를 주입)
  cat > "$BIN/uv" <<'STUB'
#!/usr/bin/env bash
echo "uv $*" >> "$CALLS_LOG"
mkdir -p .venv/bin
cat > .venv/bin/python <<'PY'
#!/usr/bin/env bash
echo "python $*" >> "$CALLS_LOG"
[ -z "${FAKE_CONFIG_FAIL:-}" ]
PY
cat > .venv/bin/alembic <<'AL'
#!/usr/bin/env bash
echo "alembic $*" >> "$CALLS_LOG"
[ -z "${FAKE_MIGRATION_FAIL:-}" ]
AL
chmod +x .venv/bin/python .venv/bin/alembic
STUB
  # 가짜 curl: FAKE_HEALTH_FAIL이 있으면 실패
  cat > "$BIN/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >> "$CALLS_LOG"
[ -z "${FAKE_HEALTH_FAIL:-}" ]
STUB
  # 가짜 sudo: 명령을 기록만 하고 실행하지 않는다(systemctl restart)
  cat > "$BIN/sudo" <<'STUB'
#!/usr/bin/env bash
echo "sudo $*" >> "$CALLS_LOG"
STUB
  cat > "$BIN/sleep" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
  chmod +x "$BIN"/*
}

# 릴리스 번들을 만든다: make_bundle <태그>
make_bundle() {
  local tag="$1"
  local src="$TMP/src/neoine-sales-$tag"
  mkdir -p "$src/backend" "$src/frontend/dist" "$src/infra/server/config"
  echo "$tag" > "$src/VERSION"
  echo '<html></html>' > "$src/frontend/dist/index.html"
  echo '{"profile":"dev"}' > "$src/infra/server/config/config.dev.json"
  echo '{"profile":"product"}' > "$src/infra/server/config/config.product.json"
  tar -czf "$APP/incoming/neoine-sales-$tag.tar.gz" -C "$TMP/src" "neoine-sales-$tag"
}

run_deploy() { # run_deploy <env> <tag> [환경변수=값...]
  local env_name="$1" tag="$2"; shift 2
  env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" \
      HEALTH_RETRIES=3 HEALTH_INTERVAL=0 "$@" bash "$DEPLOY" "$env_name" "$tag" > "$TMP/out.log" 2>&1
}

current_tag() { basename "$(readlink -f "$APP/current" 2>/dev/null)"; }
called() { grep -q "$1" "$LOG"; }
count_calls() { grep -c "$1" "$LOG" || true; }
cleanup() { rm -r "$TMP"; }

echo "[1] 정상 배포: 번들 풀기, 설정 검증, 마이그레이션, 전환, 재시작"
new_case; make_bundle aaaa11112222
run_deploy dev aaaa11112222; rc=$?
check "종료 코드 0" [ "$rc" -eq 0 ]
check "current가 새 릴리스를 가리킴" [ "$(current_tag)" = "aaaa11112222" ]
check "uv sync가 --locked --no-dev --no-editable로 실행됨" called "uv sync --locked --no-dev --no-editable"
check "설정 사전 검증이 실행됨" called "python -c from app.config import get_settings"
check "alembic upgrade head가 실행됨" called "alembic -c .*alembic.ini upgrade head"
check "서비스가 한 번 재시작됨" [ "$(count_calls 'sudo systemctl restart neoine-sales-api')" -eq 1 ]
check "프런트 런타임 설정이 설치됨" grep -q '"dev"' "$APP/shared/config.json"
cleanup

echo "[2] 마이그레이션은 전환보다 먼저, 설정 검증은 마이그레이션보다 먼저"
new_case; make_bundle bbbb11112222
run_deploy dev bbbb11112222
order="$(grep -n "python -c\|alembic\|systemctl" "$LOG" | cut -d: -f2 | awk '{print $1}' | tr '\n' ' ')"
check "순서: python(검증) -> alembic -> sudo(재시작)" [ "$order" = "python alembic sudo " ]
cleanup

echo "[3] 이미 실행 중인 릴리스가 있으면 헬스체크 실패 시 이전 릴리스로 롤백"
new_case; make_bundle cccc11112222; make_bundle dddd11112222
run_deploy dev cccc11112222
run_deploy dev dddd11112222 FAKE_HEALTH_FAIL=1; rc=$?
check "종료 코드 1" [ "$rc" -eq 1 ]
check "current가 이전 릴리스로 돌아감" [ "$(current_tag)" = "cccc11112222" ]
check "롤백 때 서비스를 다시 재시작함(총 3회)" [ "$(count_calls 'sudo systemctl restart neoine-sales-api')" -eq 3 ]
cleanup

echo "[4] 설정 검증이 실패하면 마이그레이션·전환 전에 중단"
new_case; make_bundle eeee11112222
run_deploy dev eeee11112222 FAKE_CONFIG_FAIL=1; rc=$?
check "종료 코드가 0이 아님" [ "$rc" -ne 0 ]
check "alembic이 실행되지 않음" [ "$(count_calls alembic)" -eq 0 ]
check "current가 만들어지지 않음" [ ! -e "$APP/current" ]
check "재시작하지 않음" [ "$(count_calls systemctl)" -eq 0 ]
check "준비 완료 표시가 없어 다음에 다시 시도 가능" [ ! -f "$APP/releases/eeee11112222/.ready" ]
cleanup

echo "[5] 마이그레이션이 실패하면 전환하지 않음"
new_case; make_bundle ffff11112222; make_bundle 1111aaaa2222
run_deploy dev ffff11112222
run_deploy dev 1111aaaa2222 FAKE_MIGRATION_FAIL=1; rc=$?
check "종료 코드가 0이 아님" [ "$rc" -ne 0 ]
check "current가 이전 릴리스 그대로" [ "$(current_tag)" = "ffff11112222" ]
check "추가 재시작 없음(첫 배포의 1회뿐)" [ "$(count_calls 'sudo systemctl restart')" -eq 1 ]
cleanup

echo "[6] .env의 APP_PROFILE이 대상 환경과 다르면 아무것도 하지 않음"
new_case; make_bundle 2222aaaa3333
run_deploy product 2222aaaa3333; rc=$?
check "종료 코드가 0이 아님" [ "$rc" -ne 0 ]
check "릴리스 디렉터리를 만들지 않음" [ ! -e "$APP/releases/2222aaaa3333" ]
check "메시지에 APP_PROFILE이 나옴" grep -q "APP_PROFILE" "$TMP/out.log"
cleanup

echo "[7] 잘못된 입력은 거부"
new_case
run_deploy staging abc; check "알 수 없는 환경" [ $? -ne 0 ]
run_deploy dev "../etc"; check "경로가 섞인 태그" [ $? -ne 0 ]
run_deploy dev "a;rm"; check "특수문자가 섞인 태그" [ $? -ne 0 ]
run_deploy dev nobundle12345; check "번들이 없음" [ $? -ne 0 ]
cleanup

echo "[8] 같은 태그로 다시 배포해도 실행 중인 릴리스를 지우지 않음(멱등)"
new_case; make_bundle 3333aaaa4444
run_deploy dev 3333aaaa4444
echo marker > "$APP/releases/3333aaaa4444/keep.txt"
run_deploy dev 3333aaaa4444; rc=$?
check "종료 코드 0" [ "$rc" -eq 0 ]
check "기존 릴리스 파일이 그대로 남음" [ -f "$APP/releases/3333aaaa4444/keep.txt" ]
check "uv sync는 한 번만 실행됨" [ "$(count_calls 'uv sync')" -eq 1 ]
cleanup

echo "[9] 오래된 릴리스는 정리하되 현재와 직전 릴리스는 보관"
new_case
for n in 1 2 3 4 5 6 7; do make_bundle "rel0000000$n"; done
for n in 1 2 3 4 5 6 7; do
  run_deploy dev "rel0000000$n"
  touch -t "20260101000$n" "$APP/releases/rel0000000$n" 2>/dev/null || true
done
count="$(ls -1d "$APP"/releases/*/ | wc -l | tr -d ' ')"
check "릴리스 수가 보관 한도(5) 이하" [ "$count" -le 5 ]
check "현재 릴리스가 남아 있음" [ -d "$APP/releases/rel00000007" ]
check "직전 릴리스가 남아 있음" [ -d "$APP/releases/rel00000006" ]
cleanup

echo
if [ "$FAILURES" -eq 0 ]; then echo "모두 통과 (${CASES}개 시나리오)"; else echo "실패 ${FAILURES}건"; exit 1; fi
