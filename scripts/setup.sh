#!/usr/bin/env bash
# 설치 스크립트(macOS·리눅스 공용). 여러 번 실행해도 안전하다(이미 있는 도구는 건너뜀).
#
# 사용: scripts/setup.sh [--profile local|dev|product] [--server] [--skip-migrate] [--tag <릴리스>] [-h|--help]
#   (인자 없음)            개발 PC 모드, profile local: 기본 도구, uv, Node.js, 의존성, backend/.env, 마이그레이션
#   --profile dev          개발 PC 모드, backend/.env.dev 사용
#   --profile dev --server dev 서버(리눅스+systemd): bootstrap.sh, 서버 .env 점검, 빌드·번들·deploy.sh
#   --profile product      product 서버 준비까지만: bootstrap.sh와 서버 .env 점검(배포는 Jenkins Deploy: Product)
#   --skip-migrate         개발 PC 모드에서 DB 스키마 적용을 건너뜀
#   --tag <릴리스>         dev --server의 릴리스 태그(기본: git 커밋 12자리)
# 종료 코드: 0 성공, 1 실행 중 실패, 2 잘못된 인자·지원하지 않는 환경, 3 사람이 값을 넣어야 함
# 일반 사용자로 실행한다(필요한 단계에서만 sudo). PostgreSQL 설치·DB 생성, TLS, 방화벽은 범위 밖이다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_VERSION="0.10.4" # uv.lock을 만든 uv와 같은 버전(infra/server/bootstrap.sh와 일치)
NODE_LINE="latest-v24.x"
NODE_MIN_MAJOR=22 # 이보다 낮으면 새로 설치(Vite 8 요구 사항)
LOCAL_BIN="$HOME/.local/bin"

# shellcheck source=../infra/server/lib/env_secrets.sh
source "$ROOT/infra/server/lib/env_secrets.sh"

PROFILE="local"
SERVER="false"
SKIP_MIGRATE="false"
TAG=""

step() { printf '\n==> %s\n' "$1"; }
has() { command -v "$1" >/dev/null 2>&1; }
usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die_usage() { echo "오류: $1" >&2; echo "도움말: scripts/setup.sh --help" >&2; exit 2; }
die_fail() { echo "오류: $1" >&2; exit 1; }

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --profile)
        [ $# -ge 2 ] || die_usage "--profile 값이 없습니다"
        case "$2" in local | dev | product) PROFILE="$2" ;; *) die_usage "알 수 없는 프로파일: $2" ;; esac
        shift 2 ;;
      --server) SERVER="true"; shift ;;
      --skip-migrate) SKIP_MIGRATE="true"; shift ;;
      --tag)
        [ $# -ge 2 ] || die_usage "--tag 값이 없습니다"
        TAG="$2"; shift 2 ;;
      -h | --help) usage; exit 0 ;;
      *) die_usage "알 수 없는 옵션: $1" ;;
    esac
  done
  if [ "$PROFILE" = "local" ] && [ "$SERVER" = "true" ]; then
    die_usage "--profile local은 --server와 함께 쓸 수 없습니다"
  fi
  local mode
  mode="$(resolve_mode)"
  if [ "$mode" = "server" ] && [ "$SKIP_MIGRATE" = "true" ]; then
    die_usage "서버 모드에서는 --skip-migrate를 쓸 수 없습니다(deploy.sh는 항상 마이그레이션합니다)"
  fi
  if [ -n "$TAG" ]; then
    [ "$mode" = "server" ] || die_usage "--tag는 서버 모드에서만 쓸 수 있습니다"
    printf '%s' "$TAG" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$' || die_usage "허용되지 않는 릴리스 태그: $TAG"
  fi
  return 0
}

# pc 또는 server
resolve_mode() {
  if [ "$SERVER" = "true" ] || [ "$PROFILE" = "product" ]; then echo server; else echo pc; fi
}

detect_os() {
  case "$(uname -s)" in
    Darwin) echo darwin ;;
    Linux) echo linux ;;
    *) return 2 ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64 | amd64) echo x64 ;;
    arm64 | aarch64) echo arm64 ;;
    *) return 2 ;;
  esac
}

is_musl() {
  [ -f /etc/alpine-release ] && return 0
  local out
  out="$(ldd --version 2>&1 || true)" # musl ldd는 종료 1이므로 출력만 보고 판정한다
  case "$out" in *[Mm][Uu][Ss][Ll]*) return 0 ;; esac
  return 1
}

