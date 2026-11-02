#!/usr/bin/env bash
# infra/docker/compose.yaml 정적 검사. 실제 `docker compose config --format json`(컨테이너·네트워크 접속 없음)을 렌더링해
# python3로 구조를 검사한다. 이미지 빌드·pull·up은 하지 않는다.
#   실행: bash infra/docker/tests/test_compose.sh
#   docker(compose v2)가 없으면 로컬은 건너뛰고(종료 0), REQUIRE_DOCKER=1이면 실패한다(CI는 항상 REQUIRE_DOCKER=1).
#   계획: artifacts/10-analysis/docker-compose-plan.md (D4·D6·D7, AC3·AC4·AC5·AC10·AC11·AC12, T-CMP-1~11)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_SRC="${COMPOSE_FILE_UNDER_TEST:-$HERE/../compose.yaml}"
EXAMPLE="${DEPLOY_ENV_EXAMPLE:-$HERE/../deploy.env.example}"
TEST_BASH="${BASH:-/bin/bash}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILURES=0
CASES=0
SKIPS=0
MARK="SECRETMARK_c0mp0se"
REG="registry.example.com"

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"

if ! docker compose version >/dev/null 2>&1; then
  if [ "${REQUIRE_DOCKER:-}" = "1" ]; then
    fail "docker compose(v2)를 쓸 수 없음: REQUIRE_DOCKER=1이라 건너뛰지 않고 실패"
    echo; echo "0 케이스, 실패 $FAILURES"; exit 1
  fi
  echo "  skip docker compose(v2)가 없어 compose 검사를 건너뜀(로컬 전용, CI는 REQUIRE_DOCKER=1로 실패)"
  exit 0
fi
command -v python3 >/dev/null 2>&1 || { fail "python3가 필요함"; echo; echo "0 케이스, 실패 $FAILURES"; exit 1; }

[ -f "$COMPOSE_SRC" ] || fail "infra/docker/compose.yaml이 없음(구현 전: red)"
[ -f "$EXAMPLE" ] || fail "infra/docker/deploy.env.example이 없음(구현 전: red)"

set_kv() { # set_kv <파일> <이름> <값>
  awk -v n="$2" -v v="$3" 'BEGIN{p=n"="} index($0,p)==1{print p v; d=1; next} {print} END{if(!d)print p v}' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}
drop_kv() { grep -v "^$2=" "$1" > "$1.tmp"; mv "$1.tmp" "$1"; }

# 케이스 환경: 배포 디렉터리 사본(compose.yaml), 가짜 앱 홈(.env 표식 비밀), deploy.env(예시 기반), image.env
new_case() {
  CASES=$((CASES + 1))
  TMP="$(mktemp -d "$WORK/case.XXXXXX")"
  APPH="$TMP/app"; KIT="$APPH/deploys/tagA"
  mkdir -p "$KIT" "$APPH/certs" "$TMP/data/postgres"
  [ -f "$COMPOSE_SRC" ] && cp "$COMPOSE_SRC" "$KIT/compose.yaml"
  {
    echo "APP_PROFILE=product"
    echo "APP_JWT_SECRET=${MARK}_jwt"
    echo "POSTGRES_USER=neoine"
    echo "POSTGRES_PASSWORD=${MARK}_pw"
    echo "POSTGRES_DB=neoinesales"
    echo "APP_DATABASE_URL=postgresql+asyncpg://neoine:${MARK}_pw@db:5432/neoinesales"
  } > "$APPH/.env"
  [ -f "$EXAMPLE" ] && cp "$EXAMPLE" "$APPH/deploy.env" || : > "$APPH/deploy.env"
  set_kv "$APPH/deploy.env" APP_HOME "$APPH"
  set_kv "$APPH/deploy.env" APP_PROFILE product
  set_kv "$APPH/deploy.env" APP_UID 4242
  set_kv "$APPH/deploy.env" APP_GID 4343
  set_kv "$APPH/deploy.env" API_WORKERS 4
  set_kv "$APPH/deploy.env" SERVER_NAME sales.example.com
  set_kv "$APPH/deploy.env" CERT_DIR "$APPH/certs"
  set_kv "$APPH/deploy.env" REGISTRY "$REG"
  set_kv "$APPH/deploy.env" DB_DATA_DIR "$TMP/data/postgres"
  echo "IMAGE_TAG=tagA" > "$KIT/image.env"
}

