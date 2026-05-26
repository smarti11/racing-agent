"""Backfill race results for past dates.

The racing-agent normally only fetches results for *today*. If a race finishes
after the agent stops looking (or the agent was down), those picks stay ungraded
forever. This tool fetches results for any date range and grades the picks.

Usage:
    python3 tools/backfill_results.py --days 7
    python3 tools/backfill_results.py --start 2026-05-05 --end 2026-05-10
"""

import argparse
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.results import (
    BASE,
    HEADERS,
    get_results_for_race,
)
from db.database import get_conn, save_result, grade_agent_picks
from config.settings import REQUEST_DELAY, REQUEST_TIMEOUT

log_path = ROOT / "logs" / "backfill_results.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(log_path)),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def get_races_for_date(date_yyyymmdd: str):
    """Get all races we have in the DB for a date (YYYYMMDD format).

    Returns list of dicts with id, track_code, track_name, race_num.
    """
    # Convert YYYYMMDD to YYYY-MM-DD for the DB query
    date_db = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, track_code, track_name, race_num
        FROM races
        WHERE race_date = ?
        ORDER BY track_code, race_num
        """,
        (date_db,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tracks_with_results(date_yyyymmdd: str):
    """Discover which tracks posted results for a given date.

    Returns list of track codes.
    """
    # Use the index pages from Equibase to find tracks with that date
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT track_code FROM races WHERE race_date = ?",
        (f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}",),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def backfill_one_date(date_yyyymmdd: str):
    """Fetch all race results for a single date and grade picks.

    Returns (results_saved, picks_graded).
    """
    date_str = date_yyyymmdd
    date_pretty = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    logger.info(f"\n=== Backfilling {date_pretty} ===")

    races = get_races_for_date(date_yyyymmdd)
    if not races:
        logger.info(f"No races in DB for {date_pretty}; skipping")
        return 0, 0

    logger.info(f"Found {len(races)} races in DB across "
                f"{len(set(r['track_code'] for r in races))} tracks")

    # Group races by track to test track-level result availability
    tracks = {}
    for race in races:
        tracks.setdefault(race["track_code"], {
            "name": race["track_name"],
            "races": [],
        })["races"].append(race)

    total_saved = 0
    total_graded = 0

    for code, info in tracks.items():
        name = info["name"]
        # First verify track has results posted for this date
        day_url = f"{BASE}/results{code}{date_str}.html"
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(day_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.info(f"  {name}: no results page (HTTP {resp.status_code})")
                continue
        except Exception as e:
            logger.warning(f"  {name}: page fetch failed: {e}")
            continue

        # Discover which race numbers have results posted
        soup = BeautifulSoup(resp.text, "html.parser")
        posted_race_nums = set()
        for link in soup.find_all("a", href=True):
            href = link["href"].split("/")[-1]
            m = re.match(rf"results{code}(\d{{8}})(\d{{2}})\.html", href)
            if m and m.group(1) == date_str:
                posted_race_nums.add(int(m.group(2)))

        if not posted_race_nums:
            logger.info(f"  {name}: results page exists but no race links")
            continue

        logger.info(f"  {name}: {len(posted_race_nums)} race(s) posted")

        track_saved = 0
        track_graded = 0
        for race in info["races"]:
            if race["race_num"] not in posted_race_nums:
                continue

            result = get_results_for_race(code, date_str, race["race_num"])
            if not result:
                continue

            try:
                save_result(race["id"], result)

                # Count how many picks get graded for this race
                conn = get_conn()
                ungraded_before = conn.execute(
                    "SELECT COUNT(*) FROM agent_picks WHERE race_id=? AND result IS NULL",
                    (race["id"],),
                ).fetchone()[0]
                conn.close()

                grade_agent_picks(race["id"], result)

                conn = get_conn()
                ungraded_after = conn.execute(
                    "SELECT COUNT(*) FROM agent_picks WHERE race_id=? AND result IS NULL",
                    (race["id"],),
                ).fetchone()[0]
                conn.close()

                graded_this_race = ungraded_before - ungraded_after
                track_saved += 1
                track_graded += graded_this_race
            except Exception as e:
                logger.warning(f"  Save/grade error {name} R{race['race_num']}: {e}")

        if track_saved:
            logger.info(f"  {name}: saved {track_saved} results, graded {track_graded} picks")
            total_saved += track_saved
            total_graded += track_graded

    logger.info(f"=== {date_pretty} done: {total_saved} results, {total_graded} picks graded ===")
    return total_saved, total_graded


def backfill_range(start_date: datetime, end_date: datetime):
    """Backfill every date in [start_date, end_date] inclusive."""
    cur = start_date
    grand_saved = 0
    grand_graded = 0
    while cur <= end_date:
        date_yyyymmdd = cur.strftime("%Y%m%d")
        saved, graded = backfill_one_date(date_yyyymmdd)
        grand_saved += saved
        grand_graded += graded
        cur += timedelta(days=1)

    logger.info(f"\n=== ALL DONE: {grand_saved} results saved, {grand_graded} picks graded ===")
    return grand_saved, grand_graded


def main():
    p = argparse.ArgumentParser(description="Backfill past-date race results")
    p.add_argument("--days", type=int, default=None,
                   help="Backfill the last N days (excluding today)")
    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    args = p.parse_args()

    today = datetime.now()
    if args.days is not None:
        end = today - timedelta(days=1)
        start = today - timedelta(days=args.days)
    elif args.start and args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end, "%Y-%m-%d")
    elif args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = today - timedelta(days=1)
    else:
        # Default: yesterday only
        start = today - timedelta(days=1)
        end = today - timedelta(days=1)

    backfill_range(start, end)


if __name__ == "__main__":
    main()
