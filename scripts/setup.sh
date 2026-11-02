#!/usr/bin/env bash
# 설치 스크립트(macOS·리눅스 공용). 여러 번 실행해도 안전하다(이미 있는 도구는 건너뜀).
#
# 사용: scripts/setup.sh [--profile local|dev|product] [--skip-migrate] [-h|--help]
#   (인자 없음)            개발 PC 모드, profile local: 기본 도구, uv, Node.js, 의존성, backend/.env, 마이그레이션
#   --profile dev          개발 PC 모드, backend/.env.dev 사용
#   --profile product      product 서버 준비까지만(리눅스, Docker Engine + Compose v2 필요): neoine 계정·디렉터리,
#                          서버 .env(비밀 생성)·deploy.env, 사람이 채울 값 점검. 배포는 Jenkins Deploy: Product
#   --skip-migrate         개발 PC 모드에서 DB 스키마 적용을 건너뜀
# 종료 코드: 0 성공, 1 실행 중 실패, 2 잘못된 인자·지원하지 않는 환경, 3 사람이 값을 넣어야 함
# 일반 사용자로 실행한다(필요한 단계에서만 sudo). PostgreSQL 설치, Docker 설치, TLS 인증서, 방화벽은 범위 밖이다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_VERSION="0.10.4" # uv.lock을 만든 uv와 같은 버전(backend/Dockerfile과 일치)
NODE_LINE="latest-v24.x"
NODE_MIN_MAJOR=22 # 이보다 낮으면 새로 설치(Vite 8 요구 사항)
LOCAL_BIN="$HOME/.local/bin"

# shellcheck source=../infra/server/lib/env_secrets.sh
source "$ROOT/infra/server/lib/env_secrets.sh"

PROFILE="local"
SKIP_MIGRATE="false"

step() { printf '\n==> %s\n' "$1"; }
has() { command -v "$1" >/dev/null 2>&1; }
usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die_usage() { echo "오류: $1" >&2; echo "도움말: scripts/setup.sh --help" >&2; exit 2; }
die_fail() { echo "오류: $1" >&2; exit 1; }

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --profile)
        [ $# -ge 2 ] || die_usage "--profile 값이 없습니다"
        case "$2" in local | dev | product) PROFILE="$2" ;; *) die_usage "알 수 없는 프로파일: $2" ;; esac
        shift 2 ;;
      --skip-migrate) SKIP_MIGRATE="true"; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die_usage "알 수 없는 옵션: $1" ;;
    esac
  done
  if [ "$PROFILE" = "product" ] && [ "$SKIP_MIGRATE" = "true" ]; then
    die_usage "product 모드는 마이그레이션을 하지 않으므로 --skip-migrate를 쓸 수 없습니다"
  fi
  return 0
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

# ---- product 서버 준비(Docker Compose 배포의 사전 준비. 배포·마이그레이션·이미지 pull은 하지 않는다) ----

gen_pg_user() { printf 'neoine'; }
gen_pg_db() { printf 'neoinesales'; }

# 값이 비었거나 CHANGE_ME이면 0(= 사람이 채워야 함). 값은 출력하지 않는다
env_value_unset() {
  local value
  value="$(grep "^${2}=" "$1" | head -1 | cut -d= -f2-)"
  [ -z "$value" ] || [ "$value" = "CHANGE_ME" ]
}

# 스테이징 파일을 neoine 소유로 설치한다: install_staged <파일> <대상> <모드>
install_staged() {
  sudo install -o neoine -g neoine -m "$3" "$1" "$2"
}

