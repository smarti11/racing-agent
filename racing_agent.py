#!/usr/bin/env python3
"""
Horse Racing Research Agent
============================
Fetches daily entries, monitors scratches, tracks odds
for all US Thoroughbred tracks via Equibase mobile site.

Usage:
    python racing_agent.py              # Run continuously
    python racing_agent.py --once       # Single fetch then exit
    python racing_agent.py --tracks     # List today's active tracks
    python racing_agent.py --card       # Print today's card to terminal
    python racing_agent.py --dashboard  # Generate dashboard only
"""

import argparse
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

import pytz

from config.settings import (
    SCRAPE_INTERVAL_MIN,
    LOOP_INTERVAL_MIN,
    SCRATCH_CHECK_HOUR_ET,
    CANADIAN_TRACKS,
    DASHBOARD_PUBLIC_URL,
)
from data.equibase import get_todays_tracks, get_all_entries_today, get_scratches, get_scratches_desktop
from data.results import get_todays_results_all_tracks
from data.chart_fetcher import fetch_all_todays_charts
from core.scratch_fetcher import fetch_track_scratches
from core.pick_manager import save_todays_picks
from db.database import (
    init_db, save_race, save_entry, mark_scratched, mark_unscratched,
    save_result, grade_agent_picks,
    get_todays_races, get_race_entries as db_get_race_entries,
)

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/racing.log", mode="a")
    ]
)
logger = logging.getLogger("racing_agent")

EASTERN = pytz.timezone("US/Eastern")
REGEN_FLAG = Path.home() / "agents/racing-agent/.regen_now"


def _scratch_gate_open() -> bool:
    """True after SCRATCH_CHECK_HOUR_ET — avoids overnight false scratches."""
    return datetime.now(EASTERN).hour >= SCRATCH_CHECK_HOUR_ET


def fetch_todays_entries() -> int:
    """Fetch entries for all tracks racing today."""
    logger.info("Fetching today's entries from Equibase mobile...")
    total_races = 0
    total_entries = 0

    tracks = get_todays_tracks()
    if not tracks:
        logger.warning("No tracks found for today")
        return 0

    from config.settings import PRIORITY_TRACKS, PRIORITY_ONLY

    def priority_key(t):
        try:
            return PRIORITY_TRACKS.index(t["name"])
        except ValueError:
            return 999

    tracks = sorted(tracks, key=priority_key)
    if PRIORITY_ONLY:
        tracks = [t for t in tracks if t["name"] in PRIORITY_TRACKS]
        logger.info(f"Priority mode: fetching {len(tracks)} priority tracks only")

    allow_scratch = _scratch_gate_open()
    today = datetime.now(EASTERN).date().isoformat()

    for track in tracks:
        try:
            races = get_all_entries_today(track["code"], track["name"])
            for race in races:
                race_id = save_race(
                    race["track_code"],
                    race["track_name"],
                    today,
                    race["race_num"],
                    race,
                )
                for entry in race.get("entries", []):
                    save_entry(race_id, entry["program_num"], entry["horse_name"], entry)
                    if allow_scratch:
                        if entry.get("scratched"):
                            mark_scratched(race_id, entry["program_num"])
                        else:
                            mark_unscratched(race_id, entry["program_num"])
                    total_entries += 1
                total_races += 1
        except Exception as e:
            logger.warning(f"Error fetching {track['name']}: {e}")

    logger.info(f"Fetched {total_races} races / {total_entries} entries today")
    return total_races


def check_scratches() -> int:
    """Check all today's races for scratches."""
    if not _scratch_gate_open():
        now_et = datetime.now(EASTERN)
        logger.info(
            f"Scratch check skipped — before {SCRATCH_CHECK_HOUR_ET} AM ET "
            f"({now_et.strftime('%H:%M')} ET)"
        )
        return 0

    logger.info("Checking for scratches...")
    races = get_todays_races()
    checked_tracks = set()
    scratch_count = 0
    unscratch_count = 0

    race_lookup = {(race["track_code"], race["race_num"]): race["id"] for race in races}

    for race in races:
        track_code = race["track_code"]
        if track_code in checked_tracks:
            continue
        checked_tracks.add(track_code)

        if track_code in CANADIAN_TRACKS:
            scratches, unscratches = get_scratches(track_code)
        else:
            scratches, unscratches = get_scratches_desktop(track_code)

        for scratch in scratches:
            race_num = scratch.get("race_num")
            prog_num = scratch.get("program_num", "")
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                mark_scratched(matched_race_id, prog_num)
                scratch_count += 1
            else:
                logger.warning(f"Scratch not matched: {track_code} R{race_num} #{prog_num}")

        for item in unscratches:
            race_num = item.get("race_num")
            prog_num = item.get("program_num", "")
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                if mark_unscratched(matched_race_id, prog_num):
                    unscratch_count += 1

        for race_num, prog_num, horse_name, _reason in fetch_track_scratches(track_code):
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                mark_scratched(matched_race_id, prog_num)
                scratch_count += 1

    logger.info(f"Found {scratch_count} scratches, {unscratch_count} un-scratches")
    return scratch_count + unscratch_count


