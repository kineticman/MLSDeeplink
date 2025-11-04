#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate || true
python3 scrape_mls_schedule.py
python3 export_mls_outputs.py
echo "✅ Artifacts:"; ls -1 out
