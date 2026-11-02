#!/usr/bin/env bash
# infra/docker/deploy.sh 동작 테스트. 실제 docker·서버·네트워크 없이 임시 디렉터리와 가짜 명령(docker, curl, sleep)으로
# 검증한다. 가짜 docker는 모든 호출을 기록하고 FAKE_* 환경변수로 단계별 실패를 낸다.
#   실행: bash infra/docker/tests/test_deploy.sh   (macOS 기본 /bin/bash 3.2에서도, bash 5에서도 통과해야 한다)
#   계획: artifacts/10-analysis/docker-compose-plan.md (D6·D8, AC4·AC6·AC7·AC8, T-DEP-1~16)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEPLOY="${DEPLOY_SCRIPT:-$HERE/../deploy.sh}"
TEST_BASH="${BASH:-/bin/bash}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILURES=0
CASES=0
SECRET_MARK="SECRETMARK_7f3a91"
REGISTRY_HOST="registry.example.com"

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (기대 '$2', 실제 '$3')"; fi; }

# 케이스마다 새 서버 디렉터리와 가짜 명령 모음을 만든다
new_case() {
  CASES=$((CASES + 1))
  TMP="$(mktemp -d "$WORK/case.XXXXXX")"
  APP="$TMP/app"; BIN="$TMP/bin"; LOG="$TMP/calls.log"
  mkdir -p "$APP/incoming" "$APP/deploys" "$APP/backups" "$APP/certs" "$BIN" "$TMP/home"
  : > "$LOG"
  {
    echo "APP_PROFILE=product"
    echo "APP_JWT_SECRET=${SECRET_MARK}_jwt"
    echo "APP_SETTINGS_ENCRYPTION_KEY=${SECRET_MARK}_key"
    echo "POSTGRES_USER=neoine"
    echo "POSTGRES_PASSWORD=${SECRET_MARK}_pw"
    echo "POSTGRES_DB=neoinesales"
    echo "APP_DATABASE_URL=postgresql+asyncpg://neoine:${SECRET_MARK}_pw@db:5432/neoinesales"
  } > "$APP/.env"
  chmod 600 "$APP/.env"
  write_deploy_env "APP_PROFILE=product" "REGISTRY=$REGISTRY_HOST"

  # 가짜 docker: compose의 동사(pull/run/up/exec/down)를 찾아 FAKE_*에 따라 실패시킨다
  cat > "$BIN/docker" <<'STUB'
#!/usr/bin/env bash
echo "docker $*" >> "$CALLS_LOG"
[ "${1:-}" = compose ] || exit 0
verb=""
for a in "$@"; do
  case "$a" in pull|run|up|exec|down|ps|config|logs) verb="$a"; break ;; esac
done
all="$*"
case "$verb" in
  pull) [ -z "${FAKE_PULL_FAIL:-}" ] || { echo "pull failed (fake)" >&2; exit 1; } ;;
  run)
    case "$all" in
      *get_settings*) [ -z "${FAKE_CONFIG_FAIL:-}" ] || { echo "settings invalid (fake)" >&2; exit 1; } ;;
      *) [ -z "${FAKE_MIGRATE_FAIL:-}" ] || { echo "migration failed (fake)" >&2; exit 1; } ;;
    esac ;;
  exec)
    case "$all" in
      *pg_dump*) printf 'DUMPDATA'; [ -z "${FAKE_DUMP_FAIL:-}" ] || exit 1 ;;
    esac ;;
  up)
    case "$all" in
      *" db") ;;
      *) if [ -n "${FAKE_UP_FAIL_TAG:-}" ]; then
           case "$all" in *"/deploys/$FAKE_UP_FAIL_TAG/"*) echo "up failed (fake)" >&2; exit 1 ;; esac
         fi ;;
    esac ;;
esac
exit 0
STUB
  cat > "$BIN/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >> "$CALLS_LOG"
