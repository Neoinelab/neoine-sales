#!/usr/bin/env bash
# 우분투 개발 환경 최초 구성(profile: local). 여러 번 실행해도 안전하다(이미 있는 도구는 건너뜀).
#   1) OS 패키지: curl, ca-certificates, git (없을 때만 sudo apt-get으로 설치)
#   2) uv(버전 고정)를 ~/.local/bin에 설치. Python 3.14는 uv가 받아 온다
#   3) Node.js가 없거나 22 미만이면 NodeSource 저장소로 Node.js 24 설치(sudo)
#   4) corepack이 없으면(Node 25부터 미포함) npm으로 ~/.local에 설치. pnpm은 corepack이 받아 온다
#   5) backend 의존성(uv sync), frontend 의존성(pnpm install)
#   6) backend/.env가 없으면 .env.example을 복사하고, DB 비밀번호를 넣으라고 안내한 뒤 멈춘다
#   7) DB 스키마 적용(alembic upgrade head)
# 사용: ./scripts/setup-ubuntu.sh [--skip-migrate]   (일반 사용자로 실행, 필요할 때만 sudo를 묻는다)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_VERSION="0.10.4" # uv.lock을 만든 uv와 같은 버전(infra/server/bootstrap.sh와 일치)
NODE_MAJOR=24       # 설치할 Node.js LTS 주 버전
NODE_MIN_MAJOR=22   # 이보다 낮으면 새로 설치(Vite 8 요구 사항)
LOCAL_BIN="$HOME/.local/bin"

SKIP_MIGRATE=false
for arg in "$@"; do
  case "$arg" in
    --skip-migrate) SKIP_MIGRATE=true ;;
    -h | --help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: ${arg}" >&2; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
has() { command -v "$1" >/dev/null 2>&1; }

if [[ "$(id -u)" -eq 0 ]]; then
  echo "오류: root가 아닌 일반 사용자로 실행하세요(필요한 단계에서만 sudo를 씁니다)." >&2
  exit 2
fi
if [[ -r /etc/os-release ]] && ! grep -qiE '^(ID|ID_LIKE)=.*(ubuntu|debian)' /etc/os-release; then
  echo "경고: 우분투(데비안 계열)가 아닌 것 같습니다. apt 단계가 실패할 수 있습니다." >&2
fi
has apt-get || { echo "오류: apt-get이 없습니다. 우분투용 스크립트입니다." >&2; exit 1; }

# 이번 실행에서 설치한 도구를 바로 쓰도록 PATH에 넣는다(새 셸에는 아래 마지막 안내 참고)
ORIGINAL_PATH="$PATH"
export PATH="${LOCAL_BIN}:${PATH}"

# 이 스크립트가 앞에 붙인 ~/.local/bin을 빼고도 PATH에 있는지 확인해, 없으면 셸 설정을 안내한다
path_hint() {
  case ":${ORIGINAL_PATH}:" in
    *":${LOCAL_BIN}:"*) ;;
    *)
      echo
      echo "새 터미널에서 uv·corepack을 쓰려면 ~/.bashrc에 다음 줄을 추가하세요:"
      echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
}

step "OS 패키지 확인 (curl, ca-certificates, git)"
missing=()
for pkg in curl ca-certificates git; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]})); then
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
else
  echo "이미 설치됨"
fi

step "uv 확인"
if has uv; then
  echo "이미 설치됨: $(uv --version)"
else
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_NO_MODIFY_PATH=1 sh
  echo "설치됨: $(uv --version)"
fi

step "Node.js 확인 (${NODE_MIN_MAJOR} 이상)"
node_major=0
if has node; then
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
fi
if ((node_major >= NODE_MIN_MAJOR)); then
  echo "이미 설치됨: node $(node --version)"
else
  echo "Node.js ${NODE_MAJOR}을 NodeSource 저장소로 설치합니다(sudo)."
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
  sudo apt-get install -y nodejs
  echo "설치됨: node $(node --version)"
fi

step "corepack 확인"
if has corepack; then
  echo "이미 설치됨: corepack $(corepack --version)"
else
  # 전역(/usr) 대신 사용자 경로(~/.local)에 설치해 sudo 없이 쓴다
  npm install --global --prefix "$HOME/.local" corepack
  echo "설치됨: corepack $(corepack --version)"
fi
# 처음 pnpm을 받을 때 묻는 확인 창을 끈다(버전은 package.json의 packageManager로 고정)
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0

step "backend: Python과 의존성 설치 (uv sync)"
(cd "$ROOT/backend" && uv sync --locked)

step "frontend: 의존성 설치 (pnpm install)"
# corepack 서명 오류(Cannot find matching keyid)가 나는 환경이면 검증 키 확인을 끄고 다시 시도한다.
if ! (cd "$ROOT/frontend" && corepack pnpm --version >/dev/null 2>&1); then
  export COREPACK_INTEGRITY_KEYS=0
fi
(cd "$ROOT/frontend" && corepack pnpm install --frozen-lockfile)

ENV_FILE="$ROOT/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  step "backend/.env 만들기"
  install -m 600 "$ROOT/backend/.env.example" "$ENV_FILE"
  echo "backend/.env를 만들었습니다. APP_DATABASE_URL의 CHANGE_ME를 로컬 DB 비밀번호로 바꾼 뒤"
  echo "이 스크립트를 다시 실행하세요(특수문자는 URL 인코딩: ! -> %21, @ -> %40)."
  path_hint
  exit 0
fi

if [[ "$SKIP_MIGRATE" == true ]]; then
  echo
  echo "DB 스키마 적용을 건너뛰었습니다(--skip-migrate)."
else
  step "DB 스키마 적용 (alembic upgrade head)"
  (cd "$ROOT/backend" && uv run alembic upgrade head)
fi

echo
echo "완료. 실행: ./scripts/start-backend.sh 와 ./scripts/start-frontend.sh (백그라운드 실행, 로그는 logs/)"
path_hint
