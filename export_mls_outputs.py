#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MLS Apple TV Exporter (v0.9: placeholders add local start-time desc)
# - Live games with two teams
# - JSON, M3U (with tvg-id), XLSX/CSV, XMLTV
# - Hero descriptions from raw_canvas.json
# - start/stop uses duration when available; else +2h
# - Placeholders (1h base, <=2h):
#   • Pre: from (floor(now to :00/:30) - 30m) up to event start
#       - title: "Event not started"
#       - desc:  "<Match Title> starts <local day/time tz>"
#   • Post: from ceil(event end to :00/:30) for 4h
#       - title: "Event ended"
#       - desc:  (none — per-entry channel has no next event)

from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import json, html, argparse, re

pd = None
# -------------------- Basics --------------------

def load_matches(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "matches" in data and isinstance(data["matches"], list):
            return data["matches"]
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        return []
    return data if isinstance(data, list) else []

def _normalize_airing_type(v: Optional[str]) -> str:
    return (v or "").strip().lower()

def is_live_with_teams(m: dict) -> bool:
    if _normalize_airing_type(m.get("airing_type")) != "live":
        return False
    return bool(m.get("team1_name")) and bool(m.get("team2_name"))

# -------------------- URLs --------------------

def strip_ctx_brand(u: str) -> str:
    try:
        parsed = urlparse(u)
        q = [(k, v) for (k, v) in parse_qsl(parsed.query, keep_blank_values=True) if k != "ctx_brand"]
        new_query = urlencode(q, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return u

def normalize_page_url(u: str) -> str:
    if not u: return ""
    u = u.strip()
    dbl = "https://tv.apple.comhttps://tv.apple.com"
    if u.startswith(dbl): u = "https://tv.apple.com" + u[len(dbl):]
    if u.startswith("/") : u = "https://tv.apple.com" + u
    return strip_ctx_brand(u)

def extract_umc_cse_id_from_url(u: str) -> str:
    if not u: return ""
    try:
        p = urlparse(u)
        qs = dict(parse_qsl(p.query, keep_blank_values=True))
        tid = qs.get("targetId", "")
        if isinstance(tid, str) and tid.startswith("umc.cse."):
            return tid
        for seg in [s for s in p.path.split("/") if s]:
            if seg.startswith("umc.cse."):
                return seg
    except Exception:
        pass
    return ""

def build_deeplink(page_url: str, playable_id: str) -> str:
    page_url = normalize_page_url(page_url)
    if not page_url: return ""
    if not playable_id: return page_url
    p = urlparse(page_url)
    q = dict(parse_qsl(p.query, keep_blank_values=True)); q["playableId"] = playable_id
    new_q = urlencode(q, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))

# -------------------- Hero maps --------------------

def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _walk(it)

def _normalize_team_bits(s: str) -> List[str]:
    s = (s or "").lower()
    s = s.replace("football club", "fc").replace("club de foot", "cf")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return [p for p in re.split(r"\s+", s) if p]

def _title_key_variants(title: str) -> List[Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    t = (title or "").lower().replace(" vs. ", " vs ").replace(" at ", " at ")
    if " vs " in t: a, b = t.split(" vs ", 2)
    elif " at " in t: a, b = t.split(" at ", 2)
    else: a, b = t, ""
    away_bits = tuple(_normalize_team_bits(a)); home_bits = tuple(_normalize_team_bits(b))
    return [(away_bits, home_bits), (home_bits, away_bits)]

def load_hero_maps(raw_canvas_path: Path) -> Tuple[Dict[str, str], Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], str]]:
    hero_by_umc: Dict[str, str] = {}
    hero_by_title: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], str] = {}
    try:
        if not raw_canvas_path.exists(): return hero_by_umc, hero_by_title
        data = json.loads(raw_canvas_path.read_text(encoding="utf-8"))
        for d in _walk(data):
            h = d.get("heroDescription")
            if not h: continue
            u = d.get("url") or ""
            umc = extract_umc_cse_id_from_url(u)
            if umc: hero_by_umc.setdefault(umc, h)
            t = d.get("title") or ""
            for key in _title_key_variants(t):
                hero_by_title.setdefault(key, h)
    except Exception:
        pass
    return hero_by_umc, hero_by_title

# -------------------- Time & duration --------------------