[ -z "${FAKE_HEALTH_FAIL:-}" ]
STUB
  printf '#!/usr/bin/env bash\nexit 0\n' > "$BIN/sleep"
  chmod +x "$BIN"/*
}

write_deploy_env() { # write_deploy_env <줄>...
  : > "$APP/deploy.env"
  local l
  for l in "$@"; do echo "$l" >> "$APP/deploy.env"; done
  chmod 640 "$APP/deploy.env"
}

# 배포 키트를 만든다: make_kit <태그>  (compose.yaml, deploy.sh 두 파일)
make_kit() {
  local tag="$1" src="$TMP/kit-$1"
  mkdir -p "$src"
  printf 'name: neoine-sales\nservices: {}\n# kit %s\n' "$tag" > "$src/compose.yaml"
  printf '#!/usr/bin/env bash\n# kit %s\n' "$tag" > "$src/deploy.sh"
  tar -czf "$APP/incoming/deploy-$tag.tar.gz" -C "$src" compose.yaml deploy.sh
}

# run_deploy <환경> <태그> [옵션 또는 NAME=값 ...]
run_deploy() {
  local env_name="$1" tag="$2" x; shift 2
  local envs=() opts=()
  for x in "$@"; do
    case "$x" in *=*) envs+=("$x") ;; *) opts+=("$x") ;; esac
  done
  env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" \
      HEALTH_RETRIES=3 HEALTH_INTERVAL=0 WAIT_TIMEOUT=7 ${envs[@]+"${envs[@]}"} \
      "$TEST_BASH" "$DEPLOY" "$env_name" "$tag" ${opts[@]+"${opts[@]}"} > "$TMP/out.log" 2>&1
}
deploy_ok() { make_kit "$1"; run_deploy product "$1" || { fail "준비 배포 실패: $1 ($(tail -3 "$TMP/out.log" | tr '\n' ' '))"; return 1; }; }

current_tag() { basename "$(readlink -f "$APP/current" 2>/dev/null)"; }
log_has()  { grep -Eq -- "$1" "$LOG"; }
log_none() { ! grep -Eq -- "$1" "$LOG"; }
log_empty() { [ ! -s "$LOG" ]; }
log_count() { grep -Ec -- "$1" "$LOG" || true; }
ups_non_db() { grep -E ' up ' "$LOG" | grep -vcE ' db$' || true; }
log_line() { grep -En -m1 -- "$1" "$LOG" | cut -d: -f1; }
log_ordered() {
  local prev=0 cur pat
  for pat in "$@"; do
    cur="$(log_line "$pat")"
    [ -n "$cur" ] || { echo "    로그에 없음: $pat" >&2; return 1; }
    [ "$cur" -gt "$prev" ] || { echo "    순서 어긋남: $pat" >&2; return 1; }
    prev="$cur"
  done
}

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"
[ -f "$DEPLOY" ] || fail "infra/docker/deploy.sh가 없음(구현 전: red)"

echo "T-DEP-1 정상 배포(AC6)"
new_case; make_kit aaaa11112222
run_deploy product aaaa11112222; rc=$?
eq "종료 코드 0" "0" "$rc"
eq "current가 새 배포를 가리킴" "aaaa11112222" "$(current_tag)"
check "배포 디렉터리에 compose.yaml" test -f "$APP/deploys/aaaa11112222/compose.yaml"
check "배포 디렉터리에 deploy.sh" test -f "$APP/deploys/aaaa11112222/deploy.sh"
check "image.env에 IMAGE_TAG" grep -qx 'IMAGE_TAG=aaaa11112222' "$APP/deploys/aaaa11112222/image.env"
DUMP="$(ls "$APP"/backups/pre-aaaa11112222-*.dump 2>/dev/null | head -1)"
check "덤프 파일이 만들어짐(pre-<태그>-<시각>.dump)" test -n "$DUMP"
check "덤프 내용은 pg_dump 출력" grep -q DUMPDATA "${DUMP:-/nonexistent}"
check ".partial 파일이 남지 않음" bash -c "! ls '$APP'/backups/*.partial >/dev/null 2>&1"

echo "T-DEP-2 실행 순서(AC6)"
new_case; make_kit bbbb11112222
run_deploy product bbbb11112222
check "순서: pull -> 설정 검증 -> db 기동 -> 덤프 -> migrate -> 전환 -> 헬스체크" \
  log_ordered ' pull api web db$' 'run .*--no-deps.*get_settings' ' up -d --wait db$' 'exec -T db .*pg_dump' \
  '--profile migrate run --rm migrate' ' up -d --wait .*--remove-orphans' '^curl '
check "전환 up에 --wait-timeout(WAIT_TIMEOUT) 사용" log_has ' up -d --wait --wait-timeout 7 '
check "설정 검증은 api 서비스를 --entrypoint python으로 실행" log_has 'run .*--entrypoint python api -c'
check "헬스체크는 web을 거친 https://127.0.0.1/readyz" log_has '^curl .*https://127\.0\.0\.1/readyz'
check "헬스체크는 인증서 이름 확인만 끔(--insecure)" log_has '^curl .*(--insecure|-k)'

echo "T-DEP-3 pull 실패: 종료 2, 이후 호출 없음, 실행 중인 버전 유지(AC6)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_PULL_FAIL=1; rc=$?
eq "종료 코드 2" "2" "$rc"
check "pull 이후 호출 없음(검증·db·덤프·migrate·전환·헬스체크)" log_none ' run | up | exec |^curl '
eq "current 그대로" "aaaa00000001" "$(current_tag)"

echo "T-DEP-4 설정 검증 실패: 종료 3, db 기동·덤프·migrate·전환 없음(AC6)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_CONFIG_FAIL=1; rc=$?
eq "종료 코드 3" "3" "$rc"
check "up·exec·migrate·헬스체크 호출 없음" log_none ' up | exec |--profile migrate|^curl '
eq "current 그대로" "aaaa00000001" "$(current_tag)"

echo "T-DEP-5 덤프 실패: 종료 4, migrate·전환 없음, .partial 정리(AC6)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_DUMP_FAIL=1; rc=$?
eq "종료 코드 4" "4" "$rc"
check "db는 기동했고 덤프를 시도함" log_ordered ' up -d --wait db$' 'exec -T db .*pg_dump'
check "migrate 없음" log_none '--profile migrate'
eq "전환 up 없음" "0" "$(ups_non_db)"
check ".partial 파일이 남지 않음" bash -c "! ls '$APP'/backups/*.partial >/dev/null 2>&1"
check "이 배포의 덤프 파일이 없음" bash -c "! ls '$APP'/backups/pre-aaaa00000002-*.dump >/dev/null 2>&1"
eq "current 그대로" "aaaa00000001" "$(current_tag)"

echo "T-DEP-6 migrate 실패(이전 배포 있음): 전환하지 않음(AC6)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_MIGRATE_FAIL=1; rc=$?
check "종료 코드가 0이 아님" test "$rc" -ne 0
eq "전환 up 없음" "0" "$(ups_non_db)"
eq "current가 이전 배포" "aaaa00000001" "$(current_tag)"

echo "T-DEP-7 헬스체크 실패(이전 있음): 이전 태그로 롤백, migrate·덤프 재실행 없음(AC7)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_HEALTH_FAIL=1; rc=$?
eq "종료 코드 1" "1" "$rc"
eq "current가 이전 배포로 돌아감" "aaaa00000001" "$(current_tag)"
check "헬스체크를 HEALTH_RETRIES(3)번 이상 시도" test "$(log_count '^curl ')" -ge 3
LAST_UP="$(grep -E ' up ' "$LOG" | grep -vE ' db$' | tail -1)"
case "$LAST_UP" in *"/deploys/aaaa00000001/compose.yaml"*) ok "롤백 up은 이전 compose 파일" ;; *) fail "롤백 up은 이전 compose 파일 ($LAST_UP)" ;; esac
case "$LAST_UP" in *"/deploys/aaaa00000001/image.env"*) ok "롤백 up은 이전 image.env" ;; *) fail "롤백 up은 이전 image.env ($LAST_UP)" ;; esac
case "$LAST_UP" in *"/deploys/aaaa00000002/"*) fail "롤백 up이 새 배포를 가리킴" ;; *) ok "롤백 up이 새 배포를 가리키지 않음" ;; esac
check "롤백 때 이전 태그 이미지를 다시 pull" bash -c "grep -E ' pull ' '$LOG' | tail -1 | grep -q '/deploys/aaaa00000001/'"
eq "덤프는 새 배포의 1회뿐" "1" "$(log_count 'pg_dump')"
eq "migrate는 새 배포의 1회뿐" "1" "$(log_count '--profile migrate run')"
eq "db 기동은 새 배포의 1회뿐" "1" "$(log_count ' up -d --wait db$')"

echo "T-DEP-8 up --wait 실패(이전 있음): T-DEP-7과 같은 롤백(AC7)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_UP_FAIL_TAG=aaaa00000002; rc=$?
eq "종료 코드 1" "1" "$rc"
eq "current가 이전 배포" "aaaa00000001" "$(current_tag)"
LAST_UP="$(grep -E ' up ' "$LOG" | grep -vE ' db$' | tail -1)"
case "$LAST_UP" in *"/deploys/aaaa00000001/"*) ok "마지막 up이 이전 배포" ;; *) fail "마지막 up이 이전 배포 ($LAST_UP)" ;; esac
eq "migrate는 1회뿐" "1" "$(log_count '--profile migrate run')"
eq "덤프는 1회뿐" "1" "$(log_count 'pg_dump')"

echo "T-DEP-9 첫 배포(이전 없음) 헬스체크 실패: 종료 1, 컨테이너를 내리지 않음(AC7)"
new_case; make_kit aaaa00000001
run_deploy product aaaa00000001 FAKE_HEALTH_FAIL=1; rc=$?
eq "종료 코드 1" "1" "$rc"
check "down 호출 없음(진단용으로 그대로 둠)" log_none ' down'
eq "전환 up은 1회뿐(롤백 up 없음)" "1" "$(ups_non_db)"

echo "T-DEP-10 --no-migrate: 덤프·migrate 건너뛰고 pull·검증·전환·헬스체크는 실행(AC7)"
new_case; deploy_ok aaaa00000001; deploy_ok aaaa00000002; : > "$LOG"
run_deploy product aaaa00000001 --no-migrate; rc=$?
eq "종료 코드 0" "0" "$rc"
check "덤프·migrate·db 단독 기동 없음" log_none 'pg_dump|--profile migrate| up -d --wait db$'
check "pull·설정 검증·전환·헬스체크는 실행" log_ordered ' pull ' 'get_settings' ' up -d --wait .*--remove-orphans' '^curl '
eq "current가 옛 태그로 돌아감" "aaaa00000001" "$(current_tag)"
echo "  (키트가 지워졌고 deploys/<태그>만 남은 경우)"
rm -f "$APP/incoming/deploy-aaaa00000002.tar.gz"; : > "$LOG"
run_deploy product aaaa00000002 --no-migrate; rc=$?
eq "배포 디렉터리가 남아 있으면 키트 없이도 종료 0" "0" "$rc"
eq "current가 그 태그" "aaaa00000002" "$(current_tag)"

echo "T-DEP-11 사전 조건 위반: 종료 2, docker 호출 없음(AC6)"
new_case; make_kit cccc00000001
sed 's/^APP_PROFILE=.*/APP_PROFILE=dev/' "$APP/.env" > "$APP/.env.t" && mv "$APP/.env.t" "$APP/.env"
run_deploy product cccc00000001; rc=$?
eq ".env의 APP_PROFILE이 product가 아님: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
check "메시지에 APP_PROFILE" grep -q APP_PROFILE "$TMP/out.log"
new_case; make_kit cccc00000001; write_deploy_env "APP_PROFILE=dev" "REGISTRY=$REGISTRY_HOST"
run_deploy product cccc00000001; rc=$?
eq "deploy.env의 APP_PROFILE이 product가 아님: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
new_case; make_kit cccc00000001; write_deploy_env "APP_PROFILE=product"
run_deploy product cccc00000001; rc=$?
eq "REGISTRY 줄 없음: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
new_case; make_kit cccc00000001; write_deploy_env "APP_PROFILE=product" "REGISTRY="
run_deploy product cccc00000001; rc=$?
eq "REGISTRY가 비어 있음: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
new_case; make_kit cccc00000001; write_deploy_env "APP_PROFILE=product" "REGISTRY=CHANGE_ME"
run_deploy product cccc00000001; rc=$?
eq "REGISTRY가 CHANGE_ME: 종료 2" "2" "$rc"; check "docker 호출 없음(pull 포함)" log_empty
check "메시지에 REGISTRY" grep -q REGISTRY "$TMP/out.log"
new_case; make_kit cccc00000001; rm "$APP/.env"
run_deploy product cccc00000001; rc=$?
eq ".env 없음: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
check "배포 디렉터리를 만들지 않음" test ! -e "$APP/deploys/cccc00000001"

