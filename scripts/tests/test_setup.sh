#!/usr/bin/env bash
# scripts/setup.sh 동작 테스트. 실제 네트워크·sudo·systemd 없이 임시 디렉터리와 가짜 명령으로 검증한다.
#   실행: bash scripts/tests/test_setup.sh          (macOS 기본 /bin/bash 3.2에서도, bash 5에서도 통과해야 한다)
#   함수 단위는 setup.sh를 source해 부르고, 흐름은 임시 저장소 사본의 scripts/setup.sh를 실행한다.
#   계획: artifacts/10-analysis/docker-compose-plan.md (D11, AC13, 끝의 "사용자 결정 추가"가 본문보다 우선)
#         개발 PC 모드는 setup-script-plan.md. dev --server 모드는 폐지됐다.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
REAL_SETUP="$ROOT/scripts/setup.sh"
REAL_LIB="$ROOT/infra/server/lib/env_secrets.sh"
TEST_BASH="${BASH:-/bin/bash}"
ORIG_PATH="$PATH"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILURES=0
CASES=0

ok()   { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
check() { local what="$1"; shift; if "$@"; then ok "$what"; else fail "$what"; fi; }
eq() { # eq <설명> <기대> <실제>
  if [ "$2" = "$3" ]; then ok "$1"; else fail "$1 (기대 '$2', 실제 '$3')"; fi
}
has_text() { # has_text <설명> <텍스트> <부분 문자열>
  case "$2" in *"$3"*) ok "$1" ;; *) fail "$1 ('$3' 없음)" ;; esac
}
lacks_text() {
  case "$2" in *"$3"*) fail "$1 ('$3' 있음)" ;; *) ok "$1" ;; esac
}
perm_of() { ls -ld "$1" | cut -c1-10; }
real_sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
log_has()  { grep -Eq -- "$1" "$LOG"; }
log_none() { ! grep -Eq -- "$1" "$LOG"; }
log_empty() { [ ! -s "$LOG" ]; }
log_line() { grep -En -m1 -- "$1" "$LOG" | cut -d: -f1; }
log_ordered() { # log_ordered <패턴>...  (모두 있고 줄 번호가 오름차순)
  local prev=0 cur pat
  for pat in "$@"; do
    cur="$(log_line "$pat")"
    [ -n "$cur" ] || { echo "    로그에 없음: $pat" >&2; return 1; }
    [ "$cur" -gt "$prev" ] || { echo "    순서 어긋남: $pat" >&2; return 1; }
    prev="$cur"
  done
}

