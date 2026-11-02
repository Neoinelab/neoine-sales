#!/usr/bin/env bash
# infra/docker/deploy.sh product <이미지_태그> [--no-migrate]
# Jenkins가 서버로 전달해 실행한다(계정: neoine, docker 그룹. sudo 없음).
# 순서: 입력·환경 검증 -> 배포 키트 설치 -> pull -> 새 이미지로 설정 검증 -> db 기동 -> DB 덤프 -> migrate
#       -> 전환(up --wait) -> 헬스체크(실패 시 이전 태그로 자동 롤백, 마이그레이션은 다시 하지 않음).
# 같은 태그로 다시 실행해도 안전하다(멱등). --no-migrate는 덤프·migrate를 건너뛴다(사람이 이전 태그로 되돌릴 때).
# 종료 코드: 0 성공, 1 헬스체크 실패(롤백 시도 후 포함), 2 입력·환경·pull 실패, 3 설정 검증 실패,
#           4 DB 덤프 실패, 5 마이그레이션 실패
# 테스트용 환경변수: APP_HOME, HEALTH_URL, HEALTH_RETRIES, HEALTH_INTERVAL, KEEP_DEPLOYS, KEEP_BACKUPS, WAIT_TIMEOUT
set -uo pipefail

die() { echo "[deploy] $1" >&2; exit "${2:-2}"; }
log() { echo "[deploy] $1"; }

ENV_NAME="${1:-}"
TAG="${2:-}"
[ "$ENV_NAME" = "product" ] || die "사용법: deploy.sh product <이미지_태그> [--no-migrate]"
# 태그는 경로와 명령에 쓰이므로 안전한 문자만 허용한다
[[ "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "허용되지 않는 이미지 태그: $TAG"
shift 2
MIGRATE="true"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-migrate) MIGRATE="false"; shift ;;
    *) die "알 수 없는 옵션: $1" ;;
  esac
done

APP_HOME="${APP_HOME:-/opt/neoine-sales}"
HEALTH_URL="${HEALTH_URL:-https://127.0.0.1/readyz}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-3}"
KEEP_DEPLOYS="${KEEP_DEPLOYS:-5}"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-180}"
DEPLOY_DIR="$APP_HOME/deploys/$TAG"

# 1) 환경 확인: 모든 검사는 docker를 부르기 전에 끝낸다(아무것도 바꾸지 않고 실패)
[ -f "$APP_HOME/.env" ] || die ".env가 없습니다: $APP_HOME/.env (scripts/setup.sh --profile product 로 준비하세요)"
grep -qx 'APP_PROFILE=product' "$APP_HOME/.env" || die ".env의 APP_PROFILE이 product가 아닙니다"
[ -f "$APP_HOME/deploy.env" ] || die "deploy.env가 없습니다: $APP_HOME/deploy.env"
grep -qx 'APP_PROFILE=product' "$APP_HOME/deploy.env" || die "deploy.env의 APP_PROFILE이 product가 아닙니다"
REGISTRY_VALUE="$(grep '^REGISTRY=' "$APP_HOME/deploy.env" | head -1 | cut -d= -f2-)"
if [ -z "$REGISTRY_VALUE" ] || [ "$REGISTRY_VALUE" = "CHANGE_ME" ]; then
  die "deploy.env의 REGISTRY가 비어 있거나 CHANGE_ME 입니다"
fi

KIT="$APP_HOME/incoming/deploy-$TAG.tar.gz"
if [ ! -d "$DEPLOY_DIR" ] && [ ! -f "$KIT" ]; then
  die "배포 키트도 배포 디렉터리도 없습니다: $KIT"
fi

# docker compose 공통 호출. 앱 .env는 --env-file로 넘기지 않고(컨테이너가 /app/.env로 읽음),
# project directory를 배포 디렉터리로 둬서 compose가 APP_HOME의 .env를 치환용으로 읽지 않게 한다
dc() { # dc <태그> <compose 인자...>
  local tag="$1" dir
  shift
  dir="$APP_HOME/deploys/$tag"
  docker compose -p neoine-sales --project-directory "$dir" -f "$dir/compose.yaml" \
    --env-file "$APP_HOME/deploy.env" --env-file "$dir/image.env" "$@"
}

# 2) 배포 키트 설치(이미 있는 배포 디렉터리는 건드리지 않는다)
install_kit() {
  local tmp
  if [ -d "$DEPLOY_DIR" ]; then
    [ -f "$DEPLOY_DIR/image.env" ] || printf 'IMAGE_TAG=%s\n' "$TAG" > "$DEPLOY_DIR/image.env"
    return 0
  fi
  if tar -tzf "$KIT" 2>/dev/null | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
    die "배포 키트에 허용되지 않는 경로가 있습니다: $KIT"
  fi
  mkdir -p "$APP_HOME/deploys" || die "deploys 디렉터리를 만들지 못했습니다"
  tmp="$(mktemp -d "$APP_HOME/deploys/.tmp.XXXXXX")" || die "임시 디렉터리를 만들지 못했습니다"
  if ! tar -xzf "$KIT" -C "$tmp" || [ ! -f "$tmp/compose.yaml" ]; then
    rm -rf "$tmp"
    die "배포 키트를 풀지 못했거나 compose.yaml이 없습니다: $KIT"
  fi
  printf 'IMAGE_TAG=%s\n' "$TAG" > "$tmp/image.env"
  mv "$tmp" "$DEPLOY_DIR" || { rm -rf "$tmp"; die "배포 디렉터리를 만들지 못했습니다"; }
}
install_kit

PREV=""
if [ -L "$APP_HOME/current" ]; then
  PREV="$(readlink "$APP_HOME/current" 2>/dev/null || true)"
