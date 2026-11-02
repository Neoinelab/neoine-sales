#!/usr/bin/env bash
# infra/docker/build_images.sh 동작 테스트. 가짜 docker(호출 기록만)로 검증한다. 실제 이미지 빌드·push는 하지 않는다.
#   실행: bash infra/docker/tests/test_build_images.sh   (bash 3.2·5 모두)
#   계획: artifacts/10-analysis/docker-compose-plan.md (D10, AC2·AC4·AC5·AC9, T-BLD-1~5)
# 스크립트는 임시 저장소 사본(스크립트 위치 기준으로 저장소 루트를 찾음)에서 실행하고, 현재 디렉터리는 저장소 밖이다.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REAL_SCRIPT="${BUILD_SCRIPT:-$HERE/../build_images.sh}"
TEST_BASH="${BASH:-/bin/bash}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILURES=0
CASES=0
REG="registry.example.com"
TAG="abc123def456"

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (기대 '$2', 실제 '$3')"; fi; }

new_case() { # 임시 저장소 사본: 스크립트, dist, backend, 키트에 들어갈 compose.yaml·deploy.sh 더미
  CASES=$((CASES + 1))
  TMP="$(mktemp -d "$WORK/case.XXXXXX")"
  REPO="$TMP/repo"; BIN="$TMP/bin"; LOG="$TMP/calls.log"; CWD="$TMP/elsewhere"
  mkdir -p "$REPO/infra/docker/web" "$REPO/backend" "$REPO/frontend/dist" "$BIN" "$CWD"
  : > "$LOG"
  [ -f "$REAL_SCRIPT" ] && cp "$REAL_SCRIPT" "$REPO/infra/docker/build_images.sh"
  printf 'name: neoine-sales\n# MARK_COMPOSE\n' > "$REPO/infra/docker/compose.yaml"
  printf '#!/usr/bin/env bash\n# MARK_DEPLOY\n' > "$REPO/infra/docker/deploy.sh"
  echo "FROM scratch" > "$REPO/infra/docker/web/Dockerfile"
  echo "FROM scratch" > "$REPO/backend/Dockerfile"
  echo '<html></html>' > "$REPO/frontend/dist/index.html"
  cat > "$BIN/docker" <<'STUB'
#!/usr/bin/env bash
echo "docker $*" >> "$CALLS_LOG"
exit 0
STUB
  chmod +x "$BIN/docker"
}

run_build() { # run_build [환경변수 NAME=값 ...] -- <인자...>  (현재 디렉터리는 저장소 밖)
  local envs=() x
  while [ $# -gt 0 ]; do
    if [ "$1" = "--" ]; then shift; break; fi
    envs+=("$1"); shift
  done
  ( cd "$CWD" && env PATH="$BIN:$PATH" HOME="$TMP" CALLS_LOG="$LOG" ${envs[@]+"${envs[@]}"} \
      "$TEST_BASH" "$REPO/infra/docker/build_images.sh" "$@" > "$TMP/out.log" 2>&1 )
}
log_has()  { grep -Eq -- "$1" "$LOG"; }
log_none() { ! grep -Eq -- "$1" "$LOG"; }
log_empty() { [ ! -s "$LOG" ]; }
log_count() { grep -Ec -- "$1" "$LOG" || true; }

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"
[ -f "$REAL_SCRIPT" ] || fail "infra/docker/build_images.sh가 없음(구현 전: red)"

echo "T-BLD-1 이미지 이름·컨텍스트·키트·push(AC5)"
new_case; run_build REGISTRY="$REG" -- "$TAG"; rc=$?
eq "종료 코드 0" "0" "$rc"
check "api 이미지 이름" log_has "docker build .*-t $REG/neoine-sales/api:$TAG( |\$)"
check "web 이미지 이름" log_has "docker build .*-t $REG/neoine-sales/web:$TAG( |\$)"
API_LINE="$(grep -E "docker build .*neoine-sales/api:$TAG" "$LOG" | head -1)"
WEB_LINE="$(grep -E "docker build .*neoine-sales/web:$TAG" "$LOG" | head -1)"
case "$API_LINE" in *" backend") ok "api 컨텍스트는 backend(마지막 인자)" ;; *) fail "api 컨텍스트는 backend ($API_LINE)" ;; esac
case "$API_LINE" in *"--build-arg RELEASE_TAG=$TAG"*) ok "api 빌드에 RELEASE_TAG 빌드 인자" ;; *) fail "api 빌드에 RELEASE_TAG 빌드 인자 ($API_LINE)" ;; esac
case "$WEB_LINE" in *"-f infra/docker/web/Dockerfile"*) ok "web은 -f infra/docker/web/Dockerfile" ;; *) fail "web은 -f infra/docker/web/Dockerfile ($WEB_LINE)" ;; esac
case "$WEB_LINE" in *" .") ok "web 컨텍스트는 저장소 루트(.)" ;; *) fail "web 컨텍스트는 저장소 루트 ($WEB_LINE)" ;; esac
check "--push 없이는 push하지 않음" log_none 'docker push'
check "docker login을 부르지 않음(로그인은 호출한 쪽)" log_none 'docker login|docker logout'
KIT="$REPO/build/deploy-$TAG.tar.gz"
check "배포 키트 build/deploy-<태그>.tar.gz 생성" test -f "$KIT"
LIST="$(tar -tzf "$KIT" 2>/dev/null | sed 's#^\./##' | sort | tr '\n' ' ')"
eq "키트에는 compose.yaml과 deploy.sh만" "compose.yaml deploy.sh " "$LIST"
check "키트의 compose.yaml이 저장소의 것" bash -c "tar -xzOf '$KIT' ./compose.yaml 2>/dev/null | grep -q MARK_COMPOSE || tar -xzOf '$KIT' compose.yaml | grep -q MARK_COMPOSE"
check "키트의 deploy.sh가 저장소의 것" bash -c "tar -xzOf '$KIT' ./deploy.sh 2>/dev/null | grep -q MARK_DEPLOY || tar -xzOf '$KIT' deploy.sh | grep -q MARK_DEPLOY"

