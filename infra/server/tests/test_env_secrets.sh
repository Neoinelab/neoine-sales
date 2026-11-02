#!/usr/bin/env bash
# infra/server/lib/env_secrets.sh(비밀 생성·.env 줄 편집 공용 함수) 테스트.
#   실행: bash infra/server/tests/test_env_secrets.sh   (/bin/bash 3.2와 bash 5 모두)
#   계획: artifacts/10-analysis/setup-script-plan.md (AC10·AC11·AC22), docker-compose-plan.md (D6·D11: DB 비밀번호·APP_DATABASE_URL)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LIB="$HERE/../lib/env_secrets.sh"
TEST_BASH="${BASH:-/bin/bash}"
FAILURES=0
CASES=0
SKIPS=0
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
skip() { printf '  skip %s\n' "$1"; SKIPS=$((SKIPS + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (기대 '$2', 실제 '$3')"; fi; }
perm_of() { ls -ld "$1" | cut -c1-10; }

# lib을 source한 새 bash에서 스니펫 실행: run_lib '<스니펫>' [인자...]
run_lib() {
  local snippet="$1"; shift
  SNIPPET="$snippet" "$TEST_BASH" -c 'source "$1"; shift; eval "$SNIPPET"' _ "$LIB" "$@"
}
new_case() { CASES=$((CASES + 1)); TMP="$(mktemp -d "$WORK/case.XXXXXX")"; }

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"
if [ ! -f "$LIB" ]; then
  fail "infra/server/lib/env_secrets.sh가 없음(구현 전: red)"
fi

echo "S1 gen_jwt_secret(AC22)"
new_case
: > "$TMP/jwt.all"; bad=0
for i in $(seq 1 20); do
  run_lib 'gen_jwt_secret' > "$TMP/jwt.one" 2>/dev/null
  size="$(wc -c < "$TMP/jwt.one" | tr -d ' ')"
  [ "$size" = 43 ] || bad=$((bad + 1))
  grep -Eq '^[A-Za-z0-9_-]{43}$' "$TMP/jwt.one" || bad=$((bad + 1))
  cat "$TMP/jwt.one" >> "$TMP/jwt.all"; echo >> "$TMP/jwt.all"
done
eq "20회 모두 정확히 43바이트(개행 없음)·URL-safe 문자만" "0" "$bad"
eq "20회 모두 서로 다름" "20" "$(sort -u "$TMP/jwt.all" | grep -c .)"

echo "S2 gen_fernet_key(AC22)"
new_case
: > "$TMP/key.all"; bad=0
for i in $(seq 1 20); do
  run_lib 'gen_fernet_key' > "$TMP/key.one" 2>/dev/null
  size="$(wc -c < "$TMP/key.one" | tr -d ' ')"
  [ "$size" = 44 ] || bad=$((bad + 1))
  grep -Eq '^[A-Za-z0-9_-]{43}=$' "$TMP/key.one" || bad=$((bad + 1))
  cat "$TMP/key.one" >> "$TMP/key.all"; echo >> "$TMP/key.all"
done
eq "20회 모두 정확히 44바이트(개행 없음)·끝 =" "0" "$bad"
eq "20회 모두 서로 다름" "20" "$(sort -u "$TMP/key.all" | grep -c .)"
if command -v python3 >/dev/null 2>&1; then
  decoded="$(python3 -I -c 'import base64,sys; print(len(base64.urlsafe_b64decode(sys.stdin.read().strip())))' < "$TMP/key.one")"
  eq "urlsafe base64 디코드 결과 32바이트" "32" "$decoded"
else
  skip "python3 없음: 디코드 검사 생략"
fi

# 테스트용 생성기
GEN='gen_fixed() { printf "%s" "VALUE123"; }'

echo "S3 env_ensure_line(AC11·AC21)"
new_case; F="$TMP/a.env"; printf 'A=1\n' > "$F"
out="$(run_lib "$GEN; env_ensure_line \"\$1\" B gen_fixed; echo \"rc=\$?\"" "$F" 2>&1)"
eq "줄 없음: 반환 0이고 출력에 값 없음" "rc=0" "$out"
eq "줄 없음: 덧붙임" "$(printf 'A=1\nB=VALUE123')" "$(cat "$F")"
new_case; F="$TMP/b.env"; printf 'B=old\nA=1\n' > "$F"; before="$(cksum < "$F")"
out="$(run_lib "$GEN; env_ensure_line \"\$1\" B gen_fixed; echo \"rc=\$?\"" "$F" 2>&1)"
eq "줄 있음: 반환 1" "rc=1" "$out"
eq "줄 있음: 파일 불변" "$before" "$(cksum < "$F")"
new_case; F="$TMP/c.env"; printf 'A=1' > "$F"
run_lib "$GEN; env_ensure_line \"\$1\" B gen_fixed" "$F" >/dev/null 2>&1
eq "마지막 줄 개행 없음: 합쳐지지 않음" "$(printf 'A=1\nB=VALUE123')" "$(cat "$F")"
eq "끝은 개행" "B=VALUE123" "$(tail -1 "$F")"
check "마지막 바이트가 개행" test "$(tail -c 1 "$F" | od -An -c | tr -d ' ')" = '\n'
new_case; F="$TMP/d.env"; : > "$F"
run_lib "$GEN; env_ensure_line \"\$1\" B gen_fixed" "$F" >/dev/null 2>&1
eq "빈 파일" "B=VALUE123" "$(cat "$F")"
new_case; F="$TMP/e.env"; printf 'APP_JWT_SECRET_OLD=1\n#APP_JWT_SECRET=x\n' > "$F"
run_lib "$GEN; env_ensure_line \"\$1\" APP_JWT_SECRET gen_fixed" "$F" >/dev/null 2>&1
eq "접두사만 같거나 주석인 줄은 '있는 줄'로 보지 않음" "APP_JWT_SECRET=VALUE123" "$(tail -1 "$F")"
new_case; F="$TMP/f.env"; printf 'A=1\n' > "$F"; chmod 600 "$F"
run_lib "$GEN; env_ensure_line \"\$1\" B gen_fixed" "$F" >/dev/null 2>&1
eq "덧붙여도 권한 600 유지" "-rw-------" "$(perm_of "$F")"

echo "S3b env_has_value"
new_case; F="$TMP/g.env"; printf 'A=\nB=x\n' > "$F"
out="$(run_lib 'env_has_value "$1" A; echo "A=$?"; env_has_value "$1" B; echo "B=$?"; env_has_value "$1" C; echo "C=$?"' "$F" 2>&1)"
eq "빈 값 1·값 있음 0·없음 1, 출력은 결과뿐" "$(printf 'A=1\nB=0\nC=1')" "$out"

echo "S4 env_replace_value(AC10)"
new_case; F="$TMP/h.env"; printf '# NAME=zzz 주석\nA=1\nNAME=old\nB=2\n' > "$F"; chmod 644 "$F"
NEWV='a/b&c=d\e|f'
ENV_NEW_VALUE="$NEWV" run_lib 'env_replace_value "$1" NAME' "$F" >/dev/null 2>&1
eq "값이 정확히 바뀜(/ & = \\ | 포함)" "NAME=$NEWV" "$(grep '^NAME=' "$F")"
eq "다른 줄·주석 보존" "$(printf '# NAME=zzz 주석\nA=1\nNAME=%s\nB=2' "$NEWV")" "$(cat "$F")"
eq "권한 600" "-rw-------" "$(perm_of "$F")"
eq "임시 파일이 남지 않음" "1" "$(ls "$TMP" | grep -c 'h.env')"
new_case; F="$TMP/i.env"; printf 'A=1\n' > "$F"
ENV_NEW_VALUE="v1" run_lib 'env_replace_value "$1" NAME' "$F" >/dev/null 2>&1
eq "줄이 없으면 덧붙임" "$(printf 'A=1\nNAME=v1')" "$(cat "$F")"
# argv에 값이 노출되지 않는지: awk 호출 인자를 기록하는 래퍼를 PATH 앞에 둔다
new_case; F="$TMP/j.env"; printf 'NAME=old\n' > "$F"; mkdir "$TMP/bin"
REAL_AWK="$(command -v awk)"
printf '#!/bin/sh\necho "$*" >> "%s/awk.args"\nexec "%s" "$@"\n' "$TMP" "$REAL_AWK" > "$TMP/bin/awk"; chmod +x "$TMP/bin/awk"
: > "$TMP/awk.args"
PATH="$TMP/bin:$PATH" ENV_NEW_VALUE="SECRETVALUE9" run_lib 'env_replace_value "$1" NAME' "$F" >/dev/null 2>&1
eq "값이 바뀜" "NAME=SECRETVALUE9" "$(cat "$F")"
check "awk 인자(argv)에 값이 없음" bash -c "! grep -q SECRETVALUE9 '$TMP/awk.args'"

echo "S5 gen_db_password(docker-compose 계획 D6·D11: 영숫자 32자)"
new_case
: > "$TMP/pw.all"; bad=0
for i in $(seq 1 20); do
  run_lib 'gen_db_password' > "$TMP/pw.one" 2>/dev/null
  size="$(wc -c < "$TMP/pw.one" | tr -d ' ')"
  [ "$size" = 32 ] || bad=$((bad + 1))
  grep -Eq '^[A-Za-z0-9]{32}$' "$TMP/pw.one" || bad=$((bad + 1))
  cat "$TMP/pw.one" >> "$TMP/pw.all"; echo >> "$TMP/pw.all"
done
eq "20회 모두 정확히 32바이트(개행 없음)·영숫자만" "0" "$bad"
eq "20회 모두 서로 다름" "20" "$(sort -u "$TMP/pw.all" | grep -c .)"

echo "S5b env_ensure_database_url(D11: POSTGRES_*로 APP_DATABASE_URL 조립, 값 출력·argv 노출 없음)"
URL_EXPECTED='APP_DATABASE_URL=postgresql+asyncpg://dbuser:Pw0rdMARK9@db:5432/dbname'
new_case; F="$TMP/u1.env"; printf 'APP_PROFILE=product\nPOSTGRES_USER=dbuser\nPOSTGRES_PASSWORD=Pw0rdMARK9\nPOSTGRES_DB=dbname\n' > "$F"
out="$(run_lib 'env_ensure_database_url "$1"; echo "rc=$?"' "$F" 2>&1)"
eq "URL 줄이 없으면 반환 0이고 출력에 값 없음" "rc=0" "$out"
eq "조립된 URL(asyncpg, 호스트 db, 포트 5432)" "$URL_EXPECTED" "$(grep '^APP_DATABASE_URL=' "$F")"
eq "다른 줄 보존" "4" "$(grep -c -E '^(APP_PROFILE|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB)=' "$F")"
eq "URL 줄은 하나뿐" "1" "$(grep -c '^APP_DATABASE_URL=' "$F")"
new_case; F="$TMP/u2.env"; printf 'POSTGRES_USER=dbuser\nPOSTGRES_PASSWORD=Pw0rdMARK9\nPOSTGRES_DB=dbname\nAPP_DATABASE_URL=postgresql+asyncpg://other:old@db:5432/x\n' > "$F"; before="$(cksum < "$F")"
out="$(run_lib 'env_ensure_database_url "$1"; echo "rc=$?"' "$F" 2>&1)"
eq "이미 있으면 반환 1" "rc=1" "$out"
eq "이미 있으면 파일 불변" "$before" "$(cksum < "$F")"
new_case; F="$TMP/u3.env"; printf 'POSTGRES_USER=dbuser\nPOSTGRES_DB=dbname\n' > "$F"; before="$(cksum < "$F")"
run_lib 'env_ensure_database_url "$1"' "$F" >/dev/null 2>&1; rc=$?
eq "POSTGRES_PASSWORD가 없으면 반환 2(사전 조건 부족)" "2" "$rc"
eq "비밀번호가 없으면 파일 불변" "$before" "$(cksum < "$F")"
new_case; F="$TMP/u4.env"; printf 'POSTGRES_USER=dbuser\nPOSTGRES_PASSWORD=Pw0rdMARK9\nPOSTGRES_DB=dbname' > "$F"
run_lib 'env_ensure_database_url "$1"' "$F" >/dev/null 2>&1
eq "마지막 줄 개행 없음: 합쳐지지 않음" "POSTGRES_DB=dbname" "$(sed -n 3p "$F")"
eq "URL이 다음 줄" "$URL_EXPECTED" "$(sed -n 4p "$F")"
new_case; F="$TMP/u5.env"; printf 'POSTGRES_USER=dbuser\nPOSTGRES_PASSWORD=Pw0rdMARK9\nPOSTGRES_DB=dbname\n' > "$F"; chmod 600 "$F"; mkdir "$TMP/bin"
: > "$TMP/tool.args"
for tool in awk sed cut grep tr head tail cat; do
  real="$(command -v "$tool")"
  printf '#!/bin/sh\necho "$*" >> "%s/tool.args"\nexec "%s" "$@"\n' "$TMP" "$real" > "$TMP/bin/$tool"; chmod +x "$TMP/bin/$tool"
done
PATH="$TMP/bin:$PATH" run_lib 'env_ensure_database_url "$1"' "$F" >/dev/null 2>&1
eq "URL이 조립됨(래퍼 PATH)" "$URL_EXPECTED" "$(grep '^APP_DATABASE_URL=' "$F")"
check "외부 명령 인자(argv)에 비밀번호가 없음" bash -c "! grep -q Pw0rdMARK9 '$TMP/tool.args'"
eq "권한 600 유지" "-rw-------" "$(perm_of "$F")"

echo "S6 lib 정적 확인"
if [ -f "$LIB" ]; then
  check "lib bash -n" "$TEST_BASH" -n "$LIB"
  check "lib은 source만으로 부작용 없음(출력 없음)" test -z "$(run_lib ':' 2>&1)"
else
  fail "lib 파일 없음(구현 전: red)"
fi

echo
echo "$CASES 케이스, 실패 $FAILURES, 건너뜀 $SKIPS"
[ "$FAILURES" -eq 0 ]
