#!/usr/bin/env bash
# Bootstrap and run the verified local inference demo from any working directory.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
MODE="${1:-run}"
case "$MODE" in
  --help|-h) printf 'Usage: ./start.sh [--check | --test]\n\nDefault: set up a local environment, verify evidence, run inference.\n--check: inspect dependencies and model integrity without installing or writing.\n--test: run the full test suite, then the demo.\n\nOverrides: PYTHON=/path/to/python3 ISAFORGE_VENV=/path/to/venv\n'; exit 0 ;;
  run|--check|--test) ;;
  *) printf 'Unknown option: %s. Use --help.\n' "$MODE" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then printf 'Expected at most one option. Use --help.\n' >&2; exit 2; fi
VENV="${ISAFORGE_VENV:-$ROOT/.venv}"
if [[ ! -x "$VENV/bin/python" ]]; then
  if [[ "$MODE" == --check ]]; then
    printf 'Missing environment: %s\nRun ./start.sh to create it.\n' "$VENV" >&2; exit 1
  fi
  if [[ -e "$VENV" ]]; then printf 'Incomplete environment: %s. Choose a fresh ISAFORGE_VENV path.\n' "$VENV" >&2; exit 1; fi
  BOOTSTRAP="${PYTHON:-python3}"
  if ! command -v "$BOOTSTRAP" >/dev/null 2>&1; then
    printf 'Python 3.11+ required. Install Python (macOS: brew install python; Ubuntu: apt install python3 python3-venv), then retry.\n' >&2; exit 1
  fi
  "$BOOTSTRAP" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python 3.11+ required")'
  "$BOOTSTRAP" -m venv "$VENV"
fi
PY="$VENV/bin/python"
if ! "$PY" -B scripts/startup.py --dependencies; then
  if [[ "$MODE" == --check ]]; then exit 1; fi
  printf '\nInstalling pinned dependencies into %s\n' "$VENV"
  "$PY" -m pip install -e '.[dev,reports]' -r requirements-research.txt
fi
"$PY" -B scripts/startup.py --check
if [[ "$MODE" == --check ]]; then exit 0; fi
if [[ "$MODE" == --test ]]; then "$PY" -m pytest -q; fi
exec "$PY" -B scripts/startup.py --demo
