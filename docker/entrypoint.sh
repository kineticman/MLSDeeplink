#!/usr/bin/env bash
set -euo pipefail

# Timezone (best-effort only; don't spam errors on read-only filesystems)
if [ -n "${TZ:-}" ] && [ -e "/usr/share/zoneinfo/$TZ" ] && [ -w /etc/localtime ]; then
  ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime 2>/dev/null || true
  echo "$TZ" > /etc/timezone 2>/dev/null || true
fi

mkdir -p /out /logs

# Render nginx.conf from template using PORT
if [ ! -f /etc/nginx/nginx.conf.tmpl ]; then
  echo "[entrypoint] ERROR: /etc/nginx/nginx.conf.tmpl not found"
  sleep 5; exit 1
fi

# Use envsubst from gettext-base
envsubst '${PORT}' < /etc/nginx/nginx.conf.tmpl > /etc/nginx/nginx.conf || {
  echo "[entrypoint] ERROR: envsubst failed to render nginx.conf"
  sleep 5; exit 1
}

# Sanity-check nginx config before starting
if ! nginx -t; then
  echo "[entrypoint] ERROR: nginx config test failed"
  sed -n '1,200p' /etc/nginx/nginx.conf || true
  sleep 10; exit 1
fi

# Start the daily runner in background
if [ -x /daily_runner.sh ]; then
  /daily_runner.sh &
else
  echo "[entrypoint] WARNING: /daily_runner.sh not found or not executable"
fi

echo "[entrypoint] Starting nginx on port ${PORT}"
exec nginx -g 'daemon off;'