detect_pkg_manager() {
  local pm
  if [ "$1" = "darwin" ]; then
    if has brew; then echo brew; else echo none; fi
    return 0
  fi
  for pm in apt-get dnf yum zypper pacman; do
    if has "$pm"; then echo "$pm"; return 0; fi
  done
  echo none
}

pkg_install() {
  local pm="$1"; shift
  case "$pm" in
    apt-get) sudo apt-get update && sudo apt-get install -y "$@" ;;
    dnf | yum) sudo "$pm" install -y "$@" ;;
    zypper) sudo zypper --non-interactive install "$@" ;;
    pacman) sudo pacman -S --needed --noconfirm "$@" ;;
    brew) brew install "$@" ;;
    *) return 1 ;;
  esac
}

# 필수 도구(curl, tar, gzip, git)가 없을 때만 패키지 관리자로 설치한다
ensure_base_tools() {
  local os="$1" t missing="" pm
  # git이 실제로 동작하면 CLT 유무와 상관없이 진행하고, CLT 스텁뿐일 때만 중단한다
  if [ "$os" = "darwin" ] && ! git --version >/dev/null 2>&1 && ! xcode-select -p >/dev/null 2>&1; then
    echo "오류: Xcode Command Line Tools가 없습니다. 'xcode-select --install'을 실행해 설치한 뒤 다시 실행하세요." >&2
    return 1
  fi
  for t in curl tar gzip git; do has "$t" || missing="$missing $t"; done
  if [ -z "$missing" ]; then echo "필수 도구가 이미 있음"; return 0; fi
  pm="$(detect_pkg_manager "$os")"
  if [ "$pm" = "none" ]; then
    echo "오류: 패키지 관리자를 찾지 못했습니다. 다음 도구를 직접 설치하세요:$missing" >&2
    return 1
  fi
  # shellcheck disable=SC2086
  pkg_install "$pm" $missing
}

# Node 공식 SHASUMS256.txt에서 <os>-<arch> tar.gz 파일명 한 줄을 출력한다. 없으면 1
node_tarball_name() {
  local name
  name="$(awk '{print $2}' "$1" | grep -E "^node-v24\\.[0-9]+\\.[0-9]+-${2}-${3}\\.tar\\.gz\$" | head -1)"
  [ -n "$name" ] || return 1
  echo "$name"
}

sha256_of() {
  if has sha256sum; then
    sha256sum "$1" | cut -d' ' -f1
  elif has shasum; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    return 1
  fi
}

node_major() {
  local v
  if ! has node; then echo 0; return 0; fi
  v="$(node --version 2>/dev/null)" || { echo 0; return 0; }
  v="${v#v}"
  echo "${v%%.*}"
}

# Node.js 공식 tarball을 sha256 검증 후 ~/.local/lib/nodejs에 풀고 ~/.local/bin에 링크한다(sudo 없음)
install_node() {
  local os="$1" arch="$2" tmp name expected actual dir base t
  base="https://nodejs.org/dist/${NODE_LINE}"
  tmp="$(mktemp -d)" || return 1
  if ! curl -fsSL "$base/SHASUMS256.txt" -o "$tmp/SHASUMS256.txt"; then rm -rf "$tmp"; return 1; fi
  if ! name="$(node_tarball_name "$tmp/SHASUMS256.txt" "$os" "$arch")"; then
    echo "오류: ${os}-${arch}용 Node.js 배포본을 찾지 못했습니다" >&2; rm -rf "$tmp"; return 1
  fi
  if ! curl -fsSL "$base/$name" -o "$tmp/$name"; then rm -rf "$tmp"; return 1; fi
  expected="$(grep " ${name}\$" "$tmp/SHASUMS256.txt" | head -1 | awk '{print $1}')"
  actual="$(sha256_of "$tmp/$name")" || { echo "오류: sha256sum 또는 shasum이 필요합니다" >&2; rm -rf "$tmp"; return 1; }
  if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
    echo "오류: Node.js 내려받은 파일의 sha256이 맞지 않아 설치하지 않습니다" >&2; rm -rf "$tmp"; return 1
  fi
  dir="${name%.tar.gz}"
  mkdir -p "$HOME/.local/lib/nodejs" "$LOCAL_BIN" || { rm -rf "$tmp"; return 1; }
  rm -rf "${HOME:?}/.local/lib/nodejs/$dir"
  tar -xzf "$tmp/$name" -C "$HOME/.local/lib/nodejs" || { rm -rf "$tmp"; return 1; }
  for t in node npm npx corepack; do
    ln -sf "$HOME/.local/lib/nodejs/$dir/bin/$t" "$LOCAL_BIN/$t"
  done
  rm -rf "$tmp"
  export PATH="$LOCAL_BIN:$PATH"
}