echo "T-DEP-12 잘못된 입력: 종료 2, docker 호출 없음(AC6)"
new_case; make_kit dddd00000001
for bad in "dev dddd00000001" "staging dddd00000001" "product ../etc" "product a;rm" "product -x" "product dddd00000001 --force"; do
  : > "$LOG"
  set -f
  # shellcheck disable=SC2086
  env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" "$TEST_BASH" "$DEPLOY" $bad > "$TMP/out.log" 2>&1; rc=$?
  set +f
  eq "종료 2: $bad" "2" "$rc"
  check "docker 호출 없음: $bad" log_empty
done
: > "$LOG"
env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" "$TEST_BASH" "$DEPLOY" > "$TMP/out.log" 2>&1; rc=$?
check "인자 없음: 종료 0이 아님" test "$rc" -ne 0
new_case
run_deploy product nokit0000001; rc=$?
check "키트도 배포 디렉터리도 없음: 종료 0이 아님" test "$rc" -ne 0
check "docker 호출 없음" log_empty
check "current가 만들어지지 않음" test ! -e "$APP/current"

echo "T-DEP-12b 줄바꿈이 섞인 태그는 거부(리뷰 Minor)"
new_case; make_kit dddd00000002
NL_TAG="$(printf 'abc\n../../x y')"
: > "$LOG"
env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" "$TEST_BASH" "$DEPLOY" product "$NL_TAG" > "$TMP/out.log" 2>&1; rc=$?
eq "줄바꿈 포함 태그: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty
NL_TAG2="$(printf 'dddd00000002\nx')"
cp "$APP/incoming/deploy-dddd00000002.tar.gz" "$APP/incoming/deploy-$NL_TAG2.tar.gz"   # 검증이 없으면 키트를 찾아 docker까지 가도록
env APP_HOME="$APP" PATH="$BIN:$PATH" HOME="$TMP/home" CALLS_LOG="$LOG" "$TEST_BASH" "$DEPLOY" product "$NL_TAG2" > "$TMP/out.log" 2>&1; rc=$?
eq "유효한 줄 뒤에 줄이 붙은 태그: 종료 2" "2" "$rc"; check "docker 호출 없음" log_empty

