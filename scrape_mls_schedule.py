#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple TV MLS Schedule Scraper — CLEAN OUTPUT (v2)
=================================================
- Fixes mojibake by using real Unicode emojis (or ASCII fallback with --no-emoji).
- Forces UTF‑8 stdout when possible.
- Keeps the same API flow/fields as your working version.
"""

import sys, os, argparse, json, requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# --- Try to force UTF‑8 stdout if the terminal supports it (Py3.7+) ---
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def _supports_utf8() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return "UTF-8" in enc.upper()

def _symbols(use_emoji: bool):
    """Return a dict of symbols, emoji or ASCII depending on use_emoji flag and terminal support."""
    if use_emoji and _supports_utf8():
        return {
            "trophy": "🏆",
            "star": "⭐",
            "live": "🔴",
            "soccer": "⚽",
            "done": "✅",
            "err": "❌",
            "info": "ℹ️",
            "id": "🆔",
            "film": "🎬",
            "link": "🔗",
            "pin": "📍",
            "time": "🕒",
            "file": "📄",
            "book": "📚",
            "sparkles": "✨",
            "check": "✅",
            "party": "🥳",
        }
    # ASCII fallback
    return {
        "trophy": "[*]",
        "star": "*",
        "live": "[LIVE]",
        "soccer": "[SOCCER]",
        "done": "[OK]",
        "err": "[X]",
        "info": "[i]",
        "id": "[ID]",
        "film": "[PLAYABLE]",
        "link": "[URL]",
        "pin": "[VENUE]",
        "time": "[TIME]",
        "file": "[FILE]",
        "book": "[SUMMARY]",
        "sparkles": "[*]",
        "check": "[OK]",
        "party": "[DONE]",
    }

def _normalize_event_time(val):
    """Return an ISO8601-like string for event_time regardless of schema or None if unknown."""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        for k in ("iso8601", "string", "utc", "value", "start", "time"):
            v = val.get(k)
            if isinstance(v, str):
                return v
    return None
OUT_DIR = Path(__file__).parent / 'out'
OUT_DIR.mkdir(parents=True, exist_ok=True)


class MLSAPIClient:
    """Client for Apple TV MLS API"""
    BASE_URL = "https://tv.apple.com/api/uts/v3"
    MLS_CHANNEL = "tvs.sbd.7000"

    # Your session tokens
    UTSK = "6e3013c6d6fae3c2::::::9b5dc2888bdb9b92"
    UTSCF = "OjAAAAEAAAAAAAIAEAAAACMAKwAtAA~~"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://tv.apple.com",
            "Referer": "https://tv.apple.com/us/channel/mls-season-pass/tvs.sbd.7000",
        })

    def get_default_params(self) -> Dict:
        return {
            "caller": "web",
            "locale": "en-US",
            "pfm": "web",
            "sf": "143441",
            "v": "90",
            "utsk": self.UTSK,
            "utscf": self.UTSCF,
        }

    def get_channel_canvas(self) -> Optional[Dict]:
        url = f"{self.BASE_URL}/canvases/channels/{self.MLS_CHANNEL}"
        try:
            response = self.session.get(url, params=self.get_default_params(), timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[X] Error: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"[X] Error: {e}")
            return None

    def parse_canvas(self, canvas_data: Dict) -> List[Dict]:
        matches = []
        seen_ids = set()
        shelves = canvas_data.get("data", {}).get("canvas", {}).get("shelves", [])
        for shelf in shelves:
            items = shelf.get("items", [])
            for item in items:
                if item.get("type") == "SportingEvent":
                    event_id = item.get("id")
                    if event_id in seen_ids:
                        continue
                    seen_ids.add(event_id)
                    match = self._parse_canvas_item(item)
                    if match:
                        matches.append(match)
        return matches

    def _parse_canvas_item(self, item: Dict) -> Optional[Dict]:
        try:
            match = {
                "event_id": item.get("id"),
                "title": item.get("title"),
                "short_title": item.get("shortTitle"),
                "league": item.get("leagueName"),
                "league_abbr": item.get("leagueAbbreviation"),
                "sport": item.get("sportName"),
                "venue": item.get("venueName"),
                "url": item.get("url"),
                "airing_type": item.get("airingType"),
                "badge": item.get("badge"),
                "event_time": item.get("eventTime"),
                "end_time": item.get("endAirTime"),
            }

            # Images/Artwork
            images = {}
            if item.get("images"):
                images["main"] = item["images"]
            if item.get("artwork"):
                images["artwork"] = item["artwork"]
            if item.get("thumbnails"):
                images["thumbnails"] = item["thumbnails"]
            if item.get("coverArt"):
                images["coverArt"] = item["coverArt"]
            if item.get("previewFrame"):
                images["previewFrame"] = item["previewFrame"]
            if images:
                match["images"] = images

            # Teams
            competitors = item.get("competitors", [])
            if len(competitors) >= 2:
                team1 = competitors[0]; team2 = competitors[1]
                match["team1_name"] = team1.get("name"); match["team1_abbr"] = team1.get("abbreviation"); match["team1_id"] = team1.get("id")
                match["team2_name"] = team2.get("name"); match["team2_abbr"] = team2.get("abbreviation"); match["team2_id"] = team2.get("id")
                
                # Team images
                if team1.get("images") or team1.get("artwork") or team1.get("logo"):
                    match["team1_images"] = {k: v for k, v in {
                        "images": team1.get("images"),
                        "artwork": team1.get("artwork"),
                        "logo": team1.get("logo")
                    }.items() if v}
                if team2.get("images") or team2.get("artwork") or team2.get("logo"):
                    match["team2_images"] = {k: v for k, v in {
                        "images": team2.get("images"),
                        "artwork": team2.get("artwork"),
                        "logo": team2.get("logo")
                    }.items() if v}

            # Playables
            playables = item.get("playables", [])
            if playables:
                p = playables[0]
                match["playable_id"] = p.get("id")
                match["playable_type"] = p.get("type")
                
                # Playable images - including the special contentImage composite
                playable_imgs = {}
                if p.get("images"):
                    playable_imgs["images"] = p["images"]
                if p.get("artwork"):
                    playable_imgs["artwork"] = p["artwork"]
                
                # Extract canonicalMetadata.images.contentImage.url - the composite image with team logos!
                canonical = p.get("canonicalMetadata", {})
                if canonical.get("images", {}).get("contentImage", {}).get("url"):
                    playable_imgs["contentImage"] = canonical["images"]["contentImage"]["url"]
                
                if playable_imgs:
                    match["playable_images"] = playable_imgs

            # Deep link
            if match["url"]:
                match["deep_link"] = f"https://tv.apple.com{match['url']}"
                if match.get("playable_id"):
                    from urllib.parse import quote
                    encoded = quote(match["playable_id"], safe="")
                    match["deep_link_full"] = f"{match['deep_link']}?playableId={encoded}"

            return match
        except Exception as e:
            print(f"[X] Parse error: {e}")
            return None

def print_match(match: Dict, index: int, SYM: Dict[str, str]):
    bar = "=" * 70
    print(f"\n{bar}\nMatch #{index}\n{bar}")

    title = match.get("title") or match.get("short_title")
    if title:
        print(f"{SYM['star']} {title}")

    team1_name = match.get("team1_name"); team1_abbr = match.get("team1_abbr")
    team2_name = match.get("team2_name"); team2_abbr = match.get("team2_abbr")
    if team1_name and team2_name:
        print(f"   {team1_name} ({team1_abbr}) vs {team2_name} ({team2_abbr})")

    league = match.get("league") or match.get("league_abbr")
    sport = match.get("sport")
    if league:
        print(f"{SYM['trophy']}  {league}" + (f" - {sport}" if sport else ""))

    if match.get("venue"):
        print(f"{SYM['pin']} {match['venue']}")

    badge = match.get("badge")
    airing_type = match.get("airing_type")
    event_time = match.get("event_time")

    if badge:
        lab = f"{badge}" + (f" ({airing_type})" if airing_type else "")
        print(lab)

    if event_time:
        try:
            dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            print(f"{SYM['time']} {dt.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
        except Exception:
            print(f"{SYM['time']} {event_time}")

    print(f"\n{SYM['id']} Event ID: {match.get('event_id')}")
    if match.get("playable_id"):
        playable = match["playable_id"]
        print(f"{SYM['film']} {playable[:60]}{'...' if len(playable) > 60 else ''}")

    # Display images if available
    if match.get("images"):
        print(f"\n🖼️  Images available: {', '.join(match['images'].keys())}")
    if match.get("team1_images"):
        print(f"   Team 1 images: {', '.join(match['team1_images'].keys())}")
    if match.get("team2_images"):
        print(f"   Team 2 images: {', '.join(match['team2_images'].keys())}")
    if match.get("playable_images"):
        print(f"   Playable images: {', '.join(match['playable_images'].keys())}")

    if match.get("deep_link"):
        link = match["deep_link"]
        print(f"\n{SYM['link']} {link[:100]}{'...' if len(link) > 100 else ''}")

def main():
    ap = argparse.ArgumentParser(description="MLS canvas scraper with clean UTF‑8/ASCII output")
    ap.add_argument("--no-emoji", action="store_true", help="Use ASCII-only symbols")
    args = ap.parse_args()

    SYM = _symbols(use_emoji=not args.no_emoji)

    bar = "=" * 70
    print(bar)
    print(f" {SYM['trophy']} Apple TV MLS Schedule Scraper {SYM['trophy']}")
    print(bar); print()

    client = MLSAPIClient()

    print("Fetching MLS channel data...")
    canvas = client.get_channel_canvas()
    if not canvas:
        print(f"{SYM['err']} Failed to fetch data"); return
    print(f"{SYM['done']} Success!\n")

    print("Saving raw canvas...")
    with open(OUT_DIR / 'raw_canvas.json', "w", encoding="utf-8") as f:
        json.dump(canvas, f, indent=2, ensure_ascii=False)
    print(f"{SYM['done']} Saved: out/raw_canvas.json\n")

    print("Parsing matches from canvas...")
    matches = client.parse_canvas(canvas)
    print(f"{SYM['done']} Found {len(matches)} unique matches!\n")

    if not matches:
        print(f"{SYM['err']} No matches found"); return

    print("="*70); print(" MATCHES"); print("="*70)

    def safe_sort(m):
        t = _normalize_event_time(m.get("event_time"))
        return t or "9999-12-31T23:59:59Z"

    sorted_matches = sorted(matches, key=safe_sort)
    for i, match in enumerate(sorted_matches, 1):
        print_match(match, i, SYM)

    print("\n" + "="*70); print("Saving data..."); print("="*70)
    with open(OUT_DIR / 'mls_schedule.json', "w", encoding="utf-8") as f:
        json.dump(sorted_matches, f, indent=2, ensure_ascii=False)
    print(f"{SYM['done']} Saved: out/mls_schedule.json")

    print("\n" + "="*70); print(" RAW CANVAS SUMMARY"); print("="*70)
    print(f"{SYM['book']} Total matches: {len(matches)}")

    live = [m for m in matches if (m.get("airing_type") or "").lower() == "live"]
    if live:
        print(f"{SYM['live']} Live: {len(live)}")

    upcoming = [m for m in matches if m.get("airing_type") in ["Upcoming", "Future"]]
    if upcoming:
        print(f"{SYM['time']} Upcoming: {len(upcoming)}")

    teams = set()
    for m in matches:
        if m.get("team1_name"): teams.add(m["team1_name"])
        if m.get("team2_name"): teams.add(m["team2_name"])
    print(f"{SYM['soccer']} Teams: {len(teams)}")

    leagues = set(m.get("league") for m in matches if m.get("league"))
    if leagues:
        print(f"{SYM['star']} Leagues: {', '.join(leagues)}")

    # Image statistics
    matches_with_images = sum(1 for m in matches if m.get("images"))
    matches_with_team_images = sum(1 for m in matches if m.get("team1_images") or m.get("team2_images"))
    matches_with_playable_images = sum(1 for m in matches if m.get("playable_images"))
    
    print(f"\n🖼️  Images:")
    print(f"   Matches with event images: {matches_with_images}/{len(matches)}")
    print(f"   Matches with team images: {matches_with_team_images}/{len(matches)}")
    print(f"   Matches with playable images: {matches_with_playable_images}/{len(matches)}")

    print("\n" + "="*70)
    print(f" {SYM['check']} DONE! {SYM['party']}")
    print("="*70)
    print("\nFiles created:")
    print(f"  {SYM['file']} mls_schedule.json - All match data")
    print(f"  {SYM['file']} raw_canvas.json   - Raw API response")
    print("\nView matches:")
    print("  cat out/mls_schedule.json | python3 -m json.tool")
    print()

if __name__ == "__main__":
    main()
