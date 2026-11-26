#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
backend_dir="${script_dir}/../backend"

cd -- "$script_dir"
exec uv run --project "$backend_dir" python "$script_dir/import_contracts.py" "$@"
