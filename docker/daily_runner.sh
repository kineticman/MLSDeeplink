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

# Run the actual generator once
run_generate() {
  mkdir -p "$OUTPUT_DIR" "$(dirname "$LOG_FILE")"
  echo "[daily_runner] $(date -Is) starting generate" | tee -a "$LOG_FILE"
  # TODO: update this line to the real generator command/path for MLSDeeplink
  python /app/bin/generate_mls.py >>"$LOG_FILE" 2>&1
  echo "[daily_runner] $(date -Is) finished generate (exit=$?)" | tee -a "$LOG_FILE"
}

# Seconds until the next RUN_AT in TZ
secs_until_next_run() {
  IFS=':' read -r run_hour run_min <<<"$RUN_AT"

  # current time in TZ
  local now_ts next_ts
  now_ts=$(TZ="$TZ" date +%s)

  # today at RUN_AT in TZ
  next_ts=$(TZ="$TZ" date -d "today ${run_hour}:${run_min}:00" +%s)

  # if that time has already passed today, schedule for tomorrow
  if (( next_ts <= now_ts )); then
    next_ts=$(TZ="$TZ" date -d "tomorrow ${run_hour}:${run_min}:00" +%s)
  fi

  echo $(( next_ts - now_ts ))
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
