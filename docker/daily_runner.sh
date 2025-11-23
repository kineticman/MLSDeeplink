#!/usr/bin/env bash
set -euo pipefail

TZ="${TZ:-America/New_York}"
RUN_AT="${RUN_AT:-04:17}"           # HH:MM in TZ (local wall time)
OUTPUT_DIR="${OUTPUT_DIR:-/out}"
LOG_FILE="/logs/generate.log"

ensure_tz() {
  if [[ -e "/usr/share/zoneinfo/$TZ" && -w /etc/localtime ]]; then
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime 2>/dev/null || true
    echo "$TZ" > /etc/timezone 2>/dev/null || true
  fi
}

# seconds until the next RUN_AT in TZ
...

main() {
  ensure_tz
  # Optional warm-up on first boot:
  run_generate
  while true; do
    sleep_seconds=$(secs_until_next_run)
    echo "[daily_runner] $(date -Is) sleeping ${sleep_seconds}s until $RUN_AT $TZ" | tee -a "$LOG_FILE"
    sleep "$sleep_seconds"
    run_generate
  done
}

main