def _coerce_time_value(v) -> str:
    """
    Accept ISO string, epoch sec/ms, or dict containing those -> ISO with Z when possible.
    """
    def _to_iso(val):
        try:
            if isinstance(val, (int, float)):
                sec = float(val) / (1000.0 if val >= 1_000_000_000_000 else 1.0)
                dt = datetime.fromtimestamp(sec, tz=timezone.utc)
                return dt.isoformat().replace("+00:00","Z")
            if isinstance(val, str):
                return val.strip()
        except Exception:
            pass
        return ""

    if v is None or v == "": return ""
    if isinstance(v, (str, int, float)): return _to_iso(v)
    if isinstance(v, dict):
        for k in ("gameKickOffStartTime","kickoff","start","startTime","iso","utc","epoch","ms","millis"):
            if k in v:
                iso = _to_iso(v[k]); 
                if iso: return iso
        for vv in v.values():
            iso = _coerce_time_value(vv)
            if iso: return iso
    return ""

def parse_event_time(iso_like) -> Optional[datetime]:
    if iso_like is None or iso_like == "": return None
    if isinstance(iso_like, dict):
        iso_like = _coerce_time_value(iso_like) or ""
        if not iso_like: return None
    if isinstance(iso_like, (int, float)):
        try:
            sec = float(iso_like) / (1000.0 if iso_like >= 1_000_000_000_000 else 1.0)
            return datetime.fromtimestamp(sec, tz=timezone.utc)
        except Exception:
            return None
    s = str(iso_like).strip()
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None

def _normalize_duration_seconds(v) -> int:
    """
    Convert duration fields (seconds or milliseconds or dicts containing them) -> integer seconds.
    >= 10^7 -> treat as ms. Returns 0 if unknown.
    """
    try:
        if v is None: return 0
        if isinstance(v, (int, float)): val = float(v)
        elif isinstance(v, str) and v.strip(): val = float(v.strip())
        elif isinstance(v, dict):
            for k in ("ms","millis","milliseconds","durationMs","durationMS","duration_ms","durationMsValue"):
                if k in v: return _normalize_duration_seconds(v[k])
            for k in ("s","sec","seconds","durationS","duration_s","secondsValue"):
                if k in v: return _normalize_duration_seconds(v[k])
            for vv in v.values():
                sec = _normalize_duration_seconds(vv)
                if sec: return sec
            return 0
        else:
            return 0
        return int(val // 1000) if val >= 10_000_000 else int(val)
    except Exception:
        return 0

# :00/:30 helpers
def floor_30(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0)

def ceil_30(dt: datetime) -> datetime:
    f = floor_30(dt)
    return f if f == dt else (f + timedelta(minutes=30))

# Local time pretty printer
def pretty_local(dt: datetime) -> str:
    try:
        loc = dt.astimezone()  # system local tz
        # Example: "Thursday 8:30 PM EST" (drop leading zero on hour)
        s = loc.strftime("%A %I:%M %p %Z")
        return s.replace(" 0", " ")
    except Exception:
        return dt.strftime("%Y-%m-%d %H:%M %Z")

# -------------------- Transform --------------------

def build_rows_from_scrapeonly(matches: List[dict],
                               hero_by_umc: Dict[str, str],
                               hero_by_title: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], str]) -> Tuple[List[dict], List[dict]]:
    summaries, playables = [], []
    for m in matches:
        if not is_live_with_teams(m): continue

        home = m.get("team1_name") or ""
        away = m.get("team2_name") or ""
        title = m.get("title") or f"{home} vs. {away}"

        page_url = normalize_page_url(m.get("deep_link") or m.get("url") or "")
        playable_id = m.get("playable_id") or ""
        deeplink = build_deeplink(page_url, playable_id)

        start_time = _coerce_time_value(m.get("event_time"))
        end_time   = _coerce_time_value(m.get("end_time"))
        venue      = m.get("venue") or ""
        sport_name = m.get("sportName") or m.get("sport") or "Soccer"
        duration_s = _normalize_duration_seconds(m.get("duration") or m.get("duration_s"))

        # Hero
        hero_desc = (m.get("heroDescription") or m.get("hero_description") or "").strip()
        if not hero_desc:
            umc = extract_umc_cse_id_from_url(page_url) or extract_umc_cse_id_from_url(deeplink)
            if umc and umc in hero_by_umc: hero_desc = hero_by_umc[umc]
        if not hero_desc:
            for key in _title_key_variants(title):
                if key in hero_by_title:
                    hero_desc = hero_by_title[key]; break

        summaries.append({
            "title": title,
            "short_title": m.get("shortTitle") or m.get("short_title") or "",
            "sport_name": sport_name,
            "type": m.get("type") or "SportingEvent",
            "hero_description": hero_desc,
            "home_team": home, "away_team": away,
            "start_time": start_time, "end_time": end_time,
            "duration_s": duration_s,
            "venue": venue,
            "primary_playable_id": playable_id,
            "primary_url": page_url,
            "deeplink_url": deeplink,
        })

        if playable_id or deeplink:
            playables.append({
                "title": title,
                "playable_id": playable_id,
                "deeplink_url": deeplink,
                "page_url": page_url,
            })
    return summaries, playables