# 시스템 도구 링크만 있는 PATH 디렉터리를 만든다: min_path <가짜 명령 이름...> (BIN의 가짜를 링크)
min_path() {
  local d="$TMP/min.$RANDOM" t src
  mkdir -p "$d"
  for t in grep sed awk tr cat head cut mktemp mkdir rm cp mv chmod ls dirname basename date wc sort tail ln tar gzip install touch tee readlink uniq expr sleep printf test; do
    src="$(PATH="$ORIG_PATH" command -v "$t" 2>/dev/null || true)"
    case "$src" in /*) ln -s "$src" "$d/$t" ;; esac
  done
  ln -s "$(PATH="$ORIG_PATH" command -v env)" "$d/env"
  ln -s "$TEST_BASH" "$d/bash"
  for t in "$@"; do ln -s "$BIN/$t" "$d/$t"; done
  echo "$d"
}

mkstub() { # mkstub <이름> <본문>  (CALLS_LOG에 기록하는 가짜 명령)
  printf '#!/usr/bin/env bash\n%s\n' "$2" > "$BIN/$1"
  chmod +x "$BIN/$1"
}

new_case() {
  CASES=$((CASES + 1))
  TMP="$(mktemp -d "$WORK/case.XXXXXX")"
  BIN="$TMP/bin"; LOG="$TMP/calls.log"; REPO="$TMP/repo"; HOME_DIR="$TMP/home"
  APPHOME="$TMP/app"; FIXTURE="$TMP/fixture"
  mkdir -p "$BIN" "$HOME_DIR" "$APPHOME/incoming" "$FIXTURE" "$TMP/run-systemd" \
           "$REPO/scripts" "$REPO/backend" "$REPO/frontend/dist" "$REPO/infra/server/lib"
  : > "$LOG"
  unset FAKE_UNAME_S FAKE_UNAME_M FAKE_UID FAKE_MUSL FAKE_NODE_VERSION FAKE_GIT_DIRTY FAKE_NOT_GIT SETUP_SUDO FAKE_GIT_CLT_STUB FAKE_XCODE_RC FAKE_COREPACK_FAIL COREPACK_INTEGRITY_KEYS FAKE_NO_DOCKER FAKE_NO_COMPOSE FAKE_NO_NEOINE
  # 임시 저장소 사본: 실제 저장소의 .env*를 건드리지 않게 setup.sh를 복사해 실행한다
  [ -f "$REAL_SETUP" ] && cp "$REAL_SETUP" "$REPO/scripts/setup.sh"
  [ -f "$REAL_LIB" ] && cp "$REAL_LIB" "$REPO/infra/server/lib/env_secrets.sh"
  cp "$ROOT/backend/.env.example" "$REPO/backend/.env.example"

  mkstub uname 'case "${1:-}" in -s) echo "${FAKE_UNAME_S:-Linux}" ;; -m) echo "${FAKE_UNAME_M:-x86_64}" ;; *) echo "${FAKE_UNAME_S:-Linux}" ;; esac'
  mkstub id 'case "$*" in
  "-u neoine") [ -n "${FAKE_NO_NEOINE:-}" ] && [ ! -f "$TMP_STATE/neoine.created" ] && exit 1; echo 4242; exit 0 ;;
  "-g neoine") [ -n "${FAKE_NO_NEOINE:-}" ] && [ ! -f "$TMP_STATE/neoine.created" ] && exit 1; echo 4343; exit 0 ;;
  neoine) [ -n "${FAKE_NO_NEOINE:-}" ] && [ ! -f "$TMP_STATE/neoine.created" ] && exit 1; echo "uid=4242(neoine)"; exit 0 ;;
esac
if [ "${1:-}" = "-u" ]; then echo "${FAKE_UID:-1000}"; else echo "uid=${FAKE_UID:-1000}(tester)"; fi'
  mkstub getent 'if [ "$1 $2" = "passwd neoine" ] && [ -n "${FAKE_NO_NEOINE:-}" ] && [ ! -f "$TMP_STATE/neoine.created" ]; then exit 2; fi
echo "$2:x:4242:4343::"; exit 0'
  mkstub docker 'echo "docker $*" >> "$CALLS_LOG"
if [ -n "${FAKE_NO_DOCKER:-}" ]; then exit 127; fi
if [ "${1:-}" = compose ] && [ -n "${FAKE_NO_COMPOSE:-}" ]; then echo "docker: unknown command: docker compose" >&2; exit 1; fi
exit 0'
  mkstub ldd 'if [ -n "${FAKE_MUSL:-}" ]; then echo "musl libc (x86_64)" >&2; exit 1; else echo "ldd (GNU libc) 2.39"; fi'
  mkstub git 'if [ -n "${FAKE_GIT_CLT_STUB:-}" ]; then echo "xcode-select: note: no developer tools were found" >&2; exit 1; fi
if [ -n "${FAKE_NOT_GIT:-}" ]; then echo "fatal: not a git repository" >&2; exit 128; fi
case "$1" in
  rev-parse) case " $* " in *--short=12*) echo abcdef123456 ;; *) echo true ;; esac ;;
  status) [ -n "${FAKE_GIT_DIRTY:-}" ] && echo " M backend/x.py" ;;
  diff|diff-index|diff-files) [ -z "${FAKE_GIT_DIRTY:-}" ] ;;
  ls-files) [ -n "${FAKE_GIT_DIRTY:-}" ] && echo "new.txt" ;;
esac
exit 0'
  # 가짜 sudo: 기록한 뒤 -u/-H/-n 옵션을 떼고, 파일 명령은 소유자 옵션(-o/-g)을 뺀 채 실제로 실행한다.
  # useradd/adduser/groupadd/usermod/chown/systemctl은 기록만 한다(useradd는 neoine 생성 표시를 남긴다).
  mkstub sudo 'echo "sudo $*" >> "$CALLS_LOG"
while [ $# -gt 0 ]; do
  case "$1" in
    -u) shift 2 ;;
    -H|-n|-E) shift ;;
    *) break ;;
  esac
done
cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
  useradd|adduser) mkdir -p "$TMP_STATE"; : > "$TMP_STATE/neoine.created"; exit 0 ;;
  groupadd|usermod|chown|chgrp|systemctl|loginctl) exit 0 ;;
  install)
    args=()
    while [ $# -gt 0 ]; do
      case "$1" in -o|-g) shift 2 ;; *) args+=("$1"); shift ;; esac
    done
    exec install "${args[@]}" ;;
  mkdir|chmod|cp|mv|tee|touch|grep|cat|rm|sed|test|ln|sh|bash|printf|head|tail|awk|cut|wc|ls|stat)
    exec "$cmd" "$@" ;;
esac
exit 0'
  mkstub uv 'echo "uv $* @$(basename "$PWD")" >> "$CALLS_LOG"
if [ "${1:-}" = run ] && [ "${2:-}" = alembic ]; then echo "alembic-env APP_PROFILE=${APP_PROFILE:-} APP_ENV_FILE=${APP_ENV_FILE:-}" >> "$CALLS_LOG"; fi
exit 0'
  mkstub xcode-select 'echo "xcode-select $*" >> "$CALLS_LOG"; if [ "${1:-}" = "-p" ]; then exit "${FAKE_XCODE_RC:-0}"; fi'
  mkstub corepack 'echo "corepack $* @$(basename "$PWD")" >> "$CALLS_LOG"
case "${FAKE_COREPACK_FAIL:-}" in
  sig) if [ "${COREPACK_INTEGRITY_KEYS:-}" != 0 ]; then echo "Error: Cannot find matching keyid: {\"signatures\":[{\"keyid\":\"SHA256:x\"}]}" >&2; exit 1; fi ;;
  net) echo "Error: connect ETIMEDOUT registry.npmjs.org:443" >&2; exit 1 ;;
esac'
  mkstub node 'case "${1:-}" in --version|-v) echo "${FAKE_NODE_VERSION:-v24.1.0}" ;; *) echo "node $*" >> "$CALLS_LOG" ;; esac'
  mkstub npm 'echo "npm $*" >> "$CALLS_LOG"'
  mkstub systemctl 'echo "systemctl $*" >> "$CALLS_LOG"'
  mkstub brew 'echo "brew $*" >> "$CALLS_LOG"'
  mkstub apt-get 'echo "apt-get $*" >> "$CALLS_LOG"'
  mkstub dnf 'echo "dnf $*" >> "$CALLS_LOG"'
  mkstub yum 'echo "yum $*" >> "$CALLS_LOG"'
  mkstub zypper 'echo "zypper $*" >> "$CALLS_LOG"'
  mkstub pacman 'echo "pacman $*" >> "$CALLS_LOG"'
  mkstub curl 'echo "curl $*" >> "$CALLS_LOG"
url=""; out=""; prev=""
for a in "$@"; do
  case "$a" in http*) url="$a" ;; esac
  [ "$prev" = "-o" ] && out="$a"
  prev="$a"
done
case "$url" in
  *SHASUMS256.txt) src="$FIXTURE/SHASUMS256.txt" ;;
  *.tar.gz) src="$FIXTURE/$(basename "$url")" ;;
  *astral.sh*) echo "echo uv-installer"; exit 0 ;;
  *) exit 22 ;;
esac
[ -f "$src" ] || exit 22
if [ -n "$out" ]; then cp "$src" "$out"; else cat "$src"; fi'

  TMP_STATE="$TMP/state"; mkdir -p "$TMP_STATE"
  export HOME="$HOME_DIR" PATH="$BIN:$ORIG_PATH" CALLS_LOG="$LOG" FIXTURE TMP_STATE \
         SETUP_APP_HOME="$APPHOME" SETUP_SYSTEMD_RUN_DIR="$TMP/run-systemd" \
         SETUP_FILES_DIR="$TMP/data/files" SETUP_DB_DATA_DIR="$TMP/data/postgres"
}

# 가짜 Node 배포본: node_fixture <good|bad>  (linux-x64 v24.1.0)
node_fixture() {
  local name="node-v24.1.0-linux-x64" t
  mkdir -p "$TMP/nodesrc/$name/bin"
  for t in node npm npx corepack; do printf '#!/bin/sh\necho %s\n' "$t" > "$TMP/nodesrc/$name/bin/$t"; chmod +x "$TMP/nodesrc/$name/bin/$t"; done
  tar -czf "$FIXTURE/$name.tar.gz" -C "$TMP/nodesrc" "$name"
  local h; h="$(real_sha "$FIXTURE/$name.tar.gz")"
  [ "$1" = bad ] && h="0000000000000000000000000000000000000000000000000000000000000000"
  {
    echo "1111111111111111111111111111111111111111111111111111111111111111  node-v24.1.0-linux-x64.tar.xz"
    echo "2222222222222222222222222222222222222222222222222222222222222222  node-v24.1.0.pkg"
    echo "$h  $name.tar.gz"
  } > "$FIXTURE/SHASUMS256.txt"
}

in_setup() { # in_setup '<스니펫>' [인자...]  새 bash에서 setup.sh를 source하고 스니펫을 평가(cwd=임시 저장소)
  local snippet="$1"; shift
  ( cd "$REPO" && REPO="$REPO" SNIPPET="$snippet" "$TEST_BASH" -c 'source "$1"; shift; eval "$SNIPPET"' _ "$REPO/scripts/setup.sh" "$@" )
}
capture() { OUT="$("$@" 2>"$TMP/err")"; RC=$?; ERR="$(<"$TMP/err")"; }
run_setup() { # 임시 저장소의 setup.sh를 실행
  ( cd "$REPO" && "$TEST_BASH" "$REPO/scripts/setup.sh" "$@" )
}

# example에서 DB URL만 채운 env 파일을 만든다: make_env <경로> <프로파일>
make_env() {
  sed -e '/^APP_DATABASE_URL=/s/CHANGE_ME/dbpass/' -e "s/^APP_PROFILE=.*/APP_PROFILE=$2/" "$REPO/backend/.env.example" > "$1"
  chmod 600 "$1"
}
secret_of() { grep "^$2=" "$1" | head -1 | cut -d= -f2-; }
EXAMPLE_JWT="$(secret_of "$ROOT/backend/.env.example" APP_JWT_SECRET)"
EXAMPLE_KEY="$(secret_of "$ROOT/backend/.env.example" APP_SETTINGS_ENCRYPTION_KEY)"

