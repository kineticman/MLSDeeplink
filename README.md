# MLS Deeplink

Scrape MLS schedule data from Apple TV and generate a simple **M3U** + **XMLTV** that deep-link into the Apple TV app (and can be reused by other platforms like Fire TV as integration evolves).

The project ships as a single Docker service with a built-in daily scheduler (no host cron) and an NGINX web server that serves the generated files from `/out`.

## Features

- Single container: **scheduler + NGINX** (no host cron required)
- **ENV-driven** configuration (no `.env` file required)
- Health endpoint at `/health`
- Artifacts written to `/out` and served over HTTP:
  - `mls.m3u` — M3U playlist
  - `guide.xml` — XMLTV EPG
  - `mls_schedule.json` — normalized schedule
  - `raw_canvas.json` — raw scrape for debugging

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
docker exec -it mlsdeeplink bash -lc 'cd /app/scripts && OUTPUT_DIR=/out ./generate.sh && ./validate.sh && ls -l /out'
```

---

## Accessing the Output

Assuming your host is `myhost.local` and `HOST_PORT=8096`:

- **Directory listing**  
  `http://myhost.local:8096/`

- **M3U playlist**  
  `http://myhost.local:8096/mls.m3u`

- **XMLTV guide**  
  `http://myhost.local:8096/guide.xml`

- **JSON schedule**  
  `http://myhost.local:8096/mls_schedule.json`

- **Raw scrape (debug)**  
  `http://myhost.local:8096/raw_canvas.json`

### Example: Channels DVR

- **M3U URL**: `http://myhost.local:8096/mls.m3u`  
- **XMLTV URL**: `http://myhost.local:8096/guide.xml`

Adjust host/port as needed.

---

## Configuration (ENV variables)

You can set these in your shell before `docker compose up`, or hard-code them in `docker-compose.yml` under `environment:`.

| Variable     | Default            | Purpose                                            |
|-------------|--------------------|----------------------------------------------------|
| `HOST_PORT` | `8096`             | Host port published by Compose                     |
| `PORT`      | `8096`             | Internal NGINX listen port                         |
| `TZ`        | `America/New_York` | Container timezone (scheduler uses this)           |
| `RUN_AT`    | `04:17`            | Daily run time (HH:MM) in `TZ`                     |
| `OUTPUT_DIR`| `/out`             | Directory where artifacts are written and served   |

### Example: hard-code into `docker-compose.yml`

```yaml
services:
  mlsdeeplink:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/kineticman/mlsdeeplink:latest
    container_name: mlsdeeplink

    ports:
      - "${HOST_PORT:-8096}:${PORT:-8096}"

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

---

## Troubleshooting

**Container restarts / CrashLoopBackOff**

- Check logs: `docker logs mlsdeeplink`
- Make sure only `docker/nginx.conf.tmpl` exists (no stale `nginx.conf`)

**`/` returns 404**

- Server is up but no files yet — run the manual generate command above

**Permission issues for `out/` or `logs/`**

```bash
sudo chown -R "$USER":"$USER" out logs && chmod 755 out logs
```

---

## Project Layout

```text
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
