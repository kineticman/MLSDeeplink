# MLSAppleTV: NGINX + daily runner (no cron)
FROM python:3.11-slim

# Keep Python output unbuffered and avoid .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# System deps: nginx, tzdata, envsubst (gettext-base), xmllint, etc.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     tzdata nginx wget ca-certificates bash coreutils gettext-base libxml2-utils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer caching: install deps first
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App files
COPY . /app/

# Runtime helpers & nginx template
COPY docker/daily_runner.sh /daily_runner.sh
COPY docker/entrypoint.sh   /entrypoint.sh
COPY docker/nginx.conf.tmpl /etc/nginx/nginx.conf.tmpl

RUN chmod +x /daily_runner.sh /entrypoint.sh \
 && mkdir -p /out /logs /var/run/nginx

# Defaults (override in docker-compose)
ENV TZ=America/New_York \
    PORT=8096 \
    RUN_AT="04:17" \
    OUTPUT_DIR=/out

EXPOSE 8096

# Simple HTTP healthcheck against /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:${PORT}/health >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/entrypoint.sh"]