echo "bash: $TEST_BASH ($("$TEST_BASH" --version | head -1))"
[ -f "$REAL_SETUP" ] || fail "scripts/setup.sh가 없음(구현 전: red)"

echo "T1 인자(AC1)"
new_case
capture in_setup 'parse_args "$@"; echo "$PROFILE"'
eq "인자 없음: local" "local" "$OUT"
capture in_setup 'parse_args "$@"; echo "$PROFILE"' --profile dev
eq "--profile dev: dev" "dev" "$OUT"
capture in_setup 'parse_args "$@"; echo "$PROFILE"' --profile product
eq "--profile product: product" "product" "$OUT"
capture in_setup 'parse_args "$@"; echo "$SKIP_MIGRATE"' --skip-migrate
eq "--skip-migrate: SKIP_MIGRATE=true" "true" "$OUT"

echo "T2 잘못된 인자는 종료 2이고 아무것도 호출하지 않음(AC2, AC13: --server 거부)"
for args in "--bogus" "--profile staging" "--profile" "--profile local --server" "--server" "--profile dev --server" \
            "--profile product --server" "--profile dev --server --skip-migrate" "--tag x" "--profile product --tag x" \
            "--profile dev --server --tag v1"; do
  new_case
  set -f
  # shellcheck disable=SC2086
  capture run_setup $args
  set +f
  eq "종료 2: $args" "2" "$RC"
  check "호출 기록 없음: $args" log_empty
done

echo "T3 root 실행 거부(AC2)"
new_case; export FAKE_UID=0
capture run_setup
eq "id -u가 0이면 종료 2" "2" "$RC"
check "호출 기록 없음" log_empty

echo "T4 --help(AC3)"
new_case
capture run_setup --help
eq "종료 0" "0" "$RC"
has_text "사용법에 --profile" "$OUT" "--profile"
lacks_text "사용법에 --server 없음" "$OUT" "--server"
lacks_text "사용법에 --tag 없음" "$OUT" "--tag"
has_text "사용법에 product" "$OUT" "product"
capture run_setup -h
eq "-h도 종료 0" "0" "$RC"

echo "T5 OS·아키텍처 판정(AC4)"
for combo in "Darwin arm64 darwin-arm64" "Darwin x86_64 darwin-x64" "Linux x86_64 linux-x64" "Linux aarch64 linux-arm64" "Linux amd64 linux-x64"; do
  set -- $combo
  new_case; export FAKE_UNAME_S="$1" FAKE_UNAME_M="$2"
  capture in_setup 'echo "$(detect_os)-$(detect_arch)"'
  eq "$1/$2" "$3" "$OUT"
done

echo "T6 지원하지 않는 OS·아키텍처(AC4)"
new_case; export FAKE_UNAME_S=FreeBSD
capture in_setup 'detect_os || echo "rc=$?"'; has_text "FreeBSD: 반환값 2" "$OUT" "rc=2"
new_case; export FAKE_UNAME_M=riscv64
capture in_setup 'detect_arch || echo "rc=$?"'; has_text "riscv64: 반환값 2" "$OUT" "rc=2"

echo "T7 musl(AC4·AC15)"
new_case; export FAKE_MUSL=1
capture in_setup 'if is_musl; then echo musl; else echo glibc; fi'
eq "ldd가 musl이면 is_musl 참" "musl" "$OUT"
capture run_setup --profile local
eq "pc 모드 종료 2" "2" "$RC"
has_text "지원하지 않는 배포판 안내" "$OUT$ERR" "지원하지 않는 배포판"
new_case; export FAKE_MUSL=1
capture run_setup --profile product
eq "product 모드 종료 2" "2" "$RC"
check "sudo 호출 없음" log_none '^sudo'
new_case
capture in_setup 'if is_musl; then echo musl; else echo glibc; fi'
eq "GNU ldd면 is_musl 거짓" "glibc" "$OUT"

echo "T8 패키지 관리자 판정(AC5)"
for pm in apt-get dnf yum zypper pacman; do
  new_case
  PATH="$(min_path "$pm")" capture in_setup 'detect_pkg_manager linux'
  eq "${pm}만 있음" "$pm" "$OUT"
done
new_case
PATH="$(min_path)" capture in_setup 'detect_pkg_manager linux'
eq "아무것도 없음: none" "none" "$OUT"
new_case
PATH="$(min_path dnf apt-get)" capture in_setup 'detect_pkg_manager linux'
eq "apt-get이 dnf보다 우선" "apt-get" "$OUT"
new_case
PATH="$(min_path brew)" capture in_setup 'detect_pkg_manager darwin'
eq "darwin+brew: brew" "brew" "$OUT"
new_case
PATH="$(min_path)" capture in_setup 'detect_pkg_manager darwin'
eq "darwin brew 없음: none" "none" "$OUT"

echo "T9 pkg_install 명령 줄(AC5)"
new_case; in_setup 'pkg_install apt-get git curl' >/dev/null 2>&1
check "apt-get update" log_has '^sudo apt-get update$'
check "apt-get install -y" log_has '^sudo apt-get install -y git curl$'
for pm in dnf yum; do
  new_case; in_setup "pkg_install $pm git" >/dev/null 2>&1
  check "$pm install -y" log_has "^sudo $pm install -y git\$"
done
new_case; in_setup 'pkg_install zypper git' >/dev/null 2>&1
check "zypper" log_has '^sudo zypper --non-interactive install git$'
new_case; in_setup 'pkg_install pacman git' >/dev/null 2>&1
check "pacman" log_has '^sudo pacman -S --needed --noconfirm git$'
new_case; in_setup 'pkg_install brew git' >/dev/null 2>&1
check "brew install" log_has '^brew install git$'
check "brew는 sudo를 쓰지 않음" log_none '^sudo'

