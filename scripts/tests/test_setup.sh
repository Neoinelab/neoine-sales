#!/usr/bin/env bash
# scripts/setup.sh 동작 테스트. 실제 네트워크·sudo·systemd 없이 임시 디렉터리와 가짜 명령으로 검증한다.
#   실행: bash scripts/tests/test_setup.sh          (macOS 기본 /bin/bash 3.2에서도, bash 5에서도 통과해야 한다)
#   함수 단위는 setup.sh를 source해 부르고, 흐름은 임시 저장소 사본의 scripts/setup.sh를 실행한다.
#   계획: artifacts/10-analysis/setup-script-plan.md (끝의 "사용자 결정(2026-10-29)"이 본문보다 우선)
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
perm_of() { ls -l "$1" | cut -c1-10; }
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
  unset FAKE_UNAME_S FAKE_UNAME_M FAKE_UID FAKE_MUSL FAKE_NODE_VERSION FAKE_GIT_DIRTY FAKE_NOT_GIT FAKE_DEPLOY_RC SETUP_SUDO FAKE_GIT_CLT_STUB FAKE_XCODE_RC FAKE_COREPACK_FAIL COREPACK_INTEGRITY_KEYS
  # 임시 저장소 사본: 실제 저장소의 .env*를 건드리지 않게 setup.sh를 복사해 실행한다
  [ -f "$REAL_SETUP" ] && cp "$REAL_SETUP" "$REPO/scripts/setup.sh"
  [ -f "$REAL_LIB" ] && cp "$REAL_LIB" "$REPO/infra/server/lib/env_secrets.sh"
  cp "$ROOT/backend/.env.example" "$REPO/backend/.env.example"
  printf '#!/usr/bin/env bash\necho "bootstrap.sh $*" >> "$CALLS_LOG"\n' > "$REPO/infra/server/bootstrap.sh"
  echo '#!/usr/bin/env bash' > "$REPO/infra/server/deploy.sh"
  cat > "$REPO/infra/build_release.sh" <<'STUB'
#!/usr/bin/env bash
echo "build_release.sh $*" >> "$CALLS_LOG"
mkdir -p "$(dirname "$0")/../build"
: > "$(dirname "$0")/../build/neoine-sales-$1.tar.gz"
STUB

  mkstub uname 'case "${1:-}" in -s) echo "${FAKE_UNAME_S:-Linux}" ;; -m) echo "${FAKE_UNAME_M:-x86_64}" ;; *) echo "${FAKE_UNAME_S:-Linux}" ;; esac'
  mkstub id 'if [ "${1:-}" = "-u" ]; then echo "${FAKE_UID:-1000}"; else echo "uid=${FAKE_UID:-1000}(tester)"; fi'
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
  # 가짜 sudo: 기록하고, grep 명령(.env 점검)만 실제로 실행한다. deploy.sh 호출은 FAKE_DEPLOY_RC로 종료 코드를 준다
  mkstub sudo 'echo "sudo $*" >> "$CALLS_LOG"
i=0
for a in "$@"; do
  i=$((i + 1))
  if [ "$a" = grep ]; then shift $((i - 1)); exec "$@"; fi
done
case "$*" in *"-u neoine"*deploy.sh*) exit "${FAKE_DEPLOY_RC:-0}" ;; esac
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

  export HOME="$HOME_DIR" PATH="$BIN:$ORIG_PATH" CALLS_LOG="$LOG" FIXTURE \
         SETUP_APP_HOME="$APPHOME" SETUP_SYSTEMD_RUN_DIR="$TMP/run-systemd"
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