echo "T-DEP-13 모든 compose 호출의 공통 인자(AC4)"
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_HEALTH_FAIL=1   # 롤백 경로까지 포함
bad=0; n=0
while IFS= read -r line; do
  case "$line" in "docker compose "*) ;; *) continue ;; esac
  n=$((n + 1))
  case "$line" in *" -p neoine-sales "*) ;; *) echo "    -p neoine-sales 없음: $line" >&2; bad=$((bad + 1)) ;; esac
  case "$line" in *"--project-directory $APP "*|*"--project-directory $APP") echo "    project-directory가 APP_HOME: $line" >&2; bad=$((bad + 1)) ;; esac
  echo "$line" | grep -Eq -- "--project-directory [^ ]*/deploys/[^ /]+( |$)" || { echo "    project-directory가 배포 디렉터리가 아님: $line" >&2; bad=$((bad + 1)); }
  echo "$line" | grep -Eq -- "--env-file $APP/deploy\.env( |$)" || { echo "    deploy.env 없음: $line" >&2; bad=$((bad + 1)); }
  echo "$line" | grep -Eq -- "--env-file [^ ]*/deploys/[^ /]+/image\.env( |$)" || { echo "    image.env 없음: $line" >&2; bad=$((bad + 1)); }
  echo "$line" | grep -Eq -- "-f [^ ]*/deploys/[^ /]+/compose\.yaml( |$)" || { echo "    compose.yaml 경로 아님: $line" >&2; bad=$((bad + 1)); }