# -------------------- Writers --------------------

def write_json(summaries: List[dict], playables: List[dict], out_json: Path) -> None:
    out_json.write_text(json.dumps({"summary": summaries, "playables": playables}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"📝 wrote JSON: {out_json.resolve()}  (summary={len(summaries)}, playables={len(playables)})")

def write_m3u(summaries: List[dict], out_m3u: Path, group: str, base_ch: int) -> None:
    lines = ["#EXTM3U\n"]; ch = base_ch
    for s in summaries:
        url = s.get("primary_url") or s.get("deeplink_url") or ""
        if not url: continue
        title = s.get("title") or "MLS Match"
        tvg_id = f"mls.apple.{ch}"
        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{title}" tvg-chno="{ch}" group-title="{group}",{title}\n{url}\n')
        ch += 1
    out_m3u.write_text("".join(lines), encoding="utf-8")
    print(f"📺 wrote M3U:  {out_m3u.resolve()}  (entries={ch - base_ch})")



def write_xlsx_or_csv(*args, **kwargs) -> None:
    return

def _emit_programme(parts: List[str], chan_id: str, start_dt: datetime, stop_dt: datetime,
                    title: str, subtitle: Optional[str]=None, desc: Optional[str]=None,
                    categories: Optional[List[str]]=None, live: bool=False) -> None:
    start_s = start_dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")
    stop_s  = stop_dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")
    parts.append(f'  <programme channel="{html.escape(chan_id)}" start="{start_s}" stop="{stop_s}">\n')
    parts.append(f'    <title lang="en">{html.escape(title)}</title>\n')
    if subtitle:
        parts.append(f'    <sub-title lang="en">{html.escape(subtitle)}</sub-title>\n')
    if desc:
        parts.append(f'    <desc lang="en">{html.escape(desc)}</desc>\n')
    if categories:
        for cat in categories:
            parts.append(f'    <category lang="en">{cat}</category>\n')
    if live:
        parts.append('    <live/>\n')
    parts.append('  </programme>\n')

def _emit_placeholders(parts: List[str], chan_id: str, window_start: datetime, window_end: datetime,
                       label: str, base_minutes: int = 60, desc_text: Optional[str]=None) -> None:
    """
    Emit placeholders on :00/:30 grid using 1-hour base blocks (<=2h each).
    Desc (if provided) will be attached to each emitted placeholder.
    """
    t = window_start
    step = timedelta(minutes=base_minutes)
    max_block = timedelta(hours=2)
    while t < window_end:
        t_next = min(window_end, t + step)
        if (t_next - t) > max_block:
            t_next = t + max_block
        _emit_programme(parts, chan_id, t, t_next, title=label, desc=desc_text)
        t = t_next

def write_xmltv(summaries: List[dict], out_xml: Path, base_ch: int, group: str) -> None:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    parts.append('<tv generator-info-name="MLS-AppleTV Exporter v0.9">\n')

    ch = base_ch
    for s in summaries:
        chan_id = f"mls.apple.{ch}"; title = s.get("title") or "MLS Match"
        parts.append(f'  <channel id="{html.escape(chan_id)}">\n')
        parts.append(f'    <display-name>{html.escape(title)}</display-name>\n')
        parts.append(f'    <display-name>{ch}</display-name>\n')
        parts.append(f'    <display-name>{html.escape(group)}</display-name>\n')
        parts.append('  </channel>\n')
        ch += 1

    now = datetime.now(timezone.utc)
    pre_anchor = floor_30(now) - timedelta(minutes=30)

    ch = base_ch
    for s in summaries:
        chan_id = f"mls.apple.{ch}"; title = s.get("title") or "MLS Match"
        away = s.get("away_team") or ""; home = s.get("home_team") or ""
        short_title = s.get("short_title") or ""; sport_name = s.get("sport_name") or ""
        ev_type = s.get("type") or ""; venue = s.get("venue") or ""
        hero = (s.get("hero_description") or "").strip()
        start_dt = parse_event_time(s.get("start_time") or "") or now  # fallback to now if missing
        stop_dt = parse_event_time(s.get("end_time") or "")
        if start_dt and not stop_dt:
            dur_sec = _normalize_duration_seconds(s.get("duration_s") or s.get("duration") or 0)
            stop_dt = start_dt + timedelta(seconds=dur_sec if dur_sec > 0 else 7200)

        # PRE placeholders: 1-hour base blocks from pre_anchor to start
        desc_pre = f'{title} starts {pretty_local(start_dt)}'
        if start_dt > pre_anchor:
            _emit_placeholders(parts, chan_id, pre_anchor, start_dt, label="Event not started", base_minutes=60, desc_text=desc_pre)

        # REAL programme
        desc_bits = []
        if short_title: desc_bits.append(short_title)
        if sport_name:  desc_bits.append(sport_name)
        if ev_type:     desc_bits.append(ev_type)
        pretty = " · ".join(desc_bits) if desc_bits else ""
        if hero:        pretty = f"{hero} — {pretty}" if pretty else hero
        if venue:       pretty = f"{pretty} @ {venue}" if pretty else f"@ {venue}"
        subtitle = f"{away} at {home}" if (home or away) else None
        cats = ["MLS","Soccer","Sports","Sports event"]
        _emit_programme(parts, chan_id, start_dt, stop_dt, title=title, subtitle=subtitle, desc=(pretty or None), categories=cats, live=True)

        # POST placeholders: 1-hour base blocks from ceil_30(stop_dt) to +4h (no desc)
        post_start = ceil_30(stop_dt)
        post_end = post_start + timedelta(hours=4)
        _emit_placeholders(parts, chan_id, post_start, post_end, label="Event ended", base_minutes=60, desc_text=None)

        ch += 1

    parts.append('</tv>\n')
    out_xml.write_text("".join(parts), encoding="utf-8")
    print(f"🗓️  wrote XMLTV: {out_xml.resolve()}  (channels={len(summaries)} programmes=varies with placeholders)")

# -------------------- CLI --------------------

from pathlib import Path
def main():
    ap = argparse.ArgumentParser(description="MLS Apple TV — Exporter (v0.9 placeholders with desc)")
    OUT_DIR = Path(__file__).parent / 'out'
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ap.add_argument("--src", default=str(OUT_DIR / 'mls_schedule.json'))
    ap.add_argument("--out-json", default=str(OUT_DIR / 'mls_deeplinks_preview.json'))
    ap.add_argument("--out-m3u",  default=str(OUT_DIR / 'mls_tvapple_control.m3u'))
    ap.add_argument("--out-xml",  default=str(OUT_DIR / 'mls_tvapple.xml'))
    ap.add_argument("--out-xlsx", default="mls_deeplinks_preview.xlsx")
    ap.add_argument("--group", default="MLS - AppleTV")
    ap.add_argument("--base-ch", type=int, default=9910)
    ap.add_argument("--raw-canvas", default=str(OUT_DIR / 'raw_canvas.json'))
    ap.add_argument("--preview", action="store_true", help="Also write preview JSON")
    args = ap.parse_args()

    hero_by_umc, hero_by_title = load_hero_maps(Path(args.raw_canvas))
    matches = load_matches(Path(args.src))
    summaries, playables = build_rows_from_scrapeonly(matches, hero_by_umc, hero_by_title)
    if args.preview:
        write_json(summaries, playables, Path(args.out_json))
    write_m3u(summaries, Path(args.out_m3u), args.group, args.base_ch)
    write_xmltv(summaries, Path(args.out_xml), args.base_ch, args.group)

if __name__ == "__main__":
    main()