echo "T1 인자와 모드(AC1)"
new_case
capture in_setup 'parse_args "$@"; echo "$PROFILE|$(resolve_mode)"'
eq "인자 없음: local|pc" "local|pc" "$OUT"
capture in_setup 'parse_args "$@"; echo "$PROFILE|$(resolve_mode)"' --profile dev
eq "--profile dev: dev|pc" "dev|pc" "$OUT"
capture in_setup 'parse_args "$@"; echo "$PROFILE|$(resolve_mode)"' --profile dev --server
eq "--profile dev --server: dev|server" "dev|server" "$OUT"
capture in_setup 'parse_args "$@"; echo "$PROFILE|$(resolve_mode)"' --profile product
eq "--profile product: product|server" "product|server" "$OUT"
capture in_setup 'parse_args "$@"; echo "$SKIP_MIGRATE|$TAG"' --profile dev --server --tag v1.2
eq "--tag 값을 TAG에 담는다" "false|v1.2" "$OUT"
capture in_setup 'parse_args "$@"; echo "$SKIP_MIGRATE"' --skip-migrate
eq "--skip-migrate: SKIP_MIGRATE=true" "true" "$OUT"

echo "T2 잘못된 인자는 종료 2이고 아무것도 호출하지 않음(AC2)"
for args in "--bogus" "--profile staging" "--profile" "--profile local --server" "--profile dev --server --skip-migrate" \
            "--profile product --skip-migrate" "--tag x" "--profile dev --server --tag ../x" "--profile dev --server --tag a;b" \
            "--profile dev --server --tag -x"; do
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
has_text "사용법에 --server" "$OUT" "--server"
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
capture run_setup --profile dev --server
eq "서버 모드 종료 2" "2" "$RC"
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

echo "T26 서버 모드 지원 여부(AC15)"
new_case; export FAKE_UNAME_S=Darwin FAKE_UNAME_M=arm64
capture run_setup --profile dev --server
eq "macOS: 종료 2" "2" "$RC"; check "sudo 기록 없음" log_none '^sudo'
has_text "대안(--profile local|dev) 안내" "$OUT$ERR" "--profile"
new_case; rmdir "$TMP/run-systemd"
capture in_setup 'check_server_supported || echo "rc=$?"'
has_text "run 디렉터리 없음: 반환 2" "$OUT" "rc=2"
new_case
capture in_setup 'check_server_supported && echo "rc=0"'
has_text "정상 환경: 반환 0" "$OUT" "rc=0"
new_case
PATH="$(min_path uname ldd sudo)" capture in_setup 'check_server_supported || echo "rc=$?"'
has_text "systemctl 없음: 반환 2" "$OUT" "rc=2"
new_case
PATH="$(min_path uname ldd systemctl)" capture in_setup 'check_server_supported || echo "rc=$?"'
has_text "sudo 없음: 반환 2" "$OUT" "rc=2"

echo "T27·T28 서버 .env 점검(AC17)"
new_case; F="$TMP/server.env"; export SETUP_SUDO=env
base_env() { printf 'APP_PROFILE=%s\nAPP_DATABASE_URL=postgresql://u:SECRETMARK@h/db\nAPP_JWT_SECRET=JWTMARK\nAPP_SETTINGS_ENCRYPTION_KEY=KEYMARK\n' "$1"; }
base_env dev > "$F"; echo APP_DEV_LOGIN_ENABLED=false >> "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "dev 완전: 0" "0" "$RC"; eq "stdout 비어 있음" "" "$OUT"
lacks_text "dev 로그인 안내 없음" "$ERR" "APP_DEV_LOGIN_ENABLED"
base_env dev > "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "APP_DEV_LOGIN_ENABLED=false 없어도 0" "0" "$RC"
has_text "공유 서버 안내(stderr)" "$ERR" "APP_DEV_LOGIN_ENABLED"
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:CHANGE_ME@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "CHANGE_ME: 3" "3" "$RC"; has_text "APP_DATABASE_URL 이름" "$OUT" "APP_DATABASE_URL"
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "빈 DB URL: 3" "3" "$RC"; has_text "APP_DATABASE_URL 이름" "$OUT" "APP_DATABASE_URL"
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:SECRETMARK@h/db\n' > "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "비밀 없음: 3" "3" "$RC"
has_text "JWT 이름" "$OUT" "APP_JWT_SECRET"; has_text "키 이름" "$OUT" "APP_SETTINGS_ENCRYPTION_KEY"
lacks_text "출력에 값 없음(stdout)" "$OUT" "SECRETMARK"; lacks_text "출력에 값 없음(stderr)" "$ERR" "SECRETMARK"
base_env product > "$F"
capture in_setup 'check_server_env "$1" product' "$F"
eq "product인데 SENTRY 없음: 3" "3" "$RC"; has_text "APP_SENTRY_DSN 이름" "$OUT" "APP_SENTRY_DSN"
echo 'APP_SENTRY_DSN=https://x@sentry.example/1' >> "$F"
capture in_setup 'check_server_env "$1" product' "$F"
eq "product 완전: 0" "0" "$RC"
base_env product > "$F"
capture in_setup 'check_server_env "$1" dev' "$F"
eq "APP_PROFILE 불일치: 3" "3" "$RC"; has_text "APP_PROFILE 이름" "$OUT" "APP_PROFILE"

