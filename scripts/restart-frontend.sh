#!/usr/bin/env bash
set -euo pipefail

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$scripts_dir/restart-service.sh" frontend 5173 "$@"