ensure_node() {
  local major
  major="$(node_major)"
  if [ "$major" -ge "$NODE_MIN_MAJOR" ]; then
    echo "Node.js가 이미 있음: $(node --version)"
  else
    echo "Node.js ${NODE_LINE}를 공식 배포본으로 ~/.local에 설치합니다(sudo 없음)."
    install_node "$1" "$2" || return 1
  fi
  if ! has corepack; then
    # Node 25부터 corepack이 빠졌다. 전역(/usr) 대신 사용자 경로에 설치한다
    npm install --global --prefix "$HOME/.local" corepack || return 1
  fi
  export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
}

ensure_uv() {
  if has uv; then echo "uv가 이미 있음: $(uv --version)"; return 0; fi
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_NO_MODIFY_PATH=1 sh || return 1
}

env_file_for() {
  case "$1" in dev) echo ".env.dev" ;; *) echo ".env" ;; esac
}

# 개발 PC용 env 파일 준비. 0 준비됨, 3 사람 입력 필요(APP_DATABASE_URL)
prepare_pc_env() {
  local backend="$1" profile="$2" file example name cur ex
  file="$backend/$(env_file_for "$profile")"
  example="$backend/.env.example"
  if [ ! -f "$file" ]; then
    install -m 600 "$example" "$file" || return 1
    ENV_NEW_VALUE="$profile" env_replace_value "$file" APP_PROFILE || return 1
    ENV_NEW_VALUE="$(gen_jwt_secret)" env_replace_value "$file" APP_JWT_SECRET || return 1
    ENV_NEW_VALUE="$(gen_fernet_key)" env_replace_value "$file" APP_SETTINGS_ENCRYPTION_KEY || return 1
    echo "$file 을(를) 만들었습니다(비밀은 새로 생성, 값은 출력하지 않음)."
  else
    env_ensure_line "$file" APP_JWT_SECRET gen_jwt_secret && echo "APP_JWT_SECRET 줄이 없어 새로 만들었습니다(값은 출력하지 않음)."
    env_ensure_line "$file" APP_SETTINGS_ENCRYPTION_KEY gen_fernet_key && echo "APP_SETTINGS_ENCRYPTION_KEY 줄이 없어 새로 만들었습니다(값은 출력하지 않음)."
    for name in APP_JWT_SECRET APP_SETTINGS_ENCRYPTION_KEY; do
      cur="$(grep "^${name}=" "$file" | head -1)"
      ex="$(grep "^${name}=" "$example" | head -1)"
      if [ -n "$ex" ] && [ "$cur" = "$ex" ]; then
        echo "경고: $file 의 $name 이(가) 공개된 예시 값 그대로입니다. 바꾸면 이미 저장한 값을 풀 수 없을 수 있어 그대로 둡니다. 필요하면 직접 교체하세요." >&2
      fi
    done
  fi
  if ! grep -q '^APP_DATABASE_URL=' "$file" || grep -q '^APP_DATABASE_URL=.*CHANGE_ME' "$file"; then
    echo "$file 의 APP_DATABASE_URL을 채워야 합니다(CHANGE_ME를 DB 비밀번호로 교체)." >&2
    echo "비밀번호의 특수문자는 URL 인코딩하세요(! -> %21, @ -> %40). 채운 뒤 scripts/setup.sh를 다시 실행하세요." >&2
    return 3
  fi
  return 0
}

check_server_supported() {
  local os why=""
  os="$(detect_os)" || os="unknown"
  if [ "$os" != "linux" ]; then why="서버 모드는 리눅스 전용입니다(현재: $os)"
  elif is_musl; then why="지원하지 않는 배포판입니다(musl, 예: Alpine)"
  elif ! has systemctl; then why="systemctl이 없습니다(systemd 필요)"
  elif [ ! -d "${SETUP_SYSTEMD_RUN_DIR:-/run/systemd/system}" ]; then why="systemd가 실행 중이 아닙니다"
  elif ! has sudo; then why="sudo가 없습니다"
  fi
  if [ -n "$why" ]; then
    echo "오류: $why. 개발 PC에서는 --profile local 또는 --profile dev(--server 없이)를 쓰세요." >&2
    return 2
  fi
  return 0
}