done < "$LOG"
check "compose 호출이 하나 이상 있음" test "$n" -gt 0
eq "모든 compose 호출이 공통 인자를 가짐" "0" "$bad"
check "앱 .env를 compose --env-file로 넘기지 않음" log_none '--env-file [^ ]*/\.env( |$)'

echo "T-DEP-14 비밀 값이 출력·docker 인자 기록에 나오지 않음(AC4)"
new_case; make_kit aaaa00000001; run_deploy product aaaa00000001
OUTS="$(cat "$TMP/out.log")"; ARGS="$(cat "$LOG")"
case "$OUTS$ARGS" in *"$SECRET_MARK"*) fail "정상 경로에 비밀 표식이 있음" ;; *) ok "정상 경로: 출력·인자에 비밀 없음" ;; esac
new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
run_deploy product aaaa00000002 FAKE_HEALTH_FAIL=1
OUTS="$(cat "$TMP/out.log")"; ARGS="$(cat "$LOG")"
case "$OUTS$ARGS" in *"$SECRET_MARK"*) fail "롤백 경로에 비밀 표식이 있음" ;; *) ok "롤백 경로: 출력·인자에 비밀 없음" ;; esac
for inj in FAKE_PULL_FAIL=1 FAKE_CONFIG_FAIL=1 FAKE_DUMP_FAIL=1 FAKE_MIGRATE_FAIL=1; do
  new_case; deploy_ok aaaa00000001; make_kit aaaa00000002; : > "$LOG"
  run_deploy product aaaa00000002 "$inj"
  OUTS="$(cat "$TMP/out.log")"; ARGS="$(cat "$LOG")"
  case "$OUTS$ARGS" in *"$SECRET_MARK"*) fail "$inj 경로에 비밀 표식이 있음" ;; *) ok "$inj 경로: 출력·인자에 비밀 없음" ;; esac