render() { # render <출력 파일> [compose 인자...]  (deploy.sh와 같은 형식의 호출)
  local out="$1"; shift
  docker compose -p neoine-sales --project-directory "$KIT" -f "$KIT/compose.yaml" \
    --env-file "$APPH/deploy.env" --env-file "$KIT/image.env" "$@" config --format json > "$out" 2> "$TMP/render.err"
}

# 렌더링 결과(JSON)를 python으로 검사한다. 줄마다 'ok ...' 또는 'FAIL ...'을 출력한다.
run_inspect() { # 출력하고 FAIL 줄 수를 실패로 센다(출력이 없으면 python 오류로 보고 실패)
  local out n
  out="$(inspect "$@" 2>&1)"
  printf '%s\n' "$out"
  if [ -z "$out" ]; then fail "검사 스크립트가 출력 없이 끝남(python 오류)"; return; fi
  case "$out" in *Traceback*) fail "검사 스크립트가 예외로 끝남"; return ;; esac
  n="$(printf '%s\n' "$out" | grep -c '^  FAIL' || true)"
  FAILURES=$((FAILURES + n))
}
inspect() { # inspect <json 파일> <python 코드(함수 정의 이후의 검사 본문)>
  JSON="$1" MARK="$MARK" REG="$REG" APPH="$APPH" TMPD="$TMP" python3 -I -c '
import json, os, sys
cfg = json.load(open(os.environ["JSON"]))
svc = cfg.get("services", {})
MARK, REG, APPH, TMPD = os.environ["MARK"], os.environ["REG"], os.environ["APPH"], os.environ["TMPD"]
def ok(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
def block(name):
    return json.dumps(svc.get(name, {}), ensure_ascii=False)
def vols(name):
    return svc.get(name, {}).get("volumes", []) or []
def has_bind(name, source, target, ro):
    for v in vols(name):
        if v.get("target") == target and v.get("source") == source and v.get("type") == "bind":
            return bool(v.get("read_only")) == ro
    return False
def joined(x):
    return " ".join(x) if isinstance(x, list) else str(x or "")
'"$2" < /dev/null
}

echo "T-CMP-1 렌더링(AC3, AC5)"
new_case
render "$TMP/base.json"; rc=$?
if [ "$rc" -eq 0 ]; then ok "예시 deploy.env·가짜 .env로 렌더링 성공"; else fail "예시 deploy.env·가짜 .env로 렌더링 실패 ($(head -c 300 "$TMP/render.err"))"; fi
BASE="$TMP/base.json"; BASE_TMP="$TMP"; BASE_APPH="$APPH"; BASE_KIT="$KIT"
# 필수 변수가 없으면 실패해야 한다(:? 검사)
new_case; : > "$KIT/image.env"
render "$TMP/o.json"; check "IMAGE_TAG가 없으면 렌더링 실패" test $? -ne 0
new_case; set_kv "$APPH/deploy.env" REGISTRY ""
render "$TMP/o.json"; check "REGISTRY가 비어 있으면 렌더링 실패" test $? -ne 0
new_case; drop_kv "$APPH/deploy.env" APP_UID
render "$TMP/o.json"; check "APP_UID가 없으면 렌더링 실패" test $? -ne 0
new_case; drop_kv "$APPH/deploy.env" APP_GID
render "$TMP/o.json"; check "APP_GID가 없으면 렌더링 실패" test $? -ne 0
new_case; drop_kv "$APPH/deploy.env" API_WORKERS
render "$TMP/o.json"; check "API_WORKERS가 없으면 렌더링 실패" test $? -ne 0
new_case; drop_kv "$APPH/deploy.env" DB_DATA_DIR
render "$TMP/o.json"; check "DB_DATA_DIR가 없으면 렌더링 실패" test $? -ne 0
new_case; drop_kv "$APPH/deploy.env" CERT_DIR
render "$TMP/o.json"; check "CERT_DIR가 없으면 렌더링 실패" test $? -ne 0

if [ ! -s "$BASE" ]; then
  fail "기본 렌더링 결과가 없어 이후 구조 검사를 할 수 없음(구현 전: red)"
else
  TMP="$BASE_TMP"; APPH="$BASE_APPH"; KIT="$BASE_KIT"

  echo "T-CMP-2 서비스 구성(AC3)"
  run_inspect "$BASE" 'ok(set(svc) == {"db","api","web"}, "기본 서비스는 db·api·web뿐: %s" % sorted(svc))'
  MIG="$TMP/mig.json"
  render "$MIG" --profile migrate
  run_inspect "$MIG" 'ok(set(svc) == {"db","api","web","migrate"}, "--profile migrate면 migrate 추가: %s" % sorted(svc))'

  echo "T-CMP-3 호스트 포트(AC3, AC12)"
  run_inspect "$BASE" '
pub = {}
for name, s in svc.items():
    for p in s.get("ports", []) or []:
        pub.setdefault(name, []).append(str(p.get("published")))
ok(set(pub) == {"web"}, "published 포트를 가진 서비스는 web뿐: %s" % pub)
ok(sorted(pub.get("web", [])) == ["443", "80"], "web의 published 포트는 80·443: %s" % pub.get("web"))
ok(not (svc.get("api", {}).get("ports")), "api는 ports 없음")
ok(not (svc.get("db", {}).get("ports")), "db는 ports 없음")
'
  run_inspect "$MIG" 'ok(not (svc.get("migrate", {}).get("ports")), "migrate는 ports 없음")'

  echo "T-CMP-4 의존성과 헬스(AC3)"
  run_inspect "$MIG" '
def cond(a, b):
    return ((svc.get(a, {}).get("depends_on") or {}).get(b) or {}).get("condition")
ok(cond("api", "db") == "service_healthy", "api는 db service_healthy에 의존")
ok(cond("migrate", "db") == "service_healthy", "migrate는 db service_healthy에 의존")
ok(cond("web", "api") == "service_healthy", "web은 api service_healthy에 의존")
ok("migrate" not in (svc.get("api", {}).get("depends_on") or {}), "api는 migrate에 의존하지 않음")
ok("migrate" not in (svc.get("web", {}).get("depends_on") or {}), "web은 migrate에 의존하지 않음")
ok(joined(svc.get("migrate", {}).get("command")).find("alembic") >= 0 and joined(svc.get("migrate", {}).get("command")).find("upgrade head") >= 0, "migrate command는 alembic upgrade head")
ok(str(svc.get("migrate", {}).get("restart", "")) in ("no", "false", "None", ""), "migrate는 재시작하지 않음(restart no)")
ok(joined((svc.get("web", {}).get("healthcheck") or {}).get("test")).find("nginx-health") >= 0, "web 헬스체크는 /nginx-health")
'

  echo "T-CMP-5 db 이미지·헬스체크(AC3, A6)"
  run_inspect "$BASE" '
db = svc.get("db", {})
ok("pg_isready" in joined((db.get("healthcheck") or {}).get("test")), "db healthcheck에 pg_isready")
ok(":18." in str(db.get("image")), "db 이미지는 주 버전 18 고정: %s" % db.get("image"))
ok("@sha256:" in str(db.get("image")), "db 이미지에 digest 고정")
ok(db.get("restart") == "unless-stopped", "db restart unless-stopped")
'

  echo "T-CMP-6 비밀 경로(AC4)"
  run_inspect "$MIG" '
for name in ("api", "web", "migrate"):
    ok("env_file" not in svc.get(name, {}), "%s에 env_file 없음" % name)
    ok(MARK not in block(name), "%s 렌더링 결과에 .env 표식 비밀 없음" % name)
for name in ("api", "migrate"):
    ok(has_bind(name, APPH + "/.env", "/app/.env", True), "%s는 .env를 /app/.env로 읽기 전용 bind" % name)
db = svc.get("db", {})
envf = json.dumps(db.get("env_file", [])) + json.dumps(db.get("environment", {}))
ok(".env" in envf or "POSTGRES_PASSWORD" in envf, "db는 같은 .env의 POSTGRES_*를 받음(env_file 또는 펼친 environment)")
for name in ("api", "web", "migrate"):
    ok("APP_JWT_SECRET" not in json.dumps(svc.get(name, {}).get("environment", {})), "%s environment에 앱 비밀 이름이 직접 정의되지 않음" % name)
'

  echo "T-CMP-7 실행 사용자·데이터 경로(AC11)"
  run_inspect "$MIG" '
ok(svc.get("api", {}).get("user") == "4242:4343", "api user는 APP_UID:APP_GID: %s" % svc.get("api", {}).get("user"))
ok(svc.get("migrate", {}).get("user") == "4242:4343", "migrate user도 APP_UID:APP_GID")
ok(has_bind("api", "/var/lib/neoine-sales", "/var/lib/neoine-sales", False), "api는 첨부 저장소를 같은 경로로 bind")
ok(has_bind("db", TMPD + "/data/postgres", "/var/lib/postgresql", False), "db 데이터는 DB_DATA_DIR -> /var/lib/postgresql")
ok(not any(v.get("target") == "/var/lib/postgresql" and v.get("type") == "volume" for v in vols("db")), "db 데이터는 named volume이 아니라 호스트 경로")
'

  echo "T-CMP-8 시간대(AC10)"
  run_inspect "$MIG" '
for name in ("api", "migrate", "db"):
    ok(has_bind(name, "/etc/localtime", "/etc/localtime", True), "%s에 /etc/localtime 읽기 전용 mount" % name)
'

  echo "T-CMP-9 프록시 헤더·워커 수(AC12)"
  run_inspect "$BASE" '
cmd = joined(svc.get("api", {}).get("command"))
ok("--proxy-headers" in cmd, "api command에 --proxy-headers")
ok("--forwarded-allow-ips" in cmd, "api command에 --forwarded-allow-ips")
ok("--workers 4" in cmd or "--workers=4" in cmd, "api command에 --workers 4: %s" % cmd)
ok(str((svc.get("api", {}).get("environment") or {}).get("APP_WORKERS")) == "4", "환경 APP_WORKERS=4")
ok("uvicorn" in cmd and "app.main:app" in cmd, "api command는 uvicorn app.main:app")
'
  new_case; set_kv "$APPH/deploy.env" API_WORKERS 3
  render "$TMP/w3.json"
  run_inspect "$TMP/w3.json" '
cmd = joined(svc.get("api", {}).get("command"))
ok("--workers 3" in cmd or "--workers=3" in cmd, "API_WORKERS=3이면 --workers 3")
ok(str((svc.get("api", {}).get("environment") or {}).get("APP_WORKERS")) == "3", "API_WORKERS=3이면 APP_WORKERS=3(둘이 같은 값)")
'

  TMP="$BASE_TMP"; APPH="$BASE_APPH"; KIT="$BASE_KIT"   # T-CMP-9가 새 케이스를 만들었으므로 기본 케이스로 되돌린다

  echo "T-CMP-10 api 하드닝·헬스체크(AC3)"
  run_inspect "$BASE" '
api = svc.get("api", {})
ok(api.get("read_only") is True, "api read_only")
ok("ALL" in (api.get("cap_drop") or []), "api cap_drop ALL")
ok(any("no-new-privileges" in str(o) for o in (api.get("security_opt") or [])), "api no-new-privileges")
ok("/readyz" in joined((api.get("healthcheck") or {}).get("test")), "api healthcheck는 /readyz")
ok(any(str(t).split(":")[0] == "/tmp" for t in (api.get("tmpfs") or [])) or any(v.get("type") == "tmpfs" and v.get("target") == "/tmp" for v in vols("api")), "api /tmp는 tmpfs")
ok(api.get("restart") == "unless-stopped", "api restart unless-stopped")
'

  echo "T-CMP-11 이미지 이름(AC5)"
  run_inspect "$MIG" '
ok(svc.get("api", {}).get("image") == REG + "/neoine-sales/api:tagA", "api 이미지: %s" % svc.get("api", {}).get("image"))
ok(svc.get("web", {}).get("image") == REG + "/neoine-sales/web:tagA", "web 이미지: %s" % svc.get("web", {}).get("image"))
ok(svc.get("migrate", {}).get("image") == svc.get("api", {}).get("image"), "migrate는 api와 같은 이미지")
'

  echo "T-CMP-12 web(AC2)"
  run_inspect "$BASE" '
web = svc.get("web", {})
env = web.get("environment") or {}
ok(env.get("SERVER_NAME") == "sales.example.com", "web 환경 SERVER_NAME")
ok(env.get("APP_PROFILE") == "product", "web 환경 APP_PROFILE=product")
ok(has_bind("web", APPH + "/certs", "/etc/nginx/certs", True), "인증서 디렉터리를 읽기 전용 mount")
ok(not any(v.get("target") == "/etc/nginx/certs" and not v.get("read_only") for v in vols("web")), "인증서는 쓰기 불가")
'

  echo "T-CMP-14 프록시 신뢰 범위와 네트워크 분리(리뷰 Blocker·Minor)"
  run_inspect "$BASE" '
import re
cmd = joined(svc.get("api", {}).get("command"))
m = re.search(r"--forwarded-allow-ips(?:=|\s+)(\S+)", cmd)
val = m.group(1).strip("\"\x27") if m else None
ok(val is not None, "api command에 --forwarded-allow-ips 값이 있음")
ok(val not in (None, "*", ""), "--forwarded-allow-ips가 *가 아님(좁은 신뢰 대역): %s" % val)
def nets(name):
    n = svc.get(name, {}).get("networks")
    return set(n) if n else {"default"}
ok(nets("web").isdisjoint(nets("db")), "web과 db는 같은 네트워크에 없음: web=%s db=%s" % (sorted(nets("web")), sorted(nets("db"))))
ok(not nets("api").isdisjoint(nets("web")), "api는 web과 네트워크를 공유")
ok(not nets("api").isdisjoint(nets("db")), "api는 db와 네트워크를 공유")
front = [c.get("subnet") for c in ((cfg.get("networks", {}).get("frontnet") or {}).get("ipam") or {}).get("config", []) or []]
ok(bool(front) and val == front[0], "--forwarded-allow-ips가 frontnet(web·api 공유) ipam subnet과 같음: %s vs %s" % (val, front))
ok("frontnet" in nets("web") and "frontnet" in nets("api"), "web·api가 frontnet을 공유")
'
fi

echo "T-CMP-15 nginx 템플릿의 X-Forwarded-For(리뷰 Blocker)"
TPL="${WEB_TEMPLATE:-$HERE/../web/templates/default.conf.template}"
if [ -f "$TPL" ]; then
  check "X-Forwarded-For 설정이 하나 이상 있음" grep -q 'proxy_set_header X-Forwarded-For' "$TPL"
  check "\$proxy_add_x_forwarded_for를 쓰지 않음(클라이언트가 보낸 값을 잇지 않음)" bash -c "! grep -q 'proxy_add_x_forwarded_for' '$TPL'"
  check "모든 X-Forwarded-For는 \$remote_addr로 덮어씀" bash -c "! grep 'proxy_set_header X-Forwarded-For' '$TPL' | grep -v '\$remote_addr' | grep -q ."
  LOC_OUT="$(python3 -I - "$TPL" <<'PYX'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
n = 0
for m in re.finditer(r"location\s+[^{]*\{([^{}]*)\}", text):
    body = m.group(1)
    if "proxy_pass" not in body:
        continue
    n += 1
    head = text[m.start():text.index("{", m.start())].strip()
    good = re.search(r"proxy_set_header\s+X-Forwarded-For\s+\$remote_addr\s*;", body) is not None
    print(("  ok   " if good else "  FAIL ") + "proxy_pass location에 X-Forwarded-For $remote_addr: " + head)
print(("  ok   " if n >= 4 else "  FAIL ") + "proxy_pass location이 4개 이상 검사됨(%d)" % n)
PYX
)"
  printf '%s\n' "$LOC_OUT"
  FAILURES=$((FAILURES + $(printf '%s\n' "$LOC_OUT" | grep -c '^  FAIL' || true)))