echo "T10·T11 node_tarball_name(AC7)"
new_case
{
  echo "aa  node-v24.1.0-darwin-arm64.tar.gz"; echo "aa  node-v24.1.0-darwin-arm64.tar.xz"
  echo "aa  node-v24.1.0-darwin-x64.tar.gz";   echo "aa  node-v24.1.0-linux-arm64.tar.gz"
  echo "aa  node-v24.1.0-linux-x64.tar.gz";    echo "aa  node-v24.1.0-linux-x64.tar.xz"
  echo "aa  node-v24.1.0-x64.msi";             echo "aa  node-v24.1.0.pkg"
} > "$TMP/shasums.txt"
for combo in "linux x64" "linux arm64" "darwin x64" "darwin arm64"; do
  set -- $combo
  capture in_setup 'node_tarball_name "$@"' "$TMP/shasums.txt" "$1" "$2"
  eq "$1-$2 한 줄만" "node-v24.1.0-$1-$2.tar.gz" "$OUT"
done
echo "aa  node-v24.1.0-darwin-x64.tar.gz" > "$TMP/shasums2.txt"
capture in_setup 'node_tarball_name "$@" || echo "rc=$?"' "$TMP/shasums2.txt" linux x64
has_text "플랫폼 줄 없음: 반환값 1" "$OUT" "rc=1"

echo "T12 sha256 불일치(AC7)"
new_case; node_fixture bad
capture in_setup 'install_node linux x64'
eq "종료(반환) 1" "1" "$RC"
check "nodejs 디렉터리 없음" test ! -e "$HOME_DIR/.local/lib/nodejs"
check "~/.local/bin/node 없음" test ! -e "$HOME_DIR/.local/bin/node"

echo "T13 sha256 일치(AC7)"
new_case; node_fixture good
capture in_setup 'install_node linux x64'
eq "반환 0" "0" "$RC"
for t in node npm npx corepack; do
  check "링크 $t" test -L "$HOME_DIR/.local/bin/$t"
  check "링크 대상 존재 $t" test -e "$HOME_DIR/.local/bin/$t"
done
check "nodejs 디렉터리에 설치" test -d "$HOME_DIR/.local/lib/nodejs/node-v24.1.0-linux-x64"
check "sudo 기록 없음" log_none '^sudo'

echo "T14 sha256_of(AC7)"
new_case; echo data > "$TMP/f.txt"
mkstub sha256sum 'echo "FAKEHASH  $1"'
PATH="$(min_path sha256sum)" capture in_setup 'sha256_of "$1"' "$TMP/f.txt"
eq "sha256sum만 있음" "FAKEHASH" "$OUT"
new_case; echo data > "$TMP/f.txt"
mkstub shasum 'echo "FAKEHASH  $3"'
PATH="$(min_path shasum)" capture in_setup 'sha256_of "$1"' "$TMP/f.txt"
eq "shasum만 있음" "FAKEHASH" "$OUT"
new_case; echo data > "$TMP/f.txt"
PATH="$(min_path)" capture in_setup 'sha256_of "$1" || echo "rc=$?"' "$TMP/f.txt"
has_text "둘 다 없음: 반환값 1" "$OUT" "rc=1"

echo "T15 node_major·ensure_node(AC7)"
new_case; export FAKE_NODE_VERSION=v22.3.0
capture in_setup 'node_major'; eq "v22.3.0 -> 22" "22" "$OUT"
new_case; export FAKE_NODE_VERSION=v20.1.0
capture in_setup 'node_major'; eq "v20.1.0 -> 20" "20" "$OUT"
new_case
PATH="$(min_path)" capture in_setup 'node_major'; eq "node 없음 -> 0" "0" "$OUT"
new_case; export FAKE_NODE_VERSION=v22.3.0
capture in_setup 'ensure_node linux x64'
check "22 이상이면 다운로드하지 않음" log_none '^curl'
new_case; export FAKE_NODE_VERSION=v20.1.0; node_fixture good
capture in_setup 'ensure_node linux x64'
check "20이면 SHASUMS를 받음" log_has 'curl .*latest-v24\.x/SHASUMS256\.txt'
check "20이면 설치됨" test -L "$HOME_DIR/.local/bin/node"
new_case; export FAKE_NODE_VERSION=v25.0.0
PATH="$(min_path node npm)" capture in_setup 'ensure_node linux x64'
check "corepack이 없으면 npm으로 설치" log_has "^npm install --global --prefix $HOME_DIR/\\.local corepack\$"

echo "T16 새 .env 생성(AC10·AC22)"
new_case
capture in_setup 'prepare_pc_env "$REPO/backend" local'
eq "CHANGE_ME가 남아 반환 3" "3" "$RC"
F="$REPO/backend/.env"
check ".env 생성" test -f "$F"
eq "권한 600" "-rw-------" "$(perm_of "$F")"
eq "APP_PROFILE=local 한 줄" "1" "$(grep -c '^APP_PROFILE=local$' "$F")"
J="$(secret_of "$F" APP_JWT_SECRET)"; K="$(secret_of "$F" APP_SETTINGS_ENCRYPTION_KEY)"
check "JWT 비밀 형식 43자" bash -c "printf %s '$J' | grep -Eq '^[A-Za-z0-9_-]{43}\$'"
check "암호화 키 형식 44자(끝 =)" bash -c "printf %s '$K' | grep -Eq '^[A-Za-z0-9_-]{43}=\$'"
check "JWT가 예시 값과 다름" test "$J" != "$EXAMPLE_JWT"
check "키가 예시 값과 다름" test "$K" != "$EXAMPLE_KEY"
OTHER='^(APP_PROFILE|APP_JWT_SECRET|APP_SETTINGS_ENCRYPTION_KEY)='
check "나머지 줄은 .env.example과 같음" bash -c "diff <(grep -Ev '$OTHER' '$F') <(grep -Ev '$OTHER' '$REPO/backend/.env.example') >/dev/null"

echo "T17 dev는 .env.dev만 만든다(AC10)"
new_case
capture in_setup 'prepare_pc_env "$REPO/backend" dev'
check ".env.dev 생성" test -f "$REPO/backend/.env.dev"
check ".env는 만들지 않음" test ! -e "$REPO/backend/.env"
eq "APP_PROFILE=dev 한 줄" "1" "$(grep -c '^APP_PROFILE=dev$' "$REPO/backend/.env.dev")"
eq "APP_PROFILE 줄은 하나뿐" "1" "$(grep -c '^APP_PROFILE=' "$REPO/backend/.env.dev")"
capture in_setup 'env_file_for local'; eq "env_file_for local" ".env" "$OUT"
capture in_setup 'env_file_for dev'; eq "env_file_for dev" ".env.dev" "$OUT"