def fetch_todays_race_results() -> int:
    """Fetch and save results for all completed races today."""
    logger.info("Fetching today's race results...")
    tracks = get_todays_tracks()
    results = get_todays_results_all_tracks(tracks)
    saved = 0

    race_lookup = {
        (race["track_code"], race["race_num"]): race["id"]
        for race in get_todays_races()
    }

    for result in results:
        try:
            race_id = race_lookup.get((result["track_code"], result["race_num"]))
            if race_id:
                save_result(race_id, result)
                grade_agent_picks(race_id, result)
                saved += 1
        except Exception as e:
            logger.warning(f"Error saving result: {e}")

    logger.info(f"Saved {saved} results")
    return saved


def generate_dashboard():
    """Generate the racing dashboard HTML."""
    try:
        from core.pick4_picker import recommend_sequences_for_date
        from datetime import date as dt
        recs = recommend_sequences_for_date(dt.today().isoformat(), verbose=False)
        n_rec = sum(1 for r in recs if r.get("recommended"))
        if n_rec > 0:
            logger.info(f"Pick 3/4: {n_rec} recommended sequences")
    except Exception as e:
        logger.warning(f"Pick 3/4 sequence generation failed: {e}")

    from dashboard.builder import build_dashboard
    build_dashboard()
    logger.info("Dashboard generated → dashboard/racing.html")


def print_todays_card():
    """Print today's racing card to terminal."""
    races = [dict(r) for r in get_todays_races()]
    if not races:
        print("\nNo races found. Run with --once to fetch entries first.")
        return

    current_track = None
    for race in races:
        if race["track_name"] != current_track:
            current_track = race["track_name"]
            print(f"\n{'='*55}")
            print(f"  {current_track}")
            print(f"{'='*55}")

        entries = [dict(e) for e in db_get_race_entries(race["id"])]
        scratches = sum(1 for e in entries if e["scratched"])
        print(
            f"\n  Race {race['race_num']} — Post: {race.get('post_time', 'TBD')} | "
            f"{len(entries)} entries ({scratches} scratched)"
        )

        for entry in entries:
            scratch_flag = " [SCR]" if entry["scratched"] else ""
            odds = f" ML:{entry['morning_line']}" if entry.get("morning_line") else ""
            live = f" Live:{entry['live_odds']}" if entry.get("live_odds") else ""
            print(f"    #{entry['program_num']:2} {entry['horse_name']:<25}{scratch_flag}{odds}{live}")
            if entry.get("jockey"):
                print(f"         J: {entry['jockey']}  T: {entry.get('trainer', '?')}")


def _backup_database():
    try:
        backup_dir = Path.home() / "agents/racing-agent/backups"
        backup_dir.mkdir(exist_ok=True)
        db_path = Path.home() / "agents/racing-agent/db/racing.db"
        if db_path.exists():
            backup_path = backup_dir / f"racing_{datetime.now().strftime('%Y-%m-%d')}.db"
            if not backup_path.exists():
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backed up → {backup_path.name}")
    except Exception as e:
        logger.warning(f"Backup failed: {e}")


