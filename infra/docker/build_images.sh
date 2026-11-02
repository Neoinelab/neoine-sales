#!/usr/bin/env bash
# infra/docker/build_images.sh <이미지_태그> [--push]
# api·web 이미지를 만들고 배포 키트(build/deploy-<태그>.tar.gz)를 만든다. 환경변수 REGISTRY(레지스트리 주소)가 필요하다.
# web 이미지는 Jenkins Verify가 검증한 frontend/dist를 그대로 넣는다(이미지 안에서 다시 빌드하지 않음).
# --push이면 두 이미지를 push한다. 레지스트리 로그인은 호출한 쪽(Jenkins)이 한다(이 스크립트는 로그인하지 않는다).
set -uo pipefail

die() { echo "[build_images] $1" >&2; exit 2; }

TAG="${1:-}"
[[ "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "사용법: build_images.sh <이미지_태그> [--push] (허용되지 않는 태그: '$TAG')"
shift
PUSH="false"
while [ $# -gt 0 ]; do
  case "$1" in
    --push) PUSH="true"; shift ;;
    *) die "알 수 없는 옵션: $1" ;;
  esac
done

[ -n "${REGISTRY:-}" ] || die "환경변수 REGISTRY(레지스트리 주소)가 필요합니다"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || die "저장소 루트로 이동하지 못했습니다"
[ -f frontend/dist/index.html ] || die "frontend/dist/index.html이 없습니다(Verify의 frontend 빌드 결과를 먼저 가져오세요)"

API_IMAGE="$REGISTRY/neoine-sales/api:$TAG"
WEB_IMAGE="$REGISTRY/neoine-sales/web:$TAG"

echo "[build_images] api 이미지: $API_IMAGE"
docker build -t "$API_IMAGE" --build-arg "RELEASE_TAG=$TAG" backend || exit 1
echo "[build_images] web 이미지: $WEB_IMAGE"
docker build -f infra/docker/web/Dockerfile -t "$WEB_IMAGE" . || exit 1

mkdir -p build || exit 1
tar -czf "build/deploy-$TAG.tar.gz" -C infra/docker compose.yaml deploy.sh || exit 1
echo "[build_images] 배포 키트: build/deploy-$TAG.tar.gz"

if [ "$PUSH" = "true" ]; then
  docker push "$API_IMAGE" || exit 1
  docker push "$WEB_IMAGE" || exit 1
fi