else
  fail "web 템플릿이 없음: $TPL"
fi

echo "T-CMP-13 저장소 파일 정적 확인(AC4)"
if [ -f "$COMPOSE_SRC" ]; then
  check "compose.yaml에 비밀 값 리터럴이 없음" bash -c "! grep -Eiq '(PASSWORD|SECRET|TOKEN|ENCRYPTION_KEY)[A-Z_]*: *[^\$ ]' '$COMPOSE_SRC'"
  check "compose.yaml에 최상위 name: neoine-sales" grep -Eq '^name: *neoine-sales' "$COMPOSE_SRC"
  check "compose.yaml에 호스트 포트 8000 노출 없음" bash -c "! grep -Eq '8000:8000' '$COMPOSE_SRC'"
fi
if [ -f "$EXAMPLE" ]; then
  check "deploy.env.example에 비밀 변수가 없음" bash -c "! grep -Eiq '(PASSWORD|SECRET|JWT|DSN|DATABASE_URL|ENCRYPTION)' '$EXAMPLE'"
  for name in APP_HOME APP_PROFILE APP_UID APP_GID API_WORKERS SERVER_NAME CERT_DIR REGISTRY DB_DATA_DIR; do
    check "deploy.env.example에 $name" grep -Eq "^${name}=" "$EXAMPLE"
  done
  check "deploy.env.example의 APP_PROFILE=product" grep -qx 'APP_PROFILE=product' "$EXAMPLE"
fi

echo
echo "$CASES 케이스, 실패 $FAILURES, 건너뜀 $SKIPS"
[ "$FAILURES" -eq 0 ]
