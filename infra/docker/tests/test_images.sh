#!/usr/bin/env bash
# 빌드된 api·web 이미지 검사. 실제 docker 데몬으로 컨테이너를 잠깐 띄운다(레지스트리 접속·push 없음).
# Jenkins Package 단계가 이미지 빌드 직후, push 전에 REQUIRE_DOCKER=1로 실행한다.
#   실행: REGISTRY=<레지스트리> bash infra/docker/tests/test_images.sh <태그>
#   docker 또는 이미지가 없으면 로컬은 건너뛰고(종료 0), REQUIRE_DOCKER=1이면 실패한다.
#   계획: artifacts/10-analysis/docker-compose-plan.md (D2·D3·D5, AC1·AC2·AC4·AC10, T-IMG-1~7)
set -uo pipefail

TEST_BASH="${BASH:-/bin/bash}"
TAG="${1:-}"
FAILURES=0
CASES=0
WORK="$(mktemp -d)"
CID=""
cleanup() { [ -z "$CID" ] || docker rm -f "$CID" >/dev/null 2>&1; rm -rf "$WORK"; }
trap cleanup EXIT

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (기대 '$2', 실제 '$3')"; fi; }
skip_or_fail() {
  if [ "${REQUIRE_DOCKER:-}" = "1" ]; then fail "$1 (REQUIRE_DOCKER=1이라 건너뛰지 않고 실패)"; echo; echo "$CASES 케이스, 실패 $FAILURES"; exit 1; fi
  echo "  skip $1"; exit 0
}

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"
if [ -z "$TAG" ] || ! printf '%s' "$TAG" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$'; then
  echo "사용법: REGISTRY=<레지스트리> test_images.sh <태그>" >&2; exit 2
fi
[ -n "${REGISTRY:-}" ] || { echo "REGISTRY가 필요합니다" >&2; exit 2; }
docker info >/dev/null 2>&1 || skip_or_fail "docker 데몬을 쓸 수 없어 이미지 검사를 건너뜀"
API="$REGISTRY/neoine-sales/api:$TAG"
WEB="$REGISTRY/neoine-sales/web:$TAG"
docker image inspect "$API" >/dev/null 2>&1 || skip_or_fail "이미지가 없음: $API"
docker image inspect "$WEB" >/dev/null 2>&1 || skip_or_fail "이미지가 없음: $WEB"

arun() { docker run --rm --pull never "$@"; }   # 항상 로컬 이미지만 쓴다

echo "T-IMG-1 api 기본 사용자는 root가 아님(AC1)"
CASES=$((CASES + 1))
USER_CFG="$(docker image inspect -f '{{.Config.User}}' "$API")"
case "$USER_CFG" in
  "" | root | root:* | 0 | 0:*) fail "api 이미지 기본 USER가 root이거나 비어 있음: '$USER_CFG'" ;;
  *) ok "api 이미지 기본 USER가 root가 아님: $USER_CFG" ;;
esac
ID_OUT="$(arun --entrypoint sh "$API" -c 'id -u' 2>/dev/null)"
check "컨테이너 안의 실제 UID가 0이 아님: $ID_OUT" test -n "$ID_OUT" -a "${ID_OUT:-0}" != "0"

