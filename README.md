# MLS Apple TV Deep Links

Scrape MLS schedule data from Apple TV and generate a simple **M3U** + **XMLTV** that launch into the Apple TV app. The project ships as a single Docker service with a built‑in daily scheduler (no cron) and an NGINX web server that serves the generated files from `/out`.

## Features
- One-container stack: **scheduler + NGINX** (no host cron).
- **Environment‑variable driven** configuration (no `.env` file required).
- Health endpoint at `/health`.
- Artifacts: `mls.m3u`, `guide.xml`, `mls_schedule.json`, `raw_canvas.json`.

---

## Quick Start (Docker + Compose)

> Prereqs: Docker and Docker Compose.

```bash
git clone https://github.com/kineticman/MLSDeeplink.git
cd MLSDeeplink

# Choose your settings (override as you like)
export HOST_PORT=8096        # host port exposed by Compose
export PORT=8096             # internal NGINX port inside the container
export TZ=America/New_York   # container timezone
export RUN_AT=04:17          # daily time (HH:MM) in TZ
export OUTPUT_DIR=/out       # where artifacts are written inside the container

# Build and start
docker compose up -d --build
```

Check health:
```bash
curl -sS http://localhost:${HOST_PORT}/health && echo
```

First-run populate (until the daily time hits):
```bash
docker exec -it mlsappletv bash -lc 'cd /app/scripts && OUTPUT_DIR=/out ./generate.sh && ./validate.sh && ls -l /out'
```

Browse outputs:
- `http://<host>:${HOST_PORT}/` → directory listing (autoindex).

---

## Configuration (ENV variables)

Supply these **environment variables** to control behavior. You can set them inline before `docker compose up`, export them in your shell (as above), or hard‑code them under the `environment:` section in `docker-compose.yml`.

| Variable     | Default            | Purpose |
|--------------|--------------------|---------|
| `HOST_PORT`  | `80`               | Host port published by Compose (left side of `HOST:CONTAINER`) |
| `PORT`       | `8096`             | Internal NGINX listen port; templated into `nginx.conf` at startup |
| `TZ`         | `America/New_York` | Container timezone (scheduler uses this) |
| `RUN_AT`     | `04:17`            | Daily run time (HH:MM) in `TZ` |
| `OUTPUT_DIR` | `/out`             | Directory where artifacts are written and served |

### Example: inline overrides
```bash
HOST_PORT=8080 PORT=9000 RUN_AT=03:05 TZ=America/New_York docker compose up -d --build
```

### Example: hard-code into `docker-compose.yml`
```yaml
services:
  mlsappletv:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/kineticman/mlsappletv:latest
    container_name: mlsappletv

    ports:
      - "${HOST_PORT:-80}:${PORT:-8096}"

    environment:
      TZ:         "${TZ:-America/New_York}"
      PORT:       "${PORT:-8096}"
      RUN_AT:     "${RUN_AT:-04:17}"
      OUTPUT_DIR: "${OUTPUT_DIR:-/out}"

    volumes:
      - ./out:/out
      - ./logs:/logs

    restart: unless-stopped
```

> **Tip:** You can still change the values at run time without editing files by prefixing the `docker compose` command with the variables, e.g. `HOST_PORT=8080 PORT=9000 docker compose up -d`.

---

## Local Development (no Docker)

> Requirement: Python 3.10+ (stdlib only).

```bash
python3 scrape_mls_schedule.py
python3 export_mls_outputs.py

# or
./scripts/generate.sh
./scripts/validate.sh
```

Artifacts are written to `./out/`.

---

## Health, Logs, and Manual Runs

Health check:
```bash
curl -sS http://localhost:${HOST_PORT}/health && echo
```

Tail the daily runner log:
```bash
tail -n 200 logs/generate.log
```

Manual run inside the container:
```bash
docker exec -it mlsappletv bash -lc 'cd /app/scripts && OUTPUT_DIR=/out ./generate.sh && ./validate.sh'
```

---

## Troubleshooting

**Container restarts / CrashLoopBackOff**  
- Check logs: `docker logs mlsappletv`  
- Ensure only `docker/nginx.conf.tmpl` exists (not a stale `nginx.conf`).

**`/` returns 404**  
- The server is up, but no files yet. Run the manual generate command above.

**Permission issues on `out/` or `logs/` on the host**  
```bash
sudo chown -R "$USER":"$USER" out logs && chmod 755 out logs
```

---

## Project Layout

```
docker/               # entrypoint, scheduler, nginx template
scripts/              # generate + validate
out/                  # generated artifacts (bind-mounted)
logs/                 # scheduler log (bind-mounted)
scrape_mls_schedule.py
export_mls_outputs.py
docker-compose.yml
Dockerfile
```

## License
MIT
