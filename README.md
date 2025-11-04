# MLS Apple TV Deep Links (Preview)

Scrape MLS schedule data from Apple TV and generate a simple M3U + XMLTV for use with players/launchers that can hand off to the Apple TV app.

## Quick start

```bash
# clone your fork
git clone https://github.com/kineticman/MLSAppleTV.git
cd MLSAppleTV

# run in two steps (outputs go to ./out)
python3 scrape_mls_schedule.py
python3 export_mls_outputs.py

# or one button
./scripts/generate.sh
```

## Outputs (written to `./out`)
- `mls_tvapple_control.m3u`
- `mls_tvapple.xml`
- `mls_schedule.json`
- `raw_canvas.json`

> Optional: include a preview JSON with `--preview`
```bash
python3 export_mls_outputs.py --preview  # writes out/mls_deeplinks_preview.json
```

## Notes
- No Excel export by default (end‑user friendly).
- If Apple changes endpoints/fields, re-run later (scripts will continue to write to `./out`).
- Repo keeps older experimental scripts under `archive/` for reference only.
