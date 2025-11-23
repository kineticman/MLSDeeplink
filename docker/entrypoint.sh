#!/usr/bin/env bash
set -euo pipefail

# Timezone (best-effort only; don't spam errors on read-only filesystems)
if [ -n "${TZ:-}" ] && [ -e "/usr/share/zoneinfo/$TZ" ] && [ -w /etc/localtime ]; then
  ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime 2>/dev/null || true
  echo "$TZ" > /etc/timezone 2>/dev/null || true
fi

mkdir -p /out /logs

TEMPLATE=/etc/nginx/nginx.conf.tmpl
DEST=/etc/nginx/nginx.conf
NGINX_CONF="$DEST"

# Ensure template exists
if [ ! -f "$TEMPLATE" ]; then
  echo "[entrypoint] ERROR: $TEMPLATE not found"
  sleep 5; exit 1
fi

render_nginx_conf() {
  envsubst '${PORT}' < "$TEMPLATE" > "$1"
}

# Try to render directly into /etc/nginx/nginx.conf if writable
if { [ -e "$DEST" ] && [ -w "$DEST" ]; } || { [ ! -e "$DEST" ] && [ -w /etc/nginx ]; }; then
  if ! render_nginx_conf "$DEST"; then
    echo "[entrypoint] ERROR: envsubst failed to render nginx.conf to $DEST"
    sleep 5; exit 1
  fi
else
  # Fall back to a writable location (e.g., read-only /etc on some hosts)
  NGINX_CONF=/tmp/nginx.conf
  if ! render_nginx_conf "$NGINX_CONF"; then
    echo "[entrypoint] ERROR: envsubst failed to render nginx.conf to $NGINX_CONF"
    sleep 5; exit 1
  fi
  echo "[entrypoint] WARNING: $DEST not writable; using $NGINX_CONF instead"
fi

# Sanity-check nginx config before starting
if ! nginx -t -c "$NGINX_CONF"; then
  echo "[entrypoint] ERROR: nginx config test failed"
  sed -n '1,200p' "$NGINX_CONF" || true
  sleep 10; exit 1
fi

# Start the daily runner in background
if [ -x /daily_runner.sh ]; then
  /daily_runner.sh &
else
  echo "[entrypoint] WARNING: /daily_runner.sh not found or not executable"
fi

echo "[entrypoint] Starting nginx on port ${PORT} with config $NGINX_CONF"
exec nginx -c "$NGINX_CONF" -g 'daemon off;'