fi

# 심볼릭 링크 교체는 원자적이다(GNU mv -T, 없으면 BSD mv -h)
switch_to() { # switch_to <배포 디렉터리 절대 경로>
  ln -sfn "$1" "$APP_HOME/current.new" \
    && { mv -T "$APP_HOME/current.new" "$APP_HOME/current" 2>/dev/null || mv -fh "$APP_HOME/current.new" "$APP_HOME/current"; }
}

# 3) 새 이미지를 받는다. 실패하면 전환하지 않는다
log "이미지 pull: $TAG"
dc "$TAG" pull api web db || die "이미지 pull 실패(neoine 계정이 레지스트리에 docker login 되어 있는지 확인)" 2

# 4) 새 이미지로 설정 사전 검증(컨테이너가 /app/.env를 읽음). db는 띄우지 않는다
log "설정 검증"
dc "$TAG" run --rm --no-deps --entrypoint python api -c "from app.config import get_settings; get_settings()" \
  || die "설정 검증 실패: .env의 필수 변수와 product 안전 조건을 확인하세요(전환하지 않음)" 3

# 5) DB 덤프와 마이그레이션(전환 전). --no-migrate는 건너뛴다
if [ "$MIGRATE" = "true" ]; then
  log "db 기동"
  dc "$TAG" up -d --wait db || die "db 기동 실패" 4
  mkdir -p "$APP_HOME/backups"
  chmod 700 "$APP_HOME/backups" 2>/dev/null || true
  DUMP="$APP_HOME/backups/pre-$TAG-$(date -u +%Y%m%d%H%M%S)Z.dump"
  log "DB 덤프: $(basename "$DUMP")"
  # db 컨테이너 안의 환경변수와 로컬 소켓을 쓰므로 호스트 쪽에 비밀이 나오지 않는다
  if ! dc "$TAG" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DUMP.partial"; then
    rm -f "$DUMP.partial"
    die "DB 덤프 실패(전환하지 않음)" 4
  fi
  mv "$DUMP.partial" "$DUMP" || die "덤프 파일 이름을 바꾸지 못했습니다" 4
  log "마이그레이션"
  dc "$TAG" --profile migrate run --rm migrate || die "마이그레이션 실패(전환하지 않음). 덤프: $DUMP" 5
else
  log "--no-migrate: 덤프와 마이그레이션을 건너뜁니다"
fi

# 6) 전환
log "전환: $TAG"
switch_to "$DEPLOY_DIR" || die "current 링크를 바꾸지 못했습니다" 1
SWITCH_OK="true"
dc "$TAG" up -d --wait --wait-timeout "$WAIT_TIMEOUT" --remove-orphans || SWITCH_OK="false"

# 7) 헬스체크: web을 거쳐 api까지 확인한다. 루프백이라 인증서 이름 확인만 끈다
healthy() {
  local i=1
  while [ "$i" -le "$HEALTH_RETRIES" ]; do
    if curl -fsS --max-time 3 --insecure "$HEALTH_URL" > /dev/null; then return 0; fi
    sleep "$HEALTH_INTERVAL"
    i=$((i + 1))
  done
  return 1
}

# 8) 성공 후 정리: 최근 KEEP_DEPLOYS개 + 현재 + 직전, 덤프 최근 KEEP_BACKUPS개, 14일 지난 키트
cleanup() {
  local count=0 dir name
  for dir in $(ls -1dt "$APP_HOME"/deploys/*/ 2>/dev/null); do
    dir="${dir%/}"
    name="$(basename "$dir")"
    count=$((count + 1))
    [ "$count" -le "$KEEP_DEPLOYS" ] && continue
    [ "$name" = "$TAG" ] && continue
    [ -n "$PREV" ] && [ "$dir" = "$PREV" ] && continue
    docker image rm "$REGISTRY_VALUE/neoine-sales/api:$name" "$REGISTRY_VALUE/neoine-sales/web:$name" > /dev/null 2>&1 || true
    rm -rf "$dir"
  done
  count=0
  for dir in $(ls -1t "$APP_HOME"/backups/*.dump 2>/dev/null); do
    count=$((count + 1))
    [ "$count" -le "$KEEP_BACKUPS" ] && continue
    rm -f "$dir"
  done
  find "$APP_HOME/incoming" -name 'deploy-*.tar.gz' -mtime +14 -delete 2>/dev/null || true
}

if [ "$SWITCH_OK" = "true" ] && healthy; then
  log "헬스체크 통과: $TAG"
  cleanup
  exit 0
fi

# 9) 실패: 이전 버전이 있으면 이전 태그·이전 compose로 되돌린다(migrate는 하지 않는다)
echo "[deploy] 헬스체크 실패: $TAG" >&2
if [ -n "$PREV" ] && [ -d "$PREV" ] && [ "$PREV" != "$DEPLOY_DIR" ]; then
  PREV_TAG="$(basename "$PREV")"
  log "롤백: $PREV_TAG (마이그레이션은 되돌리지 않습니다. 필요하면 DB 덤프로 사람이 복원하세요)"
  switch_to "$PREV"
  dc "$PREV_TAG" pull api web || echo "[deploy] 이전 이미지 pull 실패(로컬 이미지로 계속)" >&2
  dc "$PREV_TAG" up -d --wait --wait-timeout "$WAIT_TIMEOUT" --remove-orphans \
    || echo "[deploy] 롤백 up 실패: 수동 확인이 필요합니다" >&2
else
  echo "[deploy] 이전 버전이 없어 컨테이너를 그대로 둡니다(진단: docker compose logs)" >&2
fi
exit 1