# 서버 .env를 스테이징 파일로 읽어 와 줄이 없는 것만 채운다. 0 준비됨, 3 사람이 맞춰야 함
# 비밀 값은 출력하지 않고 명령 인자에도 싣지 않는다(스테이징 파일은 현재 사용자만 읽는 0600 임시 디렉터리 안)
product_prepare_env() {
  local staged="$1" file="$2"
  if sudo test -f "$file"; then
    sudo cat "$file" > "$staged"
  else
    : > "$staged"
    echo "$file 을(를) 새로 만듭니다."
  fi
  if ! grep -q '^APP_PROFILE=' "$staged"; then
    printf 'APP_PROFILE=product\n' >> "$staged"
  fi
  env_ensure_line "$staged" APP_JWT_SECRET gen_jwt_secret && echo "APP_JWT_SECRET을 새로 만들었습니다(값은 출력하지 않음)."
  env_ensure_line "$staged" APP_SETTINGS_ENCRYPTION_KEY gen_fernet_key && echo "APP_SETTINGS_ENCRYPTION_KEY를 새로 만들었습니다(값은 출력하지 않음). DB 백업과 다른 곳에 따로 보관하세요."
  env_ensure_line "$staged" POSTGRES_USER gen_pg_user
  env_ensure_line "$staged" POSTGRES_DB gen_pg_db
  if grep -q '^APP_DATABASE_URL=' "$staged" && ! grep -q '^POSTGRES_PASSWORD=' "$staged"; then
    # 이미 DB 비밀번호가 들어간 URL이 있는데 새 비밀번호를 만들면 둘이 어긋나므로 사람이 맞추게 한다
    echo "오류: .env 에 POSTGRES_PASSWORD 가 없습니다. APP_DATABASE_URL 의 비밀번호와 같은 값으로 직접 넣으세요(새로 만들지 않았습니다)." >&2
    return 3
  fi
  env_ensure_line "$staged" POSTGRES_PASSWORD gen_db_password && echo "POSTGRES_PASSWORD를 새로 만들었습니다(값은 출력하지 않음)."
  env_ensure_database_url "$staged" && echo "APP_DATABASE_URL을 POSTGRES_* 값으로 조립했습니다(값은 출력하지 않음)."
  return 0
}

# deploy.env(비밀 없음)를 스테이징 파일로 준비한다. 있으면 APP_UID·APP_GID 줄만 보장한다
product_prepare_deploy_env() {
  local staged="$1" file="$2" app_home="$3" db_dir="$4" uid gid
  uid="$(id -u neoine)" && gid="$(id -g neoine)" || return 1
  if sudo test -f "$file"; then
    sudo cat "$file" > "$staged"
    if [ -n "$(tail -c 1 "$staged")" ]; then printf '\n' >> "$staged"; fi
    grep -q '^APP_UID=' "$staged" || printf 'APP_UID=%s\n' "$uid" >> "$staged"
    grep -q '^APP_GID=' "$staged" || printf 'APP_GID=%s\n' "$gid" >> "$staged"
    return 0
  fi
  {
    printf 'APP_HOME=%s\n' "$app_home"
    printf 'APP_PROFILE=product\n'
    printf 'APP_UID=%s\n' "$uid"
    printf 'APP_GID=%s\n' "$gid"
    printf 'API_WORKERS=4\n'
    printf 'CERT_DIR=%s/certs\n' "$app_home"
    printf 'DB_DATA_DIR=%s\n' "$db_dir"
    printf 'SERVER_NAME=CHANGE_ME\n'
    printf 'REGISTRY=CHANGE_ME\n'
  } > "$staged"
  echo "$file 을(를) 새로 만듭니다(SERVER_NAME·REGISTRY는 CHANGE_ME)."
}

# 사람이 채워야 하는 항목의 이름만 stdout에 출력한다(값은 출력하지 않음)
product_missing() {
  local env_staged="$1" deploy_staged="$2" app_home="$3" name
  grep -qx 'APP_PROFILE=product' "$env_staged" || echo APP_PROFILE
  for name in APP_DATABASE_URL APP_JWT_SECRET APP_SETTINGS_ENCRYPTION_KEY POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB APP_SENTRY_DSN; do
    ! env_value_unset "$env_staged" "$name" || echo "$name"
  done
  for name in SERVER_NAME REGISTRY; do
    ! env_value_unset "$deploy_staged" "$name" || echo "$name"
  done
  for name in fullchain.pem privkey.pem; do
    sudo test -f "$app_home/certs/$name" || echo "certs/$name"
  done
}