def _run_data_cycle() -> bool:
    """Scratches, results, charts, picks. Returns True if anything may have changed."""
    changed = False
    if check_scratches() > 0:
        changed = True

    if _scratch_gate_open():
        try:
            from core.scratch_fetcher import fetch_and_mark_scratches_for_today
            if fetch_and_mark_scratches_for_today():
                changed = True
        except Exception as e:
            logger.warning(f"Scratch fetcher error: {e}")
    else:
        hr = datetime.now(EASTERN).hour
        logger.info(
            f"Late-changes fetch skipped — before {SCRATCH_CHECK_HOUR_ET} AM ET ({hr}:xx ET)"
        )

    if fetch_todays_race_results() > 0:
        changed = True
    if fetch_all_todays_charts() > 0:
        changed = True

    try:
        from data.odds_fetcher import fetch_all_live_odds
        if fetch_all_live_odds() > 0:
            changed = True
    except Exception as e:
        logger.warning(f"Live odds fetch error: {e}")

    if save_todays_picks() > 0:
        changed = True
    return changed


def main():
    parser = argparse.ArgumentParser(description="Horse Racing Research Agent")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--tracks", action="store_true", help="List today's active tracks")
    parser.add_argument("--dashboard", action="store_true", help="Generate dashboard only")
    parser.add_argument("--card", action="store_true", help="Print today's card")
    args = parser.parse_args()

    init_db()

    if args.tracks:
        tracks = get_todays_tracks()
        print(f"\nTracks racing today ({len(tracks)}):")
        for t in tracks:
            print(f"  [{t['code']:5}] {t['name']}")
        return

    if args.dashboard:
        generate_dashboard()
        import socket
        import webbrowser
        import os as _os
        try:
            s = socket.create_connection(("localhost", 8081), timeout=1)
            s.close()
            webbrowser.open("http://localhost:8081/racing.html")
        except Exception:
            webbrowser.open("file://" + _os.path.abspath("dashboard/racing.html"))
        return

    if args.card:
        print_todays_card()
        return

    print(f"\n{'='*55}")
    print(f"  HORSE RACING RESEARCH AGENT")
    print(f"  Data refresh every {SCRAPE_INTERVAL_MIN} min")
    print(f"  Loop interval: {LOOP_INTERVAL_MIN} min")
    print(f"  Dashboard: {DASHBOARD_PUBLIC_URL}")
    print(f"  (HTTP :8081 + scratch :8082 managed by launchd)")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*55}\n")

    _backup_database()

    fetch_todays_entries()
    try:
        from data.odds_fetcher import fetch_all_live_odds
        fetch_all_live_odds()
    except Exception as e:
        logger.warning(f"Initial live odds fetch error: {e}")
    save_todays_picks()
    fetch_todays_race_results()
    generate_dashboard()

    if args.once:
        print_todays_card()
        return

    last_data_cycle = datetime.now()
    last_entries = datetime.now()
    scan_count = 0
    dashboard_dirty = False

    while True:
        try:
            now = datetime.now()
            data_due = (now - last_data_cycle).total_seconds() >= SCRAPE_INTERVAL_MIN * 60

            if data_due:
                if _run_data_cycle():
                    dashboard_dirty = True
                last_data_cycle = now

            et_now = datetime.now(EASTERN)
            entry_interval = 1800 if et_now.hour < 14 else 3600
            if (now - last_entries).total_seconds() >= entry_interval:
                fetch_todays_entries()
                save_todays_picks()
                last_entries = now
                dashboard_dirty = True

            if dashboard_dirty or REGEN_FLAG.exists():
                if REGEN_FLAG.exists():
                    try:
                        REGEN_FLAG.unlink()
                    except FileNotFoundError:
                        pass
                    logger.info("Manual scratch flag — regenerating dashboard")
                generate_dashboard()
                dashboard_dirty = False
                scan_count += 1
                logger.info(f"Dashboard updated — scan #{scan_count}")
            else:
                logger.info("No data changes — skipping dashboard rebuild")

            sleep_total = LOOP_INTERVAL_MIN * 60
            slice_seconds = 30
            slept = 0
            logger.info(f"Sleeping up to {LOOP_INTERVAL_MIN} min (watching for manual scratches)...")
            while slept < sleep_total:
                time.sleep(min(slice_seconds, sleep_total - slept))
                slept += slice_seconds
                if REGEN_FLAG.exists():
                    try:
                        REGEN_FLAG.unlink()
                    except FileNotFoundError:
                        pass
                    logger.info("Manual scratch detected — regenerating dashboard")
                    generate_dashboard()
                    dashboard_dirty = False
                    scan_count += 1
                    logger.info(f"Dashboard regenerated after manual scratch — scan #{scan_count}")

        except KeyboardInterrupt:
            logger.info("Racing agent stopped by user")
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
