#!/usr/bin/env bash
set -euo pipefail

# --- locate repo root robustly (works under cron & docker) ---
SRC="${BASH_SOURCE[0]}"
while [ -L "$SRC" ]; do
  DIR="$(cd -- "$(dirname -- "$SRC")" >/dev/null 2>&1 && pwd -P)"
  SRC="$(readlink "$SRC")"
  [[ $SRC != /* ]] && SRC="$DIR/$SRC"
done
SCRIPT_DIR="$(cd -- "$(dirname -- "$SRC")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$REPO_ROOT"

trap 'echo "[generate.sh] FAILED at $(date -Is) in $REPO_ROOT" >&2' ERR
echo "[generate.sh] START $(date -Is) in $REPO_ROOT"

# Optional venv
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Resolve python binary from PATH (works in python:3.11-slim)
PY_BIN="${PY_BIN:-python3}"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  echo "[generate.sh] ERROR: '$PY_BIN' not found on PATH" >&2
  exit 127
fi

# Where to place final artifacts (container sets OUTPUT_DIR=/out)
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/out}"
mkdir -p "$OUTPUT_DIR"

# Run pipeline with unbuffered py output
"$PY_BIN" -u scrape_mls_schedule.py
"$PY_BIN" -u export_mls_outputs.py

# Ensure expected artifacts exist in repo out/, then copy into OUTPUT_DIR (no-op if same)
for f in guide.xml mls.m3u mls_schedule.json raw_canvas.json; do
  if [ -f "out/$f" ] && [ "$OUTPUT_DIR" != "$REPO_ROOT/out" ]; then
    cp -f "out/$f" "$OUTPUT_DIR/$f"
  fi
done

echo "✅ Artifacts in $OUTPUT_DIR:"
ls -1 "$OUTPUT_DIR" || true
echo "[generate.sh] DONE $(date -Is)"

# Add poster art to guide.xml (post-process)
python3 -u inject_icons.py || echo "[generate.sh] inject_icons.py failed (non-fatal)"