echo "T-BLD-1b --push는 두 이미지를 빌드 뒤에 push(AC5)"
new_case; run_build REGISTRY="$REG" -- "$TAG" --push; rc=$?
eq "종료 코드 0" "0" "$rc"
eq "push는 2회" "2" "$(log_count 'docker push')"
check "api push" log_has "docker push $REG/neoine-sales/api:$TAG\$"
check "web push" log_has "docker push $REG/neoine-sales/web:$TAG\$"
LAST_BUILD="$(grep -n 'docker build' "$LOG" | tail -1 | cut -d: -f1)"
FIRST_PUSH="$(grep -n 'docker push' "$LOG" | head -1 | cut -d: -f1)"
check "모든 빌드가 push보다 먼저" test -n "$LAST_BUILD" -a -n "$FIRST_PUSH" -a "${LAST_BUILD:-99}" -lt "${FIRST_PUSH:-0}"
check "docker login을 부르지 않음" log_none 'docker login|docker logout'

echo "T-BLD-2 frontend/dist가 없으면 빌드 없이 실패(AC2)"
new_case; rm "$REPO/frontend/dist/index.html"
run_build REGISTRY="$REG" -- "$TAG"; rc=$?
check "종료 코드가 0이 아님" test "$rc" -ne 0
check "docker 호출 없음" log_empty
check "키트도 만들지 않음" test ! -e "$REPO/build/deploy-$TAG.tar.gz"

echo "T-BLD-3 REGISTRY가 비어 있으면 실패(AC9)"
new_case; run_build REGISTRY= -- "$TAG"; rc=$?
check "빈 REGISTRY: 종료 코드가 0이 아님" test "$rc" -ne 0
check "빈 REGISTRY: docker 호출 없음" log_empty
new_case; run_build -- "$TAG"; rc=$?
check "REGISTRY 미설정: 종료 코드가 0이 아님" test "$rc" -ne 0
check "REGISTRY 미설정: docker 호출 없음" log_empty
has_reg="$(grep -c REGISTRY "$TMP/out.log" || true)"
check "메시지에 REGISTRY가 나옴" test "$has_reg" -ge 1

echo "T-BLD-4 잘못된 태그·옵션은 실패(D10)"
for bad in "../etc" "a;rm" "-x" "a b" ""; do
  new_case; run_build REGISTRY="$REG" -- "$bad"; rc=$?
  check "태그 '$bad': 종료 코드가 0이 아님" test "$rc" -ne 0
  check "태그 '$bad': docker 호출 없음" log_empty
done
new_case; run_build REGISTRY="$REG" -- "$(printf 'abc\n../../x y')"; rc=$?
check "줄바꿈 포함 태그: 종료 2" test "$rc" -eq 2
check "줄바꿈 포함 태그: docker 호출 없음" log_empty
new_case; run_build REGISTRY="$REG" -- "$(printf '%s\nx' "$TAG")"; rc=$?
check "유효한 줄 뒤에 줄이 붙은 태그: 종료 2" test "$rc" -eq 2
check "유효한 줄 뒤에 줄이 붙은 태그: docker 호출 없음" log_empty
new_case; run_build REGISTRY="$REG" -- "$TAG" --bogus; rc=$?
check "알 수 없는 옵션: 종료 코드가 0이 아님" test "$rc" -ne 0
check "알 수 없는 옵션: docker 호출 없음" log_empty
new_case; run_build REGISTRY="$REG" -- ; rc=$?
check "태그 없음: 종료 코드가 0이 아님" test "$rc" -ne 0

echo "T-BLD-5 빌드 인자에 비밀이 없음(AC4)"
new_case; run_build REGISTRY="$REG" APP_JWT_SECRET=SECRETMARK_x POSTGRES_PASSWORD=SECRETMARK_y -- "$TAG" --push
check "빌드 인자는 RELEASE_TAG뿐" bash -c "! grep -E -- '--build-arg' '$LOG' | grep -Ev -- '--build-arg RELEASE_TAG=$TAG' | grep -q ."
check "비밀 이름의 빌드 인자 없음" log_none '--build-arg [A-Za-z_]*(SECRET|PASSWORD|TOKEN|KEY|DSN|DATABASE_URL)'
check "환경의 비밀 표식이 docker 인자·출력에 없음" bash -c "! cat '$LOG' '$TMP/out.log' | grep -q SECRETMARK"

echo "T-BLD-6 정적 확인"
if [ -f "$REAL_SCRIPT" ]; then
  check "bash -n" "$TEST_BASH" -n "$REAL_SCRIPT"
  BODY="$WORK/build.body"; grep -v '^[[:space:]]*#' "$REAL_SCRIPT" > "$BODY"
  check "docker login을 직접 하지 않음" bash -c "! grep -Eq 'docker +login' '$BODY'"
  check "frontend를 이미지 안에서 다시 빌드하지 않음(pnpm·npm 호출 없음)" bash -c "! grep -Eq '(^|[[:space:];&|])(pnpm|npm|corepack) ' '$BODY'"
else
  fail "build_images.sh 없음(구현 전: red)"
fi

echo
echo "$CASES 케이스, 실패 $FAILURES"
[ "$FAILURES" -eq 0 ]