echo "T18 비밀 값은 출력에 나오지 않음(AC10)"
new_case
capture in_setup 'prepare_pc_env "$REPO/backend" local'
J="$(secret_of "$REPO/backend/.env" APP_JWT_SECRET)"; K="$(secret_of "$REPO/backend/.env" APP_SETTINGS_ENCRYPTION_KEY)"
lacks_text "stdout에 JWT 없음" "$OUT" "$J"
lacks_text "stderr에 JWT 없음" "$ERR" "$J"
lacks_text "stdout에 키 없음" "$OUT" "$K"
lacks_text "stderr에 키 없음" "$ERR" "$K"

echo "T19 기존 비밀 보존·멱등(AC11·AC14)"
new_case; F="$REPO/backend/.env"; make_env "$F" local
sed -e 's/^APP_JWT_SECRET=.*/APP_JWT_SECRET=customJwtSecretValueCustomJwtSecretValue1/' \
    -e 's/^APP_SETTINGS_ENCRYPTION_KEY=.*/APP_SETTINGS_ENCRYPTION_KEY=customKeyValueCustomKeyValueCustomKeyVa=/' "$F" > "$F.tmp" && mv "$F.tmp" "$F"
chmod 600 "$F"; B1="$(cksum < "$F")"
capture in_setup 'prepare_pc_env "$REPO/backend" local'; eq "첫 실행 0" "0" "$RC"
capture in_setup 'prepare_pc_env "$REPO/backend" local'; eq "두 번째 실행 0" "0" "$RC"
eq "파일 내용 불변" "$B1" "$(cksum < "$F")"

echo "T20 줄이 없으면 덧붙임(개행 보정)(AC11)"
new_case; F="$REPO/backend/.env"
printf 'APP_PROFILE=local\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_SETTINGS_ENCRYPTION_KEY=abc=' > "$F"; chmod 600 "$F"
capture in_setup 'prepare_pc_env "$REPO/backend" local'; eq "반환 0" "0" "$RC"
eq "1줄 그대로" "APP_PROFILE=local" "$(sed -n 1p "$F")"
eq "2줄 그대로" "APP_DATABASE_URL=postgresql://u:p@h/db" "$(sed -n 2p "$F")"
eq "마지막 줄이 합쳐지지 않음" "APP_SETTINGS_ENCRYPTION_KEY=abc=" "$(sed -n 3p "$F")"
check "새 JWT 줄이 따로 덧붙음" bash -c "sed -n 4p '$F' | grep -Eq '^APP_JWT_SECRET=[A-Za-z0-9_-]{43}\$'"
eq "총 4줄" "4" "$(wc -l < "$F" | tr -d ' ')"

echo "T21 공개 예시 값은 바꾸지 않고 경고만(AC11)"
new_case; F="$REPO/backend/.env"; make_env "$F" local
B1="$(cksum < "$F")"
capture in_setup 'prepare_pc_env "$REPO/backend" local'
eq "반환 0" "0" "$RC"
eq "파일 불변" "$B1" "$(cksum < "$F")"
has_text "경고 출력" "$OUT$ERR" "경고"
lacks_text "경고에 예시 키 값 없음" "$OUT$ERR" "$EXAMPLE_KEY"
lacks_text "경고에 예시 JWT 값 없음" "$OUT$ERR" "$EXAMPLE_JWT"

echo "T22 DB URL 미설정은 종료 3(AC12)"
new_case; F="$REPO/backend/.env"
capture in_setup 'prepare_pc_env "$REPO/backend" local'; eq "CHANGE_ME: 반환 3" "3" "$RC"
has_text "변수 이름 안내" "$OUT$ERR" "APP_DATABASE_URL"
has_text "파일 경로 안내" "$OUT$ERR" ".env"
new_case; F="$REPO/backend/.env"; make_env "$F" local; grep -v '^APP_DATABASE_URL=' "$F" > "$F.tmp" && mv "$F.tmp" "$F"
capture in_setup 'prepare_pc_env "$REPO/backend" local'; eq "URL 줄 없음: 반환 3" "3" "$RC"
new_case
capture run_setup --profile local
eq "흐름 종료 3" "3" "$RC"
check "마이그레이션 호출 없음" log_none 'alembic'

echo "T23~T25 pc 흐름(AC9·AC13)"
new_case; make_env "$REPO/backend/.env.dev" dev
B1="$(cksum < "$REPO/backend/.env.dev")"
capture run_setup --profile dev
eq "종료 0" "0" "$RC"
check "순서: uv sync -> pnpm install -> 마이그레이션" log_ordered '^uv sync --locked @backend$' '^corepack pnpm install --frozen-lockfile @frontend$' '^uv run alembic upgrade head @backend$'
check "마이그레이션 환경 APP_PROFILE=dev, APP_ENV_FILE=.env.dev" log_has '^alembic-env APP_PROFILE=dev APP_ENV_FILE=(.*/)?\.env\.dev$'
eq "비밀 줄 불변(재실행 안전)" "$B1" "$(cksum < "$REPO/backend/.env.dev")"
capture run_setup --profile dev; eq "두 번째 실행도 0" "0" "$RC"
eq "두 번째 실행 후에도 불변" "$B1" "$(cksum < "$REPO/backend/.env.dev")"
lacks_text "출력에 JWT 예시 값 없음" "$OUT$ERR" "$EXAMPLE_JWT"
new_case; make_env "$REPO/backend/.env" local
capture run_setup
eq "인자 없음(local) 종료 0" "0" "$RC"
check "마이그레이션 환경 APP_PROFILE=local, APP_ENV_FILE=.env" log_has '^alembic-env APP_PROFILE=local APP_ENV_FILE=(.*/)?\.env$'
new_case; make_env "$REPO/backend/.env.dev" dev
capture run_setup --profile dev --skip-migrate
eq "--skip-migrate 종료 0" "0" "$RC"
check "마이그레이션 기록 없음" log_none 'alembic'
check "의존성 설치는 수행" log_has '^uv sync --locked @backend$'

set_kv() { # set_kv <파일> <이름> <값>  (줄을 바꾸거나 덧붙임, 값은 인자로만 쓰는 테스트 전용 더미)
  awk -v n="$2" -v v="$3" 'BEGIN{p=n"="} index($0,p)==1{print p v; d=1; next} {print} END{if(!d)print p v}' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}
APP_ENV() { echo "$APPHOME/.env"; }
DEPLOY_ENV() { echo "$APPHOME/deploy.env"; }
PRODUCT_NO_CALLS='docker compose (up|pull|run|exec|down|--profile|-p)|deploy\.sh|alembic|pnpm|corepack|npm |^uv |^docker login'

