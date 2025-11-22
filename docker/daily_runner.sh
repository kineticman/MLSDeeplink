#!/usr/bin/env bash
set -euo pipefail

TZ="${TZ:-America/New_York}"
RUN_AT="${RUN_AT:-04:17}"           # HH:MM in TZ (local wall time)
OUTPUT_DIR="${OUTPUT_DIR:-/out}"
LOG_FILE="/logs/generate.log"

ensure_tz() {
  if [[ -e "/usr/share/zoneinfo/$TZ" ]]; then
    ln -sf "/usr/share/zoneinfo/$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
  fi
}

# seconds until the next RUN_AT in TZ
secs_until_next_run() {
  local now_ts next_ts today target
  today=$(TZ="$TZ" date +%Y-%m-%d)
  target="$today $RUN_AT:00"
  now_ts=$(TZ="$TZ" date +%s)
  next_ts=$(TZ="$TZ" date -d "$target" +%s || TZ="$TZ" date -jf "%Y-%m-%d %H:%M:%S" "$target" +%s 2>/dev/null || true)

  # If that time today already passed, use tomorrow
  if (( next_ts <= now_ts )); then
    target=$(TZ="$TZ" date -d "tomorrow $RUN_AT:00" +%Y-%m-%d' '%H:%M:%S 2>/dev/null || TZ="$TZ" date -v+1d +"%Y-%m-%d $RUN_AT:00")
    next_ts=$(TZ="$TZ" date -d "$target" +%s 2>/dev/null || TZ="$TZ" date -j -f "%Y-%m-%d %H:%M:%S" "$target" +%s)
  fi
  echo $(( next_ts - now_ts ))
}

run_generate() {
  echo "[daily_runner] $(date -Is) starting generate..." | tee -a "$LOG_FILE"
  mkdir -p /logs "$OUTPUT_DIR"
  /usr/bin/flock -n /tmp/mlsapple_generate.lock \
    bash -lc "cd /app/scripts && OUTPUT_DIR='${OUTPUT_DIR}' ./generate.sh" \
    >> "$LOG_FILE" 2>&1 || true
  echo "[daily_runner] $(date -Is) done." | tee -a "$LOG_FILE"
}

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