echo "T-IMG-2 .env·tests·개발 의존성이 없음(AC1, AC4)"
CASES=$((CASES + 1))
LS_ENV="$(arun --entrypoint sh "$API" -c 'ls -A /app | grep -E "^\.env" || true' 2>/dev/null)"
eq "/app에 .env* 없음" "" "$LS_ENV"
check "/app/tests 없음" arun --entrypoint sh "$API" -c 'test ! -e /app/tests'
FOUND_ENV="$(arun --entrypoint sh "$API" -c 'find / -xdev \( -name ".env" -o -name ".env.*" \) -not -path "/proc/*" -not -name ".env.example" 2>/dev/null | head -5' 2>/dev/null)"
eq "이미지 어디에도 .env 파일이 없음" "" "$FOUND_ENV"
for mod in pytest ruff mypy; do
  check "개발 의존성 $mod를 import할 수 없음" bash -c "! docker run --rm --pull never --entrypoint python '$API' -c 'import $mod' >/dev/null 2>&1"
done

echo "T-IMG-3 앱 import와 alembic(AC1)"
CASES=$((CASES + 1))
check "import app.main 성공" arun --entrypoint python "$API" -c 'import app.main'
check "alembic -c /app/alembic.ini heads 성공" arun --entrypoint alembic "$API" -c /app/alembic.ini heads >/dev/null
HEADS="$(arun --entrypoint alembic "$API" -c /app/alembic.ini heads 2>/dev/null | grep -c '(head)')"
eq "head revision이 하나" "1" "$HEADS"

echo "T-IMG-4 임의 UID로도 동작(AC1)"
CASES=$((CASES + 1))
check "--user 12345:12345에서 import app.main 성공" arun --user 12345:12345 --entrypoint python "$API" -c 'import app.main'
check "--user 12345:12345에서 alembic heads 성공" arun --user 12345:12345 --entrypoint alembic "$API" -c /app/alembic.ini heads >/dev/null

echo "T-IMG-5 /etc/localtime mount 시 시간대가 호스트와 같음(AC10)"
CASES=$((CASES + 1))
if [ -e /etc/localtime ]; then
  IMG_TZ="$(arun -v /etc/localtime:/etc/localtime:ro --entrypoint python "$API" -c "import datetime; print(datetime.datetime.now().astimezone().strftime('%z'))" 2>/dev/null)"
  eq "컨테이너의 UTC 오프셋이 호스트 date +%z와 같음" "$(date +%z)" "$IMG_TZ"
else
  echo "  skip 호스트에 /etc/localtime이 없음"
fi

echo "T-IMG-7 web 이미지 내용(AC2)"
CASES=$((CASES + 1))
check "index.html 존재" arun --entrypoint sh "$WEB" -c 'test -f /usr/share/nginx/html/index.html'
check "config.product.json 존재" arun --entrypoint sh "$WEB" -c 'test -f /usr/share/nginx/config/config.product.json'
check "config.dev.json은 없음(product만)" arun --entrypoint sh "$WEB" -c 'test ! -e /usr/share/nginx/config/config.dev.json'
check "인증서·비밀이 이미지에 들어 있지 않음" arun --entrypoint sh "$WEB" -c 'test -z "$(find /etc/nginx /usr/share/nginx -name "*.pem" -o -name "*.key" -o -name ".env*" 2>/dev/null | head -1)"'

echo "T-IMG-6 web 컨테이너 동작(자체 서명 인증서, AC2)"
CASES=$((CASES + 1))
if ! command -v openssl >/dev/null 2>&1; then
  fail "openssl이 필요함(자체 서명 인증서 생성)"
else
  mkdir -p "$WORK/certs"
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=localhost" \
    -keyout "$WORK/certs/privkey.pem" -out "$WORK/certs/fullchain.pem" >/dev/null 2>&1
  chmod 644 "$WORK/certs/privkey.pem" "$WORK/certs/fullchain.pem"
  CID="$(docker run -d --pull never --add-host api:127.0.0.1 -e SERVER_NAME=localhost -e APP_PROFILE=product \
          -v "$WORK/certs:/etc/nginx/certs:ro" "$WEB" 2>/dev/null)"
  if [ -z "$CID" ]; then
    fail "web 컨테이너를 띄우지 못함"
  else
    up=0
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
      if docker exec "$CID" wget -q -O /dev/null http://127.0.0.1/nginx-health >/dev/null 2>&1; then up=1; break; fi
      sleep 1
    done
    check "web이 기동하고 /nginx-health가 200" test "$up" = 1
    dex() { docker exec "$CID" sh -c "$1" 2>&1; }
    check "nginx -t 통과" docker exec "$CID" nginx -t
    CONF="$(dex 'cat /etc/nginx/conf.d/default.conf')"
    case "$CONF" in *'$uri'*) ok "렌더링 conf에 nginx 변수 \$uri 유지" ;; *) fail "렌더링 conf에 nginx 변수 \$uri 유지" ;; esac
    case "$CONF" in *'$host'*) ok "렌더링 conf에 nginx 변수 \$host 유지" ;; *) fail "렌더링 conf에 nginx 변수 \$host 유지" ;; esac
    case "$CONF" in *'${SERVER_NAME}'*|*'${APP_PROFILE}'*) fail "치환되지 않은 템플릿 변수가 남음" ;; *) ok "템플릿 변수(SERVER_NAME·APP_PROFILE)가 치환됨" ;; esac
    case "$CONF" in *"server_name localhost"*) ok "server_name이 SERVER_NAME으로 치환됨" ;; *) fail "server_name이 SERVER_NAME으로 치환됨" ;; esac
    case "$CONF" in *101m*) ok "업로드 경로 101m" ;; *) fail "업로드 경로 101m" ;; esac
    case "$CONF" in *300s*) ok "업로드 경로 300s" ;; *) fail "업로드 경로 300s" ;; esac
    case "$CONF" in *"http://api:8000"*) ok "api로 프록시(http://api:8000)" ;; *) fail "api로 프록시(http://api:8000)" ;; esac
    case "$CONF" in *1y*|*31536000*) ok "/assets/ 1년 캐시" ;; *) fail "/assets/ 1년 캐시" ;; esac
    case "$CONF" in *gzip*) ok "gzip" ;; *) fail "gzip" ;; esac
    HTTP_HDR="$(dex 'wget -S --max-redirect=0 -O /dev/null http://127.0.0.1/some/path 2>&1')"
    case "$HTTP_HDR" in *" 301 "*) ok "http 다른 경로는 301(80→443)" ;; *) fail "http 다른 경로는 301 ($HTTP_HDR)" ;; esac
    HTTPS_HDR="$(dex 'wget --no-check-certificate -S -O /dev/null https://127.0.0.1/index.html 2>&1')"
    case "$HTTPS_HDR" in *" 200 "*) ok "https index.html 200" ;; *) fail "https index.html 200 ($HTTPS_HDR)" ;; esac
    LOWER="$(printf '%s' "$HTTPS_HDR" | tr 'A-Z' 'a-z')"
    case "$LOWER" in *no-cache*) ok "index.html Cache-Control no-cache" ;; *) fail "index.html Cache-Control no-cache" ;; esac
    for h in x-content-type-options x-frame-options referrer-policy; do
      case "$LOWER" in *"$h"*) ok "보안 헤더 $h" ;; *) fail "보안 헤더 $h" ;; esac
    done
    BODY="$(dex 'wget --no-check-certificate -q -O- https://127.0.0.1/config.json' | tr -d ' \n')"
    eq "/config.json은 product 설정" '{"profile":"product"}' "$BODY"
    CFG_HDR="$(dex 'wget --no-check-certificate -S -O /dev/null https://127.0.0.1/config.json 2>&1' | tr 'A-Z' 'a-z')"
    case "$CFG_HDR" in *no-cache*) ok "/config.json no-cache" ;; *) fail "/config.json no-cache" ;; esac
  fi
fi

echo
echo "$CASES 케이스, 실패 $FAILURES"
[ "$FAILURES" -eq 0 ]