done

echo "T-DEP-15 같은 태그 재배포는 안전(멱등)(AC8)"
new_case; deploy_ok aaaa00000001
echo marker > "$APP/deploys/aaaa00000001/keep.txt"
run_deploy product aaaa00000001; rc=$?
eq "종료 코드 0" "0" "$rc"
check "기존 배포 디렉터리 파일이 그대로 남음" test -f "$APP/deploys/aaaa00000001/keep.txt"
eq "current 유지" "aaaa00000001" "$(current_tag)"
check "image.env 유지" grep -qx 'IMAGE_TAG=aaaa00000001' "$APP/deploys/aaaa00000001/image.env"

echo "T-DEP-16 정리: 배포 디렉터리 최근 5개, 덤프 최근 10개, 오래된 키트(AC8)"
new_case
for n in 1 2 3 4 5 6 7; do
  deploy_ok "t0000000$n"
  touch -t "20260101000$n" "$APP/deploys/t0000000$n" 2>/dev/null || true
done
count="$(ls -1d "$APP"/deploys/*/ | wc -l | tr -d ' ')"
check "배포 디렉터리 수가 보관 한도(5) 이하" test "$count" -le 5
check "현재 배포가 남아 있음" test -d "$APP/deploys/t00000007"
check "직전 배포가 남아 있음" test -d "$APP/deploys/t00000006"
check "지워진 가장 오래된 태그의 api 이미지를 제거" log_has 'image rm .*/neoine-sales/api:t00000001'
check "지워진 가장 오래된 태그의 web 이미지를 제거" log_has 'image rm .*/neoine-sales/web:t00000001'
check "현재·직전 이미지는 제거하지 않음" log_none 'image rm .*:t0000000[67]$'
new_case
for n in 01 02 03 04 05 06 07 08 09 10 11 12; do
  f="$APP/backups/pre-old$n-202001010000${n}Z.dump"
  echo old > "$f"; touch -t "2020010100$n" "$f" 2>/dev/null || true
done
make_kit zz000000001; run_deploy product zz000000001 KEEP_BACKUPS=10; rc=$?
eq "종료 코드 0" "0" "$rc"
eq "덤프가 10개로 줄어듦" "10" "$(ls -1 "$APP"/backups/*.dump | wc -l | tr -d ' ')"
check "이번 배포의 덤프는 남음" bash -c "ls '$APP'/backups/pre-zz000000001-*.dump >/dev/null 2>&1"
check "가장 오래된 덤프가 지워짐" test ! -e "$APP/backups/pre-old01-20200101000001Z.dump"
check "새 쪽 덤프는 남음" test -e "$APP/backups/pre-old12-20200101000012Z.dump"
new_case
echo old > "$APP/incoming/deploy-ancient0001.tar.gz"; touch -t 202001010000 "$APP/incoming/deploy-ancient0001.tar.gz"
deploy_ok recent0000001
check "14일이 지난 키트는 지워짐" test ! -e "$APP/incoming/deploy-ancient0001.tar.gz"
check "이번 키트는 남음" test -e "$APP/incoming/deploy-recent0000001.tar.gz"

echo "T-DEP-17 정적 확인"
if [ -f "$DEPLOY" ]; then
  check "bash -n" "$TEST_BASH" -n "$DEPLOY"
  BODY_FILE="$WORK/deploy.body"; grep -v '^[[:space:]]*#' "$DEPLOY" > "$BODY_FILE"
  check "sudo를 쓰지 않음(neoine 계정으로 실행)" bash -c "! grep -Eq '(^|[[:space:];&|])sudo ' '$BODY_FILE'"
  check "systemctl을 쓰지 않음" bash -c "! grep -q systemctl '$BODY_FILE'"
  check "uv·alembic을 호스트에서 직접 실행하지 않음" bash -c "! grep -Eq '(^|[[:space:];&|])(uv|alembic) ' '$BODY_FILE'"
  for pat in 'declare -A' 'mapfile' 'readarray' ',,}' '^^}' 'declare -n'; do
    if grep -Fq -e "$pat" "$BODY_FILE"; then fail "bash 3.2 비호환 구문 '$pat'"; else ok "'$pat' 없음"; fi
  done
else
  fail "deploy.sh 없음(구현 전: red)"
fi

echo
echo "$CASES 케이스, 실패 $FAILURES"
[ "$FAILURES" -eq 0 ]