# 서버 .env 필수값 점검. stdout에는 빠진 변수 이름만, 안내는 stderr. 0 통과, 3 누락
check_server_env() {
  local file="$1" env="$2" s="${SETUP_SUDO:-sudo}" missing=0
  _report() { echo "$1"; missing=1; }
  $s grep -qx "APP_PROFILE=${env}" "$file" || _report APP_PROFILE
  if ! $s grep -q '^APP_DATABASE_URL=.' "$file" || $s grep -q '^APP_DATABASE_URL=.*CHANGE_ME' "$file"; then
    _report APP_DATABASE_URL
  fi
  $s grep -q '^APP_JWT_SECRET=.' "$file" || _report APP_JWT_SECRET
  $s grep -q '^APP_SETTINGS_ENCRYPTION_KEY=.' "$file" || _report APP_SETTINGS_ENCRYPTION_KEY
  if [ "$env" = "product" ]; then
    $s grep -q '^APP_SENTRY_DSN=.' "$file" || _report APP_SENTRY_DSN
  fi
  if [ "$env" = "dev" ] && ! $s grep -qx 'APP_DEV_LOGIN_ENABLED=false' "$file"; then
    echo "안내: 공유 서버라면 $file 에 APP_DEV_LOGIN_ENABLED=false 를 넣어 개발용 로그인을 끄세요." >&2
  fi
  [ "$missing" -eq 0 ] || return 3
  return 0
}

# dev 서버 모드의 기본 릴리스 태그
default_tag() {
  local stamp hash
  stamp="$(date +%Y%m%d%H%M%S)"
  if ! (cd "$ROOT" && git rev-parse --is-inside-work-tree >/dev/null 2>&1); then
    echo "local-$stamp"; return 0
  fi
  hash="$(cd "$ROOT" && git rev-parse --short=12 HEAD)"
  if [ -n "$(cd "$ROOT" && git status --porcelain 2>/dev/null)" ]; then
    echo "${hash}-dirty-${stamp}"
  else
    echo "$hash"
  fi
}

path_hint() {
  case ":${ORIGINAL_PATH}:" in
    *":${LOCAL_BIN}:"*) return 0 ;;
  esac
  local rc="~/.bashrc"
  case "${SHELL:-}" in */zsh) rc="~/.zprofile" ;; esac
  echo
  echo "새 터미널에서 uv·node를 쓰려면 ${rc} 에 다음 줄을 추가하세요:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
}

corepack_ready() {
  # corepack 서명 오류(Cannot find matching keyid)가 나는 환경이면 검증 키 확인을 끈다
  local out
  if out="$(cd "$ROOT/frontend" && corepack pnpm --version 2>&1)"; then return 0; fi
  case "$out" in
    *keyid* | *[Ss]ignature*)
      export COREPACK_INTEGRITY_KEYS=0
      echo "corepack 서명 검증 오류가 있어 COREPACK_INTEGRITY_KEYS=0 으로 검증 키 확인을 끕니다." ;;
    *) echo "오류: corepack pnpm 실행에 실패했습니다(서명 오류 아님): $out" >&2; return 1 ;;
  esac
}

run_pc() {
  local os="$1" arch="$2" env_file rc
  step "기본 도구 확인 (curl, tar, gzip, git)"
  ensure_base_tools "$os" || exit 1
  step "uv 확인"
  ensure_uv || die_fail "uv 설치에 실패했습니다"
  step "Node.js 확인 (${NODE_MIN_MAJOR} 이상)"
  ensure_node "$os" "$arch" || die_fail "Node.js 설치에 실패했습니다"
  corepack_ready || exit 1
  step "backend: Python과 의존성 설치 (uv sync)"
  (cd "$ROOT/backend" && uv sync --locked) || die_fail "uv sync 실패"
  step "frontend: 의존성 설치 (pnpm install)"
  (cd "$ROOT/frontend" && corepack pnpm install --frozen-lockfile) || die_fail "pnpm install 실패"
  step "backend env 파일 준비"
  prepare_pc_env "$ROOT/backend" "$PROFILE"; rc=$?
  if [ "$rc" -ne 0 ]; then path_hint; exit "$rc"; fi
  env_file="$ROOT/backend/$(env_file_for "$PROFILE")"
  if [ "$SKIP_MIGRATE" = "true" ]; then
    echo; echo "DB 스키마 적용을 건너뛰었습니다(--skip-migrate)."
  else
    step "DB 스키마 적용 (alembic upgrade head, profile=$PROFILE)"
    (cd "$ROOT/backend" && APP_PROFILE="$PROFILE" APP_ENV_FILE="$env_file" uv run alembic upgrade head) || die_fail "마이그레이션 실패"
  fi
  echo
  if [ "$PROFILE" = "dev" ]; then
    echo "완료. 실행: ./scripts/start-backend.sh --profile dev 와 ./scripts/start-frontend.sh"
  else
    echo "완료. 실행: ./scripts/start-backend.sh 와 ./scripts/start-frontend.sh"
  fi
  path_hint
}

