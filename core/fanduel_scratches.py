"""Scratches from FanDuel Research race pages.

Since 2026-11-18 Equibase's www scratch feeds (desktop entries, late changes)
answer with an Imperva bot-check page. FanDuel Research's public race pages
(https://www.fanduel.com/research/horse-racing/picks/{CODE}/{slug}?race=N)
embed the race card as JSON in __NEXT_DATA__, with an explicit
`scratched` flag and the program number (`runnerId`) for every horse. robots.txt
only disallows /research/api, which this does not touch.

FanDuel (TVG) track codes mostly match Equibase's; FANDUEL_TRACK_CODES lists
the exceptions. A scratch is applied only when FanDuel's horse name matches the
name we have for that program number, so a wrong code or a renumbered card
can never mark the wrong horse.
"""

import json
import logging
import re
import time

import requests

logger = logging.getLogger("racing_agent")

URL = "https://www.fanduel.com/research/horse-racing/picks/{code}/race?race={race}"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
REQUEST_DELAY_SEC = 1.0

# Equibase code -> FanDuel/TVG code, where they differ (checked 2026-11-24).
FANDUEL_TRACK_CODES = {
    "PRX": "PHI",   # Parx Racing
    "MVR": "MVD",   # Mahoning Valley
}

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _find_race(obj, race_num):
    """Depth-first search of the page JSON for the race dict."""
    if isinstance(obj, dict):
        if "bettingInterests" in obj and str(obj.get("number")) == str(race_num):
            return obj
        for v in obj.values():
            r = _find_race(v, race_num)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_race(v, race_num)
            if r is not None:
                return r
    return None


def parse_race_page(html, race_num):
    """Returns [(program_num, horse_name, scratched)] or None if the page has
    no data for this race (wrong code, no card, layout change)."""
    m = _NEXT_DATA.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    race = _find_race(data, race_num)
    if not race:
        return None
    runners = []
    for bi in race.get("bettingInterests") or []:
        for r in bi.get("runners") or []:
            prog = str(r.get("runnerId") or "").strip()
            if prog:
                runners.append((prog, r.get("horseName") or "", bool(r.get("scratched"))))
    return runners or None


def fetch_race(track_code, race_num, session=None):
    code = FANDUEL_TRACK_CODES.get(track_code, track_code)
    url = URL.format(code=code, race=race_num)
    try:
        resp = (session or requests).get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    except Exception as e:
        logger.warning(f"[FANDUEL] {track_code} R{race_num}: {e}")
        return None
    if resp.status_code != 200:
        logger.warning(f"[FANDUEL] {track_code} R{race_num}: HTTP {resp.status_code}")
        return None
    return parse_race_page(resp.text, race_num)


def match_scratches(runners, db_entries):
    """Compare FanDuel runners with our entries for one race.

    db_entries: iterable of dicts/rows with program_num, horse_name.
    Returns (scratch_progs, running_progs, mismatches). Only horses whose name
    matches ours for that program number are returned."""
    ours = {str(e["program_num"]): e["horse_name"] for e in db_entries}
    scratched, running, mismatches = [], [], []
    for prog, name, is_scr in runners:
        if prog not in ours:
            continue
        if _norm(ours[prog]) != _norm(name):
            mismatches.append((prog, ours[prog], name))
            continue
        (scratched if is_scr else running).append(prog)
    return scratched, running, mismatches


def get_track_scratches(track_code, races, get_entries):
    """races: [(race_id, race_num)] still to run. get_entries(race_id) -> entries.

    Returns (scratches, reinstated, ok) where scratches / reinstated are
    [(race_id, program_num)] and ok says whether FanDuel had data for any race."""
    scratches, reinstated, ok = [], [], False
    session = requests.Session()
    for race_id, race_num in races:
        runners = fetch_race(track_code, race_num, session)
        time.sleep(REQUEST_DELAY_SEC)
        if runners is None:
            continue
        ok = True
        scr, running, mismatches = match_scratches(runners, get_entries(race_id))
        for prog, ours, theirs in mismatches:
            logger.warning(
                f"[FANDUEL] {track_code} R{race_num} #{prog}: name mismatch "
                f"(ours '{ours}', FanDuel '{theirs}') — ignored"
            )
        scratches += [(race_id, p) for p in scr]
        reinstated += [(race_id, p) for p in running]
    if not ok:
        logger.warning(f"[FANDUEL] {track_code}: no race data — check FANDUEL_TRACK_CODES")
    return scratches, reinstated, ok
