#!/usr/bin/env bash
# 릴리스 번들(tar.gz) 생성. Jenkins와 로컬에서 동일하게 쓴다.
#   사용법: infra/build_release.sh <tag>      (사전에 frontend에서 pnpm build 실행)
set -euo pipefail

TAG="${1:?usage: build_release.sh <tag>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="neoine-sales-$TAG"
OUT="$ROOT/build/$NAME"

[ -f "$ROOT/frontend/dist/index.html" ] || { echo "frontend/dist가 없습니다. 먼저 pnpm build를 실행하세요" >&2; exit 1; }

rm -rf "$ROOT/build"
mkdir -p "$OUT/backend" "$OUT/frontend"
cp -r "$ROOT/backend/src" "$ROOT/backend/alembic" "$ROOT/backend/alembic.ini" \
      "$ROOT/backend/pyproject.toml" "$ROOT/backend/uv.lock" "$OUT/backend/"
[ -f "$ROOT/backend/.python-version" ] && cp "$ROOT/backend/.python-version" "$OUT/backend/"
cp -r "$ROOT/frontend/dist" "$OUT/frontend/dist"
if [ -d "$ROOT/infra/server" ]; then
  mkdir -p "$OUT/infra" && cp -r "$ROOT/infra/server" "$OUT/infra/server"
fi
# 개발 중 생성물은 번들에 넣지 않는다
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "$TAG" > "$OUT/VERSION"
tar -czf "$ROOT/build/$NAME.tar.gz" -C "$ROOT/build" "$NAME"
echo "created build/$NAME.tar.gz"