echo "T29 default_tag(dev)(AC18)"
new_case
capture in_setup 'default_tag'
check "깨끗함: 12자 해시" bash -c "printf %s '$OUT' | grep -Eq '^[0-9a-f]{12}\$'"
new_case; export FAKE_GIT_DIRTY=1
capture in_setup 'default_tag'
check "dirty: <hash>-dirty-<14자리>" bash -c "printf %s '$OUT' | grep -Eq '^abcdef123456-dirty-[0-9]{14}\$'"
check "deploy.sh 태그 규칙 통과" bash -c "printf %s '$OUT' | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*\$'"
new_case; export FAKE_NOT_GIT=1
capture in_setup 'default_tag'
check "git 아님: local-<14자리>" bash -c "printf %s '$OUT' | grep -Eq '^local-[0-9]{14}\$'"

echo "T31 dev --server 흐름(AC16, nginx 제외)"
new_case
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:SECRETMARK@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\nAPP_DEV_LOGIN_ENABLED=false\n' > "$APPHOME/.env"
capture run_setup --profile dev --server
eq "종료 0" "0" "$RC"
check "순서: bootstrap -> .env 점검 -> pnpm install -> pnpm build -> build_release -> incoming 복사 -> deploy" \
  log_ordered 'sudo .*bash .*infra/server/bootstrap\.sh dev$' 'sudo .*grep .*\.env' \
  '^corepack pnpm install --frozen-lockfile @frontend$' '^corepack pnpm build @frontend$' \
  '^build_release\.sh abcdef123456$' 'sudo .*neoine.*incoming' 'sudo -u neoine -H bash .*/incoming/deploy\.sh dev abcdef123456$'
check "incoming 복사: 소유자 neoine·권한 640" bash -c "grep -E 'sudo' '$LOG' | grep incoming | grep -v 'deploy.sh dev' | grep neoine | grep -q 640"
check "nginx를 설치·enable하지 않음" log_none 'nginx'
check "호출 사용자의 uv 실행 없음" log_none '^uv '
check "마이그레이션은 deploy.sh에 맡김(직접 실행 없음)" log_none 'alembic'
lacks_text "출력에 DB 값 없음" "$OUT$ERR" "SECRETMARK"
new_case
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$APPHOME/.env"
capture run_setup --profile dev --server --tag v1.2.3
eq "--tag 사용 종료 0" "0" "$RC"
check "build_release와 deploy에 같은 태그" log_ordered '^build_release\.sh v1\.2\.3$' 'deploy\.sh dev v1\.2\.3$'
new_case; export FAKE_DEPLOY_RC=7
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$APPHOME/.env"
capture run_setup --profile dev --server
eq "deploy.sh 종료 코드를 그대로 반환" "7" "$RC"

