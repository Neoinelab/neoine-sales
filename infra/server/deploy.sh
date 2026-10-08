#!/usr/bin/env bash
# infra/server/deploy.sh <dev|product> <release_tag>
# Jenkins가 서버로 전달해 실행한다(계정: neoine). 배포 = 번들 풀기 -> 설정 검증 -> 마이그레이션 -> 전환 -> 헬스체크(실패 시 롤백).
# 같은 태그로 다시 실행해도 안전하다(멱등). 테스트를 위해 APP_HOME 등은 환경변수로 바꿀 수 있다.
set -euo pipefail

die() { echo "[deploy] $*" >&2; exit "${2:-2}"; }

ENV_NAME="${1:-}"
TAG="${2:-}"
case "$ENV_NAME" in dev | product) ;; *) die "사용법: deploy.sh <dev|product> <release_tag>" ;; esac
# 태그는 경로와 명령에 쓰이므로 안전한 문자만 허용한다
[[ "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "허용되지 않는 릴리스 태그: $TAG"

APP_HOME="${APP_HOME:-/opt/neoine-sales}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/readyz}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-3}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
SERVICE="neoine-sales-api"
RELEASE="$APP_HOME/releases/$TAG"

cd "$APP_HOME"
export PATH="$HOME/.local/bin:$PATH" # uv 위치(비대화형 SSH 세션용)

# .env의 APP_PROFILE이 대상 환경과 같은지 확인(dev 설정이 product 서버에 올라가는 사고 방지)
[ -f .env ] || die ".env가 없습니다. bootstrap.sh 실행 후 필수 변수를 입력하세요"
grep -qx "APP_PROFILE=$ENV_NAME" .env || die "APP_PROFILE이 $ENV_NAME 과 다릅니다"
[ -f "incoming/neoine-sales-$TAG.tar.gz" ] || die "번들이 없습니다: incoming/neoine-sales-$TAG.tar.gz"

PREV="$(readlink -f current 2>/dev/null || true)"

# 1) 번들 풀기 + 의존성 설치(잠금 파일 기준, 개발 의존성 제외) + 설정 사전 검증
#    .ready 표시가 있는 릴리스는 이미 준비된 것이므로 다시 만들지 않는다(실행 중인 릴리스를 지우지 않기 위해)
if [ ! -f "$RELEASE/.ready" ]; then
  rm -rf "$RELEASE"
  mkdir -p "$RELEASE"
  tar -xzf "incoming/neoine-sales-$TAG.tar.gz" -C "$RELEASE" --strip-components=1
  (cd "$RELEASE/backend" && uv sync --locked --no-dev --no-editable)
  # 필수 변수 누락·형식 오류·product 안전 조건 위반이면 여기서 중단(전환 전). cwd=$APP_HOME여야 .env를 읽는다
  "$RELEASE/backend/.venv/bin/python" -c "from app.config import get_settings; get_settings()" ||
    die "설정 검증 실패: $APP_HOME/.env 를 확인하세요(비밀 값은 출력하지 않습니다)" 3
  touch "$RELEASE/.ready"
fi

# 1-1) 프런트 런타임 설정 설치(비밀 없음)
install -m 644 "$RELEASE/infra/server/config/config.$ENV_NAME.json" shared/config.json

# 2) DB 마이그레이션(하위 호환 변경만: expand -> migrate -> contract). 실패하면 set -e로 여기서 중단(전환 전)
"$RELEASE/backend/.venv/bin/alembic" -c "$RELEASE/backend/alembic.ini" upgrade head

# 3) 전환 + 재시작(심볼릭 링크 교체는 원자적)
switch_to() { ln -sfn "$1" current.new && mv -T current.new current 2>/dev/null || mv -fh current.new current; }
switch_to "$RELEASE"
sudo systemctl restart "$SERVICE"

# 4) 오래된 릴리스 정리(최근 KEEP_RELEASES개 + 현재 + 직전 릴리스는 보관)
prune_releases() {
  local count=0 dir
  for dir in $(ls -1dt releases/*/ 2>/dev/null); do
    dir="${dir%/}"
    count=$((count + 1))
    [ "$count" -le "$KEEP_RELEASES" ] && continue
    [ "$(readlink -f "$dir")" = "$(readlink -f current)" ] && continue
    [ -n "$PREV" ] && [ "$(readlink -f "$dir")" = "$PREV" ] && continue
    rm -rf "$dir"
  done
  find incoming -name 'neoine-sales-*.tar.gz' -mtime +14 -delete
}

# 5) 헬스체크, 실패 시 롤백(코드만 되돌린다. 그래서 마이그레이션은 하위 호환이어야 한다)
for _ in $(seq 1 "$HEALTH_RETRIES"); do
  if curl -fsS --max-time 3 "$HEALTH_URL" > /dev/null; then
    echo "[deploy] 배포 성공: $ENV_NAME $TAG"
    prune_releases
    exit 0
  fi
  sleep "$HEALTH_INTERVAL"
done

echo "[deploy] 헬스체크 실패 - 롤백: ${PREV:-없음}" >&2
if [ -n "$PREV" ]; then
  switch_to "$PREV"
  sudo systemctl restart "$SERVICE"
fi
exit 1