run_product() {
  local os="$1" app_home="${SETUP_APP_HOME:-/opt/neoine-sales}"
  local files_dir="${SETUP_FILES_DIR:-/var/lib/neoine-sales/files}"
  local db_dir="${SETUP_DB_DATA_DIR:-/var/lib/neoine-sales-postgres}"
  local staged_env staged_deploy missing rc registry

  if [ "$os" != "linux" ]; then
    die_usage "product 모드는 리눅스 전용입니다(현재: $os). 개발 PC에서는 --profile local 또는 dev를 쓰세요"
  fi
  has sudo || die_usage "sudo가 없습니다"
  step "Docker Engine과 Compose v2 확인"
  if ! has docker || ! docker compose version >/dev/null 2>&1; then
    echo "오류: docker 또는 docker compose(v2)를 쓸 수 없습니다. Docker Engine과 Compose 플러그인을 먼저 설치하세요(이 스크립트는 설치하지 않습니다)." >&2
    exit 2
  fi

  step "neoine 계정과 docker 그룹"
  if ! id -u neoine >/dev/null 2>&1; then
    sudo useradd --create-home --shell /bin/bash neoine || die_fail "neoine 계정을 만들지 못했습니다"
    echo "neoine 계정을 만들었습니다."
  fi
  sudo usermod -aG docker neoine || die_fail "neoine를 docker 그룹에 넣지 못했습니다(docker 그룹이 있는지 확인)"

  step "디렉터리"
  sudo install -d -o neoine -g neoine -m 750 "$app_home" "$app_home/incoming" "$app_home/deploys" "$app_home/certs" \
    || die_fail "디렉터리를 만들지 못했습니다: $app_home"
  sudo install -d -o neoine -g neoine -m 700 "$app_home/backups" || die_fail "backups 디렉터리를 만들지 못했습니다"
  sudo install -d -o neoine -g neoine -m 750 "$(dirname "$files_dir")" "$files_dir" || die_fail "첨부 저장 디렉터리를 만들지 못했습니다"
  # DB 데이터 디렉터리는 postgres 이미지가 초기화 때 내용의 소유자를 정한다
  sudo install -d -m 755 "$db_dir" || die_fail "DB 데이터 디렉터리를 만들지 못했습니다"

  PRODUCT_TMPDIR="$(mktemp -d)" || die_fail "임시 디렉터리를 만들지 못했습니다"
  trap 'rm -rf "$PRODUCT_TMPDIR"' EXIT
  chmod 700 "$PRODUCT_TMPDIR"
  staged_env="$PRODUCT_TMPDIR/env"; staged_deploy="$PRODUCT_TMPDIR/deploy.env"

  step "서버 .env (비밀은 없을 때만 생성, 값은 출력하지 않음)"
  product_prepare_env "$staged_env" "$app_home/.env"; rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "맞춘 뒤 다시 실행하세요: ${EDITOR:-vi} $app_home/.env (neoine 계정으로 편집)" >&2
    exit "$rc"
  fi
  install_staged "$staged_env" "$app_home/.env" 600 || die_fail ".env를 저장하지 못했습니다"

  step "deploy.env (compose 변수, 비밀 없음)"
  product_prepare_deploy_env "$staged_deploy" "$app_home/deploy.env" "$app_home" "$db_dir" || die_fail "deploy.env를 준비하지 못했습니다"
  install_staged "$staged_deploy" "$app_home/deploy.env" 640 || die_fail "deploy.env를 저장하지 못했습니다"

  step "사람이 채울 값 점검"
  missing="$(product_missing "$staged_env" "$staged_deploy" "$app_home")"
  registry="$(grep '^REGISTRY=' "$staged_deploy" | head -1 | cut -d= -f2-)"
  if [ -z "$registry" ] || [ "$registry" = "CHANGE_ME" ]; then registry="<REGISTRY>"; fi
  echo "레지스트리 로그인(읽기 전용 계정, 사람이 neoine 계정으로 한 번): sudo -u neoine -H docker login $registry"
  if [ -n "$missing" ]; then
    echo "채워야 하는 항목(이름만 표시):"
    echo "$missing" | sed 's/^/  - /'
    echo "값 위치: $app_home/.env, $app_home/deploy.env, 인증서는 $app_home/certs (neoine 계정으로 편집)" >&2
    echo "참고: backend/.env.example, docs/dev-guide.html 16장" >&2
    exit 3
  fi
  echo
  echo "product 서버 준비를 마쳤습니다. 이미지 pull·마이그레이션·배포는 하지 않았습니다."
  echo "배포는 Jenkins 'Deploy: Product'에서 사람이 승인해 실행하세요."
  return 0
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
  if [ "$PROFILE" = "product" ]; then
    run_product "$os"
  else
    run_pc "$os" "$arch"
  fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
  exit $?
fi
