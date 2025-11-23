# MLS Deeplink

Scrape MLS schedule data from Apple TV and generate a simple **M3U** + **XMLTV** that deep-link into the Apple TV app (and can be reused by other platforms like Fire TV as integration evolves).

The project runs as a single Docker container with a built-in daily scheduler (no host cron) and an NGINX web server that serves the generated files from `/out`.

- Single container: **scheduler + NGINX**
- **ENV-driven** configuration (no `.env` file required)
- Health endpoint at `/health`
- Artifacts written to `/out` and served over HTTP:
  - `mls.m3u` — M3U playlist
  - `guide.xml` — XMLTV EPG
  - `mls_schedule.json` — normalized schedule
  - `raw_canvas.json` — raw scrape for debugging

---

## Option 1: Portainer (recommended)

If you use **Portainer**, you can deploy MLSDeeplink as a stack using the prebuilt image on GHCR.

1. In Portainer, go to **Stacks → Add stack**
2. Name it something like `mlsdeeplink`
3. Paste this as the **Stack file**:

```yaml
version: "3.8"

services:
  mlsdeeplink:
    image: ghcr.io/kineticman/mlsdeeplink:latest
    container_name: mlsdeeplink

    # Change the left side (8096) if you want a different host port
    ports:
      - "8096:8096"

    environment:
      TZ: "America/New_York"   # your timezone
      PORT: "8096"             # internal NGINX port (leave as 8096)
      RUN_AT: "04:17"          # daily scrape time (HH:MM in TZ)
      OUTPUT_DIR: "/out"       # where files are written in the container

    volumes:
      - mlsdeeplink_out:/out
      - mlsdeeplink_logs:/logs

    restart: unless-stopped

volumes:
  mlsdeeplink_out:
  mlsdeeplink_logs:
```

4. Click **Deploy the stack**
5. After it comes up, you should see an `mlsdeeplink` container in Portainer → Containers.

---

## Option 2: Docker + Compose (CLI)

If you prefer the command line:

```bash
git clone https://github.com/kineticman/MLSDeeplink.git
cd MLSDeeplink

# Choose your settings (override as you like)
export HOST_PORT=8096        # host port
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

First-run populate (so you don’t have to wait for the scheduled time):

```bash
docker exec -it mlsdeeplink bash -lc 'cd /app/scripts && OUTPUT_DIR=/out ./generate.sh && ./validate.sh && ls -l /out'
```

---

## Accessing the Output

Assuming your host is `myhost.local` and you exposed port `8096`:

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

Adjust hostname/port to match your setup.

---

## Configuration (ENV variables)

Whether you’re using Portainer or `docker compose`, these env vars control behavior:

| Variable     | Default            | Purpose                                            |
|-------------|--------------------|----------------------------------------------------|
| `HOST_PORT` | `8096`             | Host port published by Compose / stack             |
| `PORT`      | `8096`             | Internal NGINX listen port                         |
| `TZ`        | `America/New_York` | Container timezone (scheduler uses this)           |
| `RUN_AT`    | `04:17`            | Daily run time (HH:MM) in `TZ`                     |
| `OUTPUT_DIR`| `/out`             | Directory where artifacts are written and served   |

Example `docker-compose.yml` for CLI use:

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
- Make sure you didn’t accidentally mount over `/etc/nginx` (the image ships its own template)
- For Portainer users: double-check that the stack YAML matches the example above and that `PORT` is `8096`.

**`/` returns 404**

- Server is up but no files yet — run the manual generate command inside the container:
  ```bash
  docker exec -it mlsdeeplink bash -lc 'cd /app/scripts && OUTPUT_DIR=/out ./generate.sh && ./validate.sh'
  ```

**Permission issues for `out/` or `logs/` (CLI mode)**

```bash
sudo chown -R "$USER":"$USER" out logs && chmod 755 out logs
```

---

## Project Layout

```text
docker/               # entrypoint, scheduler, nginx template
scripts/              # generate + validate
out/                  # generated artifacts (bind-mounted or named volume)
logs/                 # scheduler log (bind-mounted or named volume)
scrape_mls_schedule.py
export_mls_outputs.py
docker-compose.yml
Dockerfile
```

## License

MIT
