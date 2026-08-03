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
    python racing_agent.py --refresh-race SAR 3 --scratch 10
                                        # Mark #10 scratched and re-handicap SAR R3
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
    DASHBOARD_OUTPUT,
    DASHBOARD_S3_ENABLED,
    DASHBOARD_S3_URI,
)
from data.equibase import get_todays_tracks, get_all_entries_today, get_scratches, get_scratches_desktop
from data.results import get_todays_results_all_tracks
from data.chart_fetcher import fetch_all_todays_charts
from core.scratch_fetcher import fetch_track_scratches
from core.pick_manager import save_todays_picks, refresh_race_picks
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

        weak_source = "mobile_diff" if track_code in CANADIAN_TRACKS else "desktop"

        for scratch in scratches:
            race_num = scratch.get("race_num")
            prog_num = scratch.get("program_num", "")
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                mark_scratched(matched_race_id, prog_num, source=weak_source)
                scratch_count += 1
            else:
                logger.warning(f"Scratch not matched: {track_code} R{race_num} #{prog_num}")

        for item in unscratches:
            race_num = item.get("race_num")
            prog_num = item.get("program_num", "")
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                if mark_unscratched(matched_race_id, prog_num, source=weak_source):
                    unscratch_count += 1

        for race_num, prog_num, horse_name, _reason in fetch_track_scratches(track_code):
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                mark_scratched(matched_race_id, prog_num, source="late_changes")
                scratch_count += 1

    logger.info(f"Found {scratch_count} scratches, {unscratch_count} un-scratches")
    return scratch_count + unscratch_count


def _run_scratch_pipeline() -> int:
    """Desktop + late-changes scratch detection. Returns total change count.

    Gated at SCRATCH_CHECK_HOUR_ET so overnight/stale Equibase pages cannot
    mark false scratches. Safe to call from --once, startup, and the loop.
    """
    changed = check_scratches()
    if not _scratch_gate_open():
        hr = datetime.now(EASTERN).hour
        logger.info(
            f"Late-changes fetch skipped — before {SCRATCH_CHECK_HOUR_ET} AM ET ({hr}:xx ET)"
        )
        return changed
    try:
        from core.scratch_fetcher import fetch_and_mark_scratches_for_today
        changed += fetch_and_mark_scratches_for_today() or 0
    except Exception as e:
        logger.warning(f"Scratch fetcher error: {e}")
    return changed


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
        from core.market import rebuild_actionable_bets_for_date
        from datetime import date as dt
        rebuild_actionable_bets_for_date(dt.today().isoformat())
    except Exception as e:
        logger.warning(f"Actionable bet rebuild failed: {e}")

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

    try:
        from dashboard.s3_publish import publish_dashboard_to_s3
        publish_dashboard_to_s3(
            DASHBOARD_OUTPUT,
            DASHBOARD_S3_URI,
            enabled=DASHBOARD_S3_ENABLED,
        )
    except Exception as e:
        logger.warning(f"S3 dashboard publish failed: {e}")


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
    if _run_scratch_pipeline() > 0:
        changed = True

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


def _port_listening(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _ensure_sidecar(port: int, name: str, argv: list[str]):
    """Start a sidecar process if nothing is already listening on port."""
    import subprocess

    if _port_listening(port):
        logger.info(f"{name} already listening on :{port}")
        return
    try:
        subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(Path(__file__).resolve().parent),
        )
        logger.info(f"{name} started on port {port}")
    except Exception as e:
        logger.warning(f"Could not start {name}: {e}")


def _ensure_scratch_server():
    """Start scratch_server.py if nothing is already listening on :8082.

    Prefer launchd (see launchd/install.sh) for reboot survival. Fall back to
    starting here so dashboard POST /scratch still works after a Mac restart
    when LaunchAgents were never installed.
    """
    import os
    import sys

    script = Path(__file__).resolve().parent / "scratch_server.py"
    if not script.exists():
        logger.warning(f"Scratch server script missing: {script}")
        return
    python = sys.executable
    venv_python = Path(os.environ["VIRTUAL_ENV"]) / "bin" / "python" if os.environ.get("VIRTUAL_ENV") else None
    if venv_python and venv_python.exists():
        python = str(venv_python)
    _ensure_sidecar(8082, "Scratch override server", [python, str(script)])