echo "P1 product 첫 실행: 계정·디렉터리·.env·deploy.env를 만들고 사람이 채울 값을 알려 종료 3(AC13)"
new_case
capture run_setup --profile product
eq "사람이 채울 값이 남아 종료 3" "3" "$RC"
check "순서: docker compose 점검 -> docker 그룹 -> 디렉터리" \
  log_ordered '^docker compose version' 'usermod -aG docker neoine' '(mkdir|install).*deploys'
for d in incoming deploys certs backups; do check "디렉터리 $APPHOME/$d" test -d "$APPHOME/$d"; done
check "첨부 디렉터리" test -d "$TMP/data/files"
check "DB 데이터 디렉터리" test -d "$TMP/data/postgres"
eq "backups 권한 0700" "drwx------" "$(perm_of "$APPHOME/backups")"
E="$(APP_ENV)"; D="$(DEPLOY_ENV)"
check ".env 생성" test -f "$E"
eq ".env 권한 600" "-rw-------" "$(perm_of "$E")"
eq "APP_PROFILE=product" "1" "$(grep -c '^APP_PROFILE=product$' "$E")"
eq "POSTGRES_USER=neoine" "1" "$(grep -c '^POSTGRES_USER=neoine$' "$E")"
eq "POSTGRES_DB=neoinesales" "1" "$(grep -c '^POSTGRES_DB=neoinesales$' "$E")"
PW="$(secret_of "$E" POSTGRES_PASSWORD)"
check "POSTGRES_PASSWORD는 영숫자 32자" bash -c "printf %s '$PW' | grep -Eq '^[A-Za-z0-9]{32}\$'"
eq "APP_DATABASE_URL이 같은 비밀번호·db 호스트로 조립됨" \
  "postgresql+asyncpg://neoine:${PW}@db:5432/neoinesales" "$(secret_of "$E" APP_DATABASE_URL)"
J="$(secret_of "$E" APP_JWT_SECRET)"; K="$(secret_of "$E" APP_SETTINGS_ENCRYPTION_KEY)"
check "JWT 비밀 43자" bash -c "printf %s '$J' | grep -Eq '^[A-Za-z0-9_-]{43}\$'"
check "암호화 키 44자(끝 =)" bash -c "printf %s '$K' | grep -Eq '^[A-Za-z0-9_-]{43}=\$'"
check "JWT가 예시 값과 다름" test "$J" != "$EXAMPLE_JWT"
check "deploy.env 생성" test -f "$D"
eq "deploy.env 권한 640" "-rw-r-----" "$(perm_of "$D")"
eq "APP_UID=neoine UID" "APP_UID=4242" "$(grep '^APP_UID=' "$D")"
eq "APP_GID=neoine GID" "APP_GID=4343" "$(grep '^APP_GID=' "$D")"
eq "API_WORKERS=4" "API_WORKERS=4" "$(grep '^API_WORKERS=' "$D")"
eq "APP_PROFILE=product(deploy.env)" "APP_PROFILE=product" "$(grep '^APP_PROFILE=' "$D")"
eq "APP_HOME" "APP_HOME=$APPHOME" "$(grep '^APP_HOME=' "$D")"
eq "CERT_DIR" "CERT_DIR=$APPHOME/certs" "$(grep '^CERT_DIR=' "$D")"
eq "DB_DATA_DIR" "DB_DATA_DIR=$TMP/data/postgres" "$(grep '^DB_DATA_DIR=' "$D")"
eq "SERVER_NAME은 CHANGE_ME" "SERVER_NAME=CHANGE_ME" "$(grep '^SERVER_NAME=' "$D")"
eq "REGISTRY는 CHANGE_ME" "REGISTRY=CHANGE_ME" "$(grep '^REGISTRY=' "$D")"
check "deploy.env에 비밀 변수가 없음" bash -c "! grep -Eq 'PASSWORD|JWT|ENCRYPTION|DATABASE_URL|SENTRY' '$D'"
for name in SERVER_NAME REGISTRY APP_SENTRY_DSN fullchain.pem privkey.pem; do
  has_text "사람이 넣을 값 이름 안내: $name" "$OUT$ERR" "$name"
done
has_text "레지스트리 로그인 명령 안내" "$OUT$ERR" "docker login"
has_text "neoine 계정으로 로그인하라는 안내" "$OUT$ERR" "neoine"
lacks_text "stdout에 DB 비밀번호 없음" "$OUT" "$PW"
lacks_text "stderr에 DB 비밀번호 없음" "$ERR" "$PW"
lacks_text "stdout에 JWT 없음" "$OUT" "$J"
lacks_text "stderr에 JWT 없음" "$ERR" "$J"
lacks_text "stdout에 암호화 키 없음" "$OUT" "$K"
lacks_text "stderr에 암호화 키 없음" "$ERR" "$K"
lacks_text "출력에 DB URL 없음" "$OUT$ERR" "@db:5432"
check "배포·컨테이너 기동·마이그레이션·빌드 호출 없음" log_none "$PRODUCT_NO_CALLS"

echo "P2 product 다시 실행: 값이 바뀌지 않음(멱등)(AC13)"
new_case
capture run_setup --profile product
E="$(APP_ENV)"; D="$(DEPLOY_ENV)"
B1="$(cksum < "$E")"; B2="$(cksum < "$D")"
capture run_setup --profile product
eq "두 번째도 종료 3" "3" "$RC"
eq ".env 불변(비밀 재생성 없음)" "$B1" "$(cksum < "$E")"
eq "deploy.env 불변" "$B2" "$(cksum < "$D")"
eq "POSTGRES_PASSWORD 줄은 하나뿐" "1" "$(grep -c '^POSTGRES_PASSWORD=' "$E")"
eq "APP_DATABASE_URL 줄은 하나뿐" "1" "$(grep -c '^APP_DATABASE_URL=' "$E")"

echo "P3 사람이 값을 채우면 종료 0이고 Jenkins 배포 안내(AC13)"
new_case
capture run_setup --profile product
E="$(APP_ENV)"; D="$(DEPLOY_ENV)"
set_kv "$D" SERVER_NAME sales.example.com
set_kv "$D" REGISTRY registry.example.com
set_kv "$E" APP_SENTRY_DSN "https://key@sentry.example.com/1"
: > "$APPHOME/certs/fullchain.pem"; : > "$APPHOME/certs/privkey.pem"
: > "$LOG"
capture run_setup --profile product
eq "종료 0" "0" "$RC"
has_text "배포는 Jenkins Deploy: Product 안내" "$OUT$ERR" "Jenkins"
has_text "레지스트리 로그인 안내가 계속 나옴" "$OUT$ERR" "docker login"
lacks_text "Sentry DSN 값 비출력" "$OUT$ERR" "sentry.example.com"
check "배포·컨테이너 기동·마이그레이션·빌드 호출 없음" log_none "$PRODUCT_NO_CALLS"

