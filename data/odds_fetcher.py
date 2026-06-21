"""Fetch live win odds from Equibase desktop entry pages."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime

import pytz
import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_DELAY, REQUEST_TIMEOUT
from core.market import clean_odds_text
from db.database import get_conn, get_todays_races, save_odds

logger = logging.getLogger("racing_agent")
EASTERN = pytz.timezone("America/New_York")


def _desktop_entry_url(track_code: str, date_str: str) -> str:
    """date_str: YYYYMMDD → MMDDYY desktop URL."""
    mmddyy = date_str[4:6] + date_str[6:8] + date_str[2:4]
    return f"https://www.equibase.com/static/entry/{track_code}{mmddyy}USA-EQB.html"


def parse_desktop_odds_html(html: str) -> dict[int, dict[str, str]]:
    """Return {race_num: {program_num: odds_str}} for active (non-scratched) runners."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[int, dict[str, str]] = {}

    for row in soup.find_all("tr"):
        classes = row.get("class") or []
        if "scratch" in classes:
            continue

        odds_td = row.find("td", id=re.compile(r"^\d+-\d+$"))
        if not odds_td:
            continue

        try:
            race_num = int(odds_td["id"].split("-")[0])
            prog_num = str(int(odds_td["id"].split("-")[1]))
        except (ValueError, IndexError, KeyError):
            continue

        odds_str = clean_odds_text(odds_td.get_text(strip=True))
        if not odds_str:
            continue

        out.setdefault(race_num, {})[prog_num] = odds_str

    return out


def fetch_track_live_odds(track_code: str, date_str: str | None = None) -> dict[int, dict[str, str]]:
    """Fetch and parse live odds for one track. Returns {race_num: {prog: odds}}."""
    if not date_str:
        date_str = datetime.now(EASTERN).strftime("%Y%m%d")

    url = _desktop_entry_url(track_code, date_str)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Live odds: {track_code} HTTP {resp.status_code}")
            return {}
        if "Pardon Our Interruption" in resp.text:
            logger.warning(f"Live odds: {track_code} blocked by bot protection")
            return {}
        parsed = parse_desktop_odds_html(resp.text)
        logger.info(
            f"Live odds: {track_code} parsed {sum(len(v) for v in parsed.values())} "
            f"runners across {len(parsed)} races"
        )
        return parsed
    except Exception as e:
        logger.warning(f"Live odds fetch failed {track_code}: {e}")
        return {}


def _race_id_map(track_code: str, race_date: str) -> dict[int, int]:
    """Map race_num → race_id for today's card at track."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, race_num FROM races WHERE track_code=? AND race_date=?",
            (track_code, race_date),
        ).fetchall()
    return {int(r["race_num"]): r["id"] for r in rows}


def _horse_name(race_id: int, program_num: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT horse_name FROM entries WHERE race_id=? AND program_num=?",
            (race_id, program_num),
        ).fetchone()
    return row["horse_name"] if row else ""


def save_track_odds(track_code: str, race_date: str, parsed: dict[int, dict[str, str]]) -> int:
    """Persist parsed odds to DB. Returns count of odds rows saved."""
    id_map = _race_id_map(track_code, race_date)
    saved = 0
    for race_num, prog_odds in parsed.items():
        race_id = id_map.get(race_num)
        if not race_id:
            continue
        for prog_num, odds_str in prog_odds.items():
            name = _horse_name(race_id, prog_num)
            save_odds(race_id, prog_num, name, odds_str, odds_type="live")
            saved += 1
    return saved


def fetch_all_live_odds() -> int:
    """Fetch live odds for all tracks racing today. Returns total odds saved."""
    today = datetime.now(EASTERN).date().isoformat()
    date_str = today.replace("-", "")

    with get_conn() as conn:
        tracks = conn.execute(
            "SELECT DISTINCT track_code FROM races WHERE race_date=?",
            (today,),
        ).fetchall()

    total = 0
    for row in tracks:
        code = row["track_code"]
        parsed = fetch_track_live_odds(code, date_str)
        if parsed:
            total += save_track_odds(code, today, parsed)

    if total:
        logger.info(f"Live odds saved: {total} runner updates across {len(tracks)} tracks")
    else:
        logger.info("Live odds: no updates (off-hours or fetch blocked)")
    return total