def _ensure_dashboard_server():
    """Start the static dashboard server on :8081 if it is not already up."""
    import os
    import sys

    root = Path(__file__).resolve().parent
    dashboard_dir = root / "dashboard"
    if not dashboard_dir.is_dir():
        logger.warning(f"Dashboard directory missing: {dashboard_dir}")
        return
    python = sys.executable
    venv_python = Path(os.environ["VIRTUAL_ENV"]) / "bin" / "python" if os.environ.get("VIRTUAL_ENV") else None
    if venv_python and venv_python.exists():
        python = str(venv_python)
    _ensure_sidecar(
        8081,
        "Dashboard server",
        [python, "-m", "http.server", "8081", "--bind", "0.0.0.0", "--directory", str(dashboard_dir)],
    )


def _ensure_sidecars():
    """Bring back :8081 / :8082 after a reboot if launchd did not."""
    _ensure_dashboard_server()
    _ensure_scratch_server()


def main():
    parser = argparse.ArgumentParser(description="Horse Racing Research Agent")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--tracks", action="store_true", help="List today's active tracks")
    parser.add_argument("--dashboard", action="store_true", help="Generate dashboard only")
    parser.add_argument("--card", action="store_true", help="Print today's card")
    parser.add_argument(
        "--refresh-race",
        nargs=2,
        metavar=("TRACK", "RACE_NUM"),
        help="Force re-handicap one race (e.g. --refresh-race SAR 3). "
             "Bypasses post-time freeze; still blocked if results posted.",
    )
    parser.add_argument(
        "--scratch",
        type=int,
        metavar="PROGRAM",
        help="With --refresh-race: mark this program number scratched before refreshing",
    )
    args = parser.parse_args()

    init_db()

    if args.refresh_race:
        track_code, race_num_s = args.refresh_race
        try:
            race_num = int(race_num_s)
        except ValueError:
            print(f"Invalid race number: {race_num_s}")
            return
        ok = refresh_race_picks(track_code, race_num, scratch_program=args.scratch)
        if ok:
            generate_dashboard()
            print(f"Refreshed picks for {track_code.upper()} R{race_num}")
            if args.scratch is not None:
                print(f"  (marked #{args.scratch} scratched)")
        else:
            print(f"Failed to refresh {track_code.upper()} R{race_num} — see logs")
        return

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
    print(f"  (HTTP :8081 / scratch :8082 — launchd or agent fallback after reboot)")
    print(f"  Scratch gate opens at {SCRATCH_CHECK_HOUR_ET}:00 ET")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*55}\n")

    _backup_database()
    if not args.once:
        _ensure_sidecars()

    fetch_todays_entries()
    # Dedicated scratch detection must run before the first handicapping pass.
    # Without this, --once (and the initial continuous-mode cycle) never calls
    # check_scratches / late-changes — only the loop does, and only after
    # SCRAPE_INTERVAL_MIN. Before SCRATCH_CHECK_HOUR_ET this is a no-op by design.
    try:
        _run_scratch_pipeline()
    except Exception as e:
        logger.warning(f"Initial scratch check error: {e}")
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
                    # Manual scratch: re-handicap dirty races first, then render.
                    # Previously only rebuilt the dashboard from stale agent_picks.
                    logger.info("Manual scratch flag — refreshing picks then dashboard")
                    try:
                        if save_todays_picks() > 0:
                            dashboard_dirty = True
                    except Exception as e:
                        logger.warning(f"Pick refresh after manual scratch failed: {e}")
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
                    logger.info("Manual scratch detected — refreshing picks then dashboard")
                    try:
                        save_todays_picks()
                    except Exception as e:
                        logger.warning(f"Pick refresh after manual scratch failed: {e}")
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