echo "P3b 하나라도 비어 있으면 종료 3이고 그 이름만 알림(AC13)"
new_case
capture run_setup --profile product
E="$(APP_ENV)"; D="$(DEPLOY_ENV)"
set_kv "$D" SERVER_NAME sales.example.com
set_kv "$D" REGISTRY registry.example.com
: > "$APPHOME/certs/fullchain.pem"; : > "$APPHOME/certs/privkey.pem"
capture run_setup --profile product
eq "APP_SENTRY_DSN만 없음: 종료 3" "3" "$RC"
has_text "APP_SENTRY_DSN 이름" "$OUT$ERR" "APP_SENTRY_DSN"
set_kv "$E" APP_SENTRY_DSN "https://key@sentry.example.com/1"
rm "$APPHOME/certs/privkey.pem"
capture run_setup --profile product
eq "privkey.pem만 없음: 종료 3" "3" "$RC"
has_text "privkey.pem 이름" "$OUT$ERR" "privkey.pem"

echo "P4 docker 또는 docker compose가 없으면 종료 2이고 아무것도 만들지 않음(AC13)"
new_case; export FAKE_NO_DOCKER=1
capture run_setup --profile product
eq "docker 실패: 종료 2" "2" "$RC"
check "usermod·디렉터리 생성 없음" log_none 'usermod|mkdir|install'
check ".env 없음" test ! -e "$(APP_ENV)"
check "deploy.env 없음" test ! -e "$(DEPLOY_ENV)"
new_case; export FAKE_NO_COMPOSE=1
capture run_setup --profile product
eq "docker compose 없음: 종료 2" "2" "$RC"
check "usermod 없음" log_none 'usermod'
check ".env 없음" test ! -e "$(APP_ENV)"
new_case
PATH="$(min_path uname ldd sudo id getent systemctl)" capture run_setup --profile product
eq "docker 명령 자체가 없음: 종료 2" "2" "$RC"
check ".env 없음" test ! -e "$(APP_ENV)"
has_text "docker를 직접 설치하라는 안내" "$OUT$ERR" "docker"
check "docker를 설치하려 하지 않음" log_none 'apt-get|dnf|yum|zypper|pacman|brew'

echo "P5 neoine 계정이 없을 때만 만들고 docker 그룹에 넣음(AC13)"
new_case; export FAKE_NO_NEOINE=1
capture run_setup --profile product
check "계정을 만듦" log_has '(useradd|adduser).*neoine'
check "계정 생성 뒤 docker 그룹 추가" log_ordered '(useradd|adduser).*neoine' 'usermod -aG docker neoine'
eq "deploy.env의 UID는 만든 계정의 UID" "APP_UID=4242" "$(grep '^APP_UID=' "$(DEPLOY_ENV)")"
new_case
capture run_setup --profile product
check "계정이 있으면 만들지 않음" log_none '(useradd|adduser)'
check "그래도 docker 그룹은 보장" log_has 'usermod -aG docker neoine'

echo "P6 APP_DATABASE_URL만 있고 POSTGRES_PASSWORD가 없으면 새 비밀번호를 만들지 않고 종료 3(AC13)"
new_case
mkdir -p "$APPHOME"
printf 'APP_PROFILE=product\nAPP_DATABASE_URL=postgresql+asyncpg://neoine:OLDPASS@db:5432/neoinesales\n' > "$APPHOME/.env"; chmod 600 "$APPHOME/.env"
capture run_setup --profile product
eq "종료 3" "3" "$RC"
check "POSTGRES_PASSWORD 줄을 만들지 않음" bash -c "! grep -q '^POSTGRES_PASSWORD=' '$APPHOME/.env'"
eq "APP_DATABASE_URL 그대로" "postgresql+asyncpg://neoine:OLDPASS@db:5432/neoinesales" "$(secret_of "$APPHOME/.env" APP_DATABASE_URL)"
has_text "POSTGRES_PASSWORD 이름만 안내" "$OUT$ERR" "POSTGRES_PASSWORD"
lacks_text "기존 비밀번호 비출력" "$OUT$ERR" "OLDPASS"

echo "P7 POSTGRES_*는 있고 APP_DATABASE_URL이 없으면 같은 값으로 조립(AC13)"
new_case
printf 'APP_PROFILE=product\nPOSTGRES_USER=neoine\nPOSTGRES_DB=neoinesales\nPOSTGRES_PASSWORD=KeepThisPass123\n' > "$APPHOME/.env"; chmod 600 "$APPHOME/.env"
capture run_setup --profile product
eq "URL 조립" "postgresql+asyncpg://neoine:KeepThisPass123@db:5432/neoinesales" "$(secret_of "$APPHOME/.env" APP_DATABASE_URL)"
eq "비밀번호 그대로" "KeepThisPass123" "$(secret_of "$APPHOME/.env" POSTGRES_PASSWORD)"
lacks_text "비밀번호 비출력" "$OUT$ERR" "KeepThisPass123"

echo "P8 기존 .env 값 보존(AC13)"
new_case
printf 'APP_PROFILE=product\nAPP_JWT_SECRET=customJwtSecretValueCustomJwtSecretValue1\nAPP_SETTINGS_ENCRYPTION_KEY=customKeyValueCustomKeyValueCustomKeyVa=\nPOSTGRES_USER=neoine\nPOSTGRES_DB=neoinesales\nPOSTGRES_PASSWORD=KeepThisPass123\nAPP_DATABASE_URL=postgresql+asyncpg://neoine:KeepThisPass123@db:5432/neoinesales\n' > "$APPHOME/.env"; chmod 600 "$APPHOME/.env"
BEFORE="$(cksum < "$APPHOME/.env")"
capture run_setup --profile product
eq "모든 키가 있으면 .env 불변" "$BEFORE" "$(cksum < "$APPHOME/.env")"

echo "P9 기존 deploy.env는 APP_UID·APP_GID 줄만 보장(AC13)"
new_case
printf 'SERVER_NAME=keep.example.com\nREGISTRY=keep-registry.example.com\nAPP_PROFILE=product\n' > "$APPHOME/deploy.env"; chmod 640 "$APPHOME/deploy.env"
capture run_setup --profile product
eq "SERVER_NAME 보존" "SERVER_NAME=keep.example.com" "$(grep '^SERVER_NAME=' "$APPHOME/deploy.env")"
eq "REGISTRY 보존" "REGISTRY=keep-registry.example.com" "$(grep '^REGISTRY=' "$APPHOME/deploy.env")"
eq "APP_UID 추가" "APP_UID=4242" "$(grep '^APP_UID=' "$APPHOME/deploy.env")"
eq "APP_GID 추가" "APP_GID=4343" "$(grep '^APP_GID=' "$APPHOME/deploy.env")"
new_case
printf 'SERVER_NAME=keep.example.com\nAPP_UID=7777\nAPP_GID=7778\n' > "$APPHOME/deploy.env"; chmod 640 "$APPHOME/deploy.env"
capture run_setup --profile product
eq "이미 있는 APP_UID는 그대로" "1" "$(grep -c '^APP_UID=' "$APPHOME/deploy.env")"
eq "APP_UID 값 유지" "APP_UID=7777" "$(grep '^APP_UID=' "$APPHOME/deploy.env")"