echo "T32 dev --server .env 점검 실패(AC16·AC17)"
new_case
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:SECRETMARK@h/db\n' > "$APPHOME/.env"
capture run_setup --profile dev --server
eq "종료 3" "3" "$RC"
check "bootstrap은 점검 전에 실행됨" log_has 'bootstrap\.sh dev'
check "pnpm build 없음" log_none 'pnpm build'
check "build_release 없음" log_none 'build_release'
check "deploy 없음" log_none 'deploy\.sh'
has_text "빠진 변수 이름 안내" "$OUT$ERR" "APP_JWT_SECRET"
lacks_text "값 비출력" "$OUT$ERR" "SECRETMARK"

echo "T36 product는 준비까지만(사용자 결정 Q1)"
new_case
printf 'APP_PROFILE=product\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\nAPP_SENTRY_DSN=https://x@s.example/1\n' > "$APPHOME/.env"
capture run_setup --profile product
eq "종료 0" "0" "$RC"
check "bootstrap product 실행 후 .env 점검" log_ordered 'bootstrap\.sh product$' 'sudo .*grep .*\.env'
check "빌드·번들 없음" log_none 'pnpm|build_release'
check "deploy.sh 호출 없음" log_none 'deploy\.sh'
check "incoming 복사 없음" log_none 'incoming'
check "마이그레이션 없음" log_none 'alembic'
check "nginx 설치·enable 없음" log_none 'nginx'
has_text "배포는 Jenkins 안내" "$OUT$ERR" "Jenkins"
new_case
printf 'APP_PROFILE=product\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_JWT_SECRET=a\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$APPHOME/.env"
capture run_setup --profile product --server
eq "SENTRY 없음: 종료 3" "3" "$RC"
check "deploy 없음" log_none 'deploy\.sh'

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

echo "R3 서버 .env 점검: 빠진 변수 목록이 안내 문구보다 먼저(리뷰 Minor)"
new_case
printf 'APP_PROFILE=dev\nAPP_DATABASE_URL=postgresql://u:p@h/db\nAPP_SETTINGS_ENCRYPTION_KEY=b\n' > "$APPHOME/.env"
ALL="$(run_setup --profile dev --server 2>&1)"; RC=$?
eq "종료 3" "3" "$RC"
printf '%s\n' "$ALL" > "$TMP/all.out"
NAME_LINE="$(grep -n -m1 'APP_JWT_SECRET' "$TMP/all.out" | cut -d: -f1)"
HELP_LINE="$(grep -n -m1 'sudo -u neoine -H' "$TMP/all.out" | cut -d: -f1)"
check "변수 이름 줄($NAME_LINE)이 편집 안내 줄($HELP_LINE)보다 앞" test -n "$NAME_LINE" -a -n "$HELP_LINE" -a "${NAME_LINE:-999}" -lt "${HELP_LINE:-0}"

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

echo "T35 Jenkins 등록(AC24)"
for pat in 'scripts/setup\.sh' 'infra/server/lib/env_secrets\.sh' 'scripts/tests/test_setup\.sh' 'infra/server/tests/test_env_secrets\.sh'; do
  check "Jenkinsfile에 $pat" grep -Eq "$pat" "$ROOT/Jenkinsfile"
done

echo "R4 임시 디렉터리 정리(리뷰 Nit)"
EXIT_TRAP="$(trap -p EXIT)"
case "$EXIT_TRAP" in *rm*"$"WORK*) ok "EXIT trap이 임시 작업 디렉터리를 지움" ;; *) fail "EXIT trap이 임시 작업 디렉터리를 지움 ('$EXIT_TRAP')" ;; esac
check "케이스 디렉터리는 작업 디렉터리 아래" test "${TMP#"$WORK"/}" != "$TMP"

echo
echo "$CASES 케이스, 실패 $FAILURES"
[ "$FAILURES" -eq 0 ]
