#!/usr/bin/env bash
set -euo pipefail

# --- locate repo root robustly (handles symlinks & cron) ---
SRC="${BASH_SOURCE[0]}"
while [ -L "$SRC" ]; do
  DIR="$(cd -- "$(dirname -- "$SRC")" >/dev/null 2>&1 && pwd -P)"
  SRC="$(readlink "$SRC")"
  [[ $SRC != /* ]] && SRC="$DIR/$SRC"
done
SCRIPT_DIR="$(cd -- "$(dirname -- "$SRC")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$REPO_ROOT"

# Optional: clearer failures in cron logs
trap 'echo "[generate.sh] FAILED at $(date -Is) in $REPO_ROOT" >&2' ERR
echo "[generate.sh] START $(date -Is) in $REPO_ROOT"

# Enter venv if present
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Ensure output dir exists (your scripts already use ./out)
mkdir -p out
rm -f out/mls_tvapple.xml out/mls_tvapple_control.m3u

# Run the pipeline
/usr/bin/python3 scrape_mls_schedule.py
/usr/bin/python3 export_mls_outputs.py

echo "✅ Artifacts:"
ls -1 out
echo "[generate.sh] DONE $(date -Is)"