echo "P10 리눅스가 아니면 종료 2(AC13)"
new_case; export FAKE_UNAME_S=Darwin FAKE_UNAME_M=arm64
capture run_setup --profile product
eq "macOS: 종료 2" "2" "$RC"
check "sudo 기록 없음" log_none '^sudo'
check ".env 없음" test ! -e "$(APP_ENV)"

echo "R1 macOS: git이 CLT 스텁일 때만 중단(AC5, 리뷰 Minor)"
new_case; export FAKE_XCODE_RC=2
capture in_setup 'ensure_base_tools darwin'
eq "CLT 없음이어도 실제 git이 있으면 중단하지 않음" "0" "$RC"
lacks_text "CLT 설치 안내를 내지 않음" "$OUT$ERR" "xcode-select --install"
new_case; export FAKE_XCODE_RC=2 FAKE_GIT_CLT_STUB=1
capture in_setup 'ensure_base_tools darwin'
eq "git이 CLT 스텁뿐이면 중단(반환 1)" "1" "$RC"
has_text "xcode-select --install 안내" "$OUT$ERR" "xcode-select --install"
new_case; export FAKE_XCODE_RC=0
capture in_setup 'ensure_base_tools darwin'
eq "CLT가 있고 git도 있으면 통과" "0" "$RC"

echo "R2 corepack 서명 오류일 때만 검증 키 확인을 끔(AC9, 리뷰 Minor)"
new_case; export FAKE_COREPACK_FAIL=sig
capture in_setup 'corepack_ready; echo "KEYS=${COREPACK_INTEGRITY_KEYS:-unset}"'
has_text "서명 오류: COREPACK_INTEGRITY_KEYS=0" "$OUT" "KEYS=0"
has_text "껐다는 사실을 안내" "$OUT$ERR" "COREPACK_INTEGRITY_KEYS"
new_case; export FAKE_COREPACK_FAIL=net
capture in_setup 'corepack_ready; echo "KEYS=${COREPACK_INTEGRITY_KEYS:-unset}"'
has_text "네트워크 오류: 켜지 않음" "$OUT" "KEYS=unset"
lacks_text "안내도 없음" "$OUT$ERR" "COREPACK_INTEGRITY_KEYS"
new_case
capture in_setup 'corepack_ready; echo "KEYS=${COREPACK_INTEGRITY_KEYS:-unset}"'
has_text "정상: 켜지 않음" "$OUT" "KEYS=unset"

echo "T33 bash 3.2 호환 정적 검사(AC8)"
for f in "$REAL_SETUP" "$REAL_LIB"; do
  name="$(basename "$f")"
  if [ ! -f "$f" ]; then fail "$name 파일 없음(구현 전: red)"; continue; fi
  body="$(grep -v '^[[:space:]]*#' "$f")"
  for pat in 'declare -A' 'mapfile' 'readarray' ',,}' '^^}' 'declare -n' '&>>' '|&' 'sed -i' 'readlink -f' 'base64 -w' 'grep -P' 'set -x'; do
    if printf '%s\n' "$body" | grep -Fq -e "$pat"; then fail "$name: 금지 구문 '$pat'"; else ok "$name: '$pat' 없음"; fi
  done
  check "$name bash -n" "$TEST_BASH" -n "$f"
done

echo "T34 구 이름 참조 없음(AC23)"
OLD="setup-""ubuntu"
HITS="$(git -C "$ROOT" grep -l -e "$OLD" -- ':!artifacts' ':!CLAUDE.md' 2>/dev/null || true)"
eq "저장소에 구 이름 참조 없음" "" "$HITS"
check "구 파일이 없음" test ! -e "$ROOT/scripts/$OLD.sh"

echo "T35 Jenkins 등록(AC14)"
for pat in 'scripts/setup\.sh' 'infra/server/lib/env_secrets\.sh' 'scripts/tests/test_setup\.sh' 'infra/server/tests/test_env_secrets\.sh' \
           'infra/docker/tests/test_deploy\.sh' 'infra/docker/tests/test_build_images\.sh' 'infra/docker/tests/test_compose\.sh'; do
  check "Jenkinsfile에 $pat" grep -Eq "$pat" "$ROOT/Jenkinsfile"
done
check "Jenkinsfile이 test_compose를 REQUIRE_DOCKER=1로 실행" grep -Eq 'REQUIRE_DOCKER=1.*test_compose\.sh' "$ROOT/Jenkinsfile"

echo "T37 폐지된 서버 모드·옛 자산 참조 없음(AC13·AC15)"
check "setup.sh에 --server 옵션 처리가 없음" bash -c "! grep -v '^[[:space:]]*#' '$REAL_SETUP' | grep -Eq -- '--server\)'"
check "setup.sh가 bootstrap.sh를 부르지 않음" bash -c "! grep -v '^[[:space:]]*#' '$REAL_SETUP' | grep -q 'bootstrap\.sh'"
check "infra/server/bootstrap.sh 삭제됨" test ! -e "$ROOT/infra/server/bootstrap.sh"
check "infra/server/deploy.sh 삭제됨" test ! -e "$ROOT/infra/server/deploy.sh"
check "infra/build_release.sh 삭제됨" test ! -e "$ROOT/infra/build_release.sh"
check "infra/server/systemd 삭제됨" test ! -e "$ROOT/infra/server/systemd"
check "infra/server/nginx 삭제됨" test ! -e "$ROOT/infra/server/nginx"
check "infra/server/sudoers 삭제됨" test ! -e "$ROOT/infra/server/sudoers"
check "옛 infra/server/tests/test_deploy.sh 삭제됨" test ! -e "$ROOT/infra/server/tests/test_deploy.sh"
check "backend/src/app/jobs 삭제됨" test ! -e "$ROOT/backend/src/app/jobs"

echo "R4 임시 디렉터리 정리(리뷰 Nit)"
EXIT_TRAP="$(trap -p EXIT)"
case "$EXIT_TRAP" in *rm*"$"WORK*) ok "EXIT trap이 임시 작업 디렉터리를 지움" ;; *) fail "EXIT trap이 임시 작업 디렉터리를 지움 ('$EXIT_TRAP')" ;; esac
check "케이스 디렉터리는 작업 디렉터리 아래" test "${TMP#"$WORK"/}" != "$TMP"

echo
echo "$CASES 케이스, 실패 $FAILURES"
[ "$FAILURES" -eq 0 ]
