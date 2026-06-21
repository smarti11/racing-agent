"""Backfill historical Pick 3 / Pick 4 payouts from Equibase.

Prerequisite for Phase 3. The pick_payouts table (created in Phase 1) needs
historical data so the Phase 3 picker can compute track-average payouts for EV
estimation.

Strategy:
1. For each date in the lookback window (default 60 days):
   2. For each track that had races on that date (from races table):
      3. Hit Equibase result index for that track
      4. For each race result link, fetch the race result HTML
      5. Parse Pick 3 / Pick 4 / Pick 5 / Pick 6 payouts using the existing parser
      6. INSERT INTO pick_payouts (skip duplicates via UNIQUE constraint)

Usage:
    venv/bin/python3 tools/backfill_pick34_payouts.py --days 60
    venv/bin/python3 tools/backfill_pick34_payouts.py --start 2026-03-01 --end 2026-05-10

Safe to re-run; UNIQUE(race_id, bet_type) prevents duplicates.
"""

import argparse
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.results import BASE, HEADERS, get_results_for_race
from db.database import get_conn, save_pick_payouts
from config.settings import REQUEST_DELAY, REQUEST_TIMEOUT

log_path = ROOT / "logs" / "backfill_pick34.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(log_path)),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pick34_backfill")


def get_races_for_date(date_yyyymmdd: str):
    """Get all races in DB for a date (YYYYMMDD)."""
    date_db = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, track_code, track_name, race_num "
        "FROM races WHERE race_date=? ORDER BY track_code, race_num",
        (date_db,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def already_have_payouts(race_id: int) -> bool:
    """Check if we've already pulled pick payouts for this race."""
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM pick_payouts WHERE race_id=?", (race_id,)
    ).fetchone()[0]
    conn.close()
    return n > 0


def store_pick_payouts(race_id: int, result: dict):
    """Extract pick3/pick4/pick5/pick6 from result dict, store rows."""
    return save_pick_payouts(race_id, result)


def backfill_one_date(date_yyyymmdd: str):
    """For a single date, pull pick payouts for every race in DB."""
    date_str = date_yyyymmdd
    date_pretty = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    logger.info(f"\n=== {date_pretty} ===")

    races = get_races_for_date(date_yyyymmdd)
    if not races:
        logger.info(f"  No races in DB; skipping")
        return 0, 0

    # Group races by track for index-page discovery
    tracks = {}
    for race in races:
        tracks.setdefault(race["track_code"], {
            "name": race["track_name"],
            "races": [],
        })["races"].append(race)

    total_stored = 0
    races_processed = 0
    races_skipped = 0

    for code, info in tracks.items():
        name = info["name"]

        # Verify result index exists for this track on this date
        day_url = f"{BASE}/results{code}{date_str}.html"
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(day_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue
        except Exception:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        posted_nums = set()
        for link in soup.find_all("a", href=True):
            href = link["href"].split("/")[-1]
            m = re.match(rf"results{code}(\d{{8}})(\d{{2}})\.html", href)
            if m and m.group(1) == date_str:
                posted_nums.add(int(m.group(2)))

        if not posted_nums:
            continue

        track_stored = 0
        for race in info["races"]:
            if race["race_num"] not in posted_nums:
                continue
            if already_have_payouts(race["id"]):
                races_skipped += 1
                continue

            result = get_results_for_race(code, date_str, race["race_num"])
            if not result:
                continue

            stored = store_pick_payouts(race["id"], result)
            track_stored += stored
            races_processed += 1

        total_stored += track_stored
        if track_stored:
            logger.info(f"  {name}: {track_stored} pick payouts stored")

    logger.info(
        f"=== {date_pretty} done: {total_stored} payouts stored, "
        f"{races_processed} races scanned, {races_skipped} skipped ==="
    )
    return total_stored, races_processed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=None, help="Backfill last N days")
    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    args = p.parse_args()

    today = date.today()
    if args.days is not None:
        end = today - timedelta(days=1)
        start = today - timedelta(days=args.days)
    elif args.start and args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        # Default 60-day window
        end = today - timedelta(days=1)
        start = today - timedelta(days=60)

    logger.info("=" * 60)
    logger.info(f"PICK 3/4 PAYOUT BACKFILL: {start} to {end}")
    logger.info("=" * 60)

    grand_stored = 0
    grand_processed = 0
    cur = start
    while cur <= end:
        date_yyyymmdd = cur.strftime("%Y%m%d")
        try:
            s, p_ = backfill_one_date(date_yyyymmdd)
            grand_stored += s
            grand_processed += p_
        except Exception as e:
            logger.error(f"Error on {cur}: {e}")
        cur += timedelta(days=1)

    logger.info("=" * 60)
    logger.info(
        f"BACKFILL DONE: {grand_stored} pick payouts stored "
        f"across {grand_processed} races"
    )
    logger.info("=" * 60)

    # Summary stats
    conn = get_conn()
    rows = conn.execute(
        "SELECT bet_type, COUNT(*) AS n, AVG(payout) AS avg, "
        "MIN(payout) AS minp, MAX(payout) AS maxp "
        "FROM pick_payouts GROUP BY bet_type ORDER BY bet_type"
    ).fetchall()
    conn.close()
    logger.info("\nSummary by bet type:")
    for r in rows:
        logger.info(
            f"  {r['bet_type']}: {r['n']} records · "
            f"avg ${r['avg']:.2f} · range ${r['minp']:.2f}-${r['maxp']:.2f}"
        )


if __name__ == "__main__":
    main()