run_server() {
  local os="$1" arch="$2" app_home="${SETUP_APP_HOME:-/opt/neoine-sales}" tag rc missing bundle
  check_server_supported || exit 2
  step "기본 도구 확인 (curl, tar, gzip, git)"
  ensure_base_tools "$os" || exit 1
  step "서버 준비 (bootstrap.sh $PROFILE)"
  sudo bash "$ROOT/infra/server/bootstrap.sh" "$PROFILE" || die_fail "bootstrap.sh 실패"
  step "서버 .env 점검"
  missing="$(check_server_env "$app_home/.env" "$PROFILE")"; rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "누락되었거나 잘못된 변수(이름만 표시):"
    echo "$missing" | sed 's/^/  - /'
    echo "위 변수를 채워야 합니다: sudo -u neoine -H ${EDITOR:-vi} $app_home/.env" >&2
    echo "참고: backend/.env.example, docs/dev-guide.html 16장" >&2
    exit "$rc"
  fi
  if [ "$PROFILE" = "product" ]; then
    echo
    echo "product 서버 준비를 마쳤습니다. 빌드·배포·마이그레이션은 하지 않았습니다."
    echo "배포는 Jenkins 'Deploy: Product'에서 사람이 승인해 실행하세요."
    return 0
  fi
  step "Node.js·pnpm 확인과 프런트엔드 빌드"
  ensure_node "$os" "$arch" || die_fail "Node.js 설치에 실패했습니다"
  corepack_ready || exit 1
  (cd "$ROOT/frontend" && corepack pnpm install --frozen-lockfile) || die_fail "pnpm install 실패"
  (cd "$ROOT/frontend" && corepack pnpm build) || die_fail "pnpm build 실패"
  tag="$TAG"
  [ -n "$tag" ] || tag="$(default_tag)"
  step "릴리스 번들 생성 ($tag)"
  bash "$ROOT/infra/build_release.sh" "$tag" || die_fail "번들 생성 실패"
  bundle="$ROOT/build/neoine-sales-$tag.tar.gz"
  step "incoming 설치와 배포 (deploy.sh $PROFILE $tag)"
  sudo install -o neoine -g neoine -m 640 "$bundle" "$app_home/incoming/neoine-sales-$tag.tar.gz" || die_fail "번들 복사 실패"
  sudo install -o neoine -g neoine -m 640 "$ROOT/infra/server/deploy.sh" "$app_home/incoming/deploy.sh" || die_fail "deploy.sh 복사 실패"
  sudo -u neoine -H bash "$app_home/incoming/deploy.sh" "$PROFILE" "$tag"
  return $?
}

main() {
  local os arch
  parse_args "$@"
  if [ "$(id -u)" -eq 0 ]; then
    die_usage "root가 아닌 일반 사용자로 실행하세요(필요한 단계에서만 sudo를 씁니다)"
  fi
  os="$(detect_os)" || die_usage "지원하지 않는 OS입니다(macOS와 리눅스만 지원)"
  arch="$(detect_arch)" || die_usage "지원하지 않는 아키텍처입니다(x86_64, arm64만 지원)"
  if [ "$os" = "linux" ] && is_musl; then
    die_usage "지원하지 않는 배포판입니다(musl, 예: Alpine). glibc 기반 배포판을 쓰세요"
  fi
  ORIGINAL_PATH="$PATH"
  export PATH="${LOCAL_BIN}:${PATH}"
  if [ "$(resolve_mode)" = "server" ]; then
    run_server "$os" "$arch"
  else
    run_pc "$os" "$arch"
  fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
  exit $?
fi
