#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python was not found. Install Python 3 and retry." >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/scripts/install_codex_library.py" \
  --process-skill-conflicts disable \
  --router-activation install \
  "$@"
