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
import time
import os
import pytz
from datetime import datetime
from pathlib import Path

from config.settings import SCRAPE_INTERVAL_MIN, ODDS_INTERVAL_MIN
from data.equibase import get_todays_tracks, get_all_entries_today, get_scratches, get_scratches_desktop
from data.results import get_todays_results_all_tracks, get_results_for_race
from data.odds import get_best_odds
from data.chart_fetcher import fetch_all_todays_charts
from db.database import (
    init_db, save_race, save_entry, mark_scratched,
    save_odds, save_result, save_agent_picks, grade_agent_picks, get_conn,
    get_agent_pick_stats, get_todays_races, get_race_entries as db_get_race_entries
)

# ── Logging ────────────────────────────────────────────────────────────
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


def fetch_todays_entries():
    """Fetch entries for all tracks racing today."""
    logger.info("Fetching today's entries from Equibase mobile...")
    total_races = 0
    total_entries = 0

    tracks = get_todays_tracks()
    if not tracks:
        logger.warning("No tracks found for today")
        return 0

    # Sort priority tracks first
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

    for track in tracks:
        try:
            races = get_all_entries_today(track["code"], track["name"])
            today = datetime.now(pytz.timezone("US/Eastern")).date().isoformat()

            for race in races:
                race_id = save_race(
                    race["track_code"],
                    race["track_name"],
                    today,
                    race["race_num"],
                    race
                )
                for entry in race.get("entries", []):
                    save_entry(race_id, entry["program_num"], entry["horse_name"], entry)
                    # FETCH_SCRATCH_GATE: don't mark scratches before 7 AM ET
                    # Equibase returns stale overnight pages with false scratch indicators
                    _allow_scratch = True
                    try:
                        import pytz as _pytz
                        from datetime import datetime as _datetime
                        _et = _pytz.timezone('America/New_York')
                        if _datetime.now(_et).hour < 7:
                            _allow_scratch = False
                    except Exception as _gte:
                        logger.warning(f'FETCH_SCRATCH_GATE error: {_gte}')
                    if entry.get("scratched") and _allow_scratch:
                        mark_scratched(race_id, entry["program_num"])
                    total_entries += 1
                total_races += 1

        except Exception as e:
            logger.warning(f"Error fetching {track['name']}: {e}")

    logger.info(f"Fetched {total_races} races / {total_entries} entries today")
    return total_races

def check_scratches():
    """Check all today's races for scratches."""
    # SCRATCH_TIME_GATE: skip scratch detection before 7 AM ET
    # Prevents false positives when agent restarts overnight
    try:
        import pytz
        _et = pytz.timezone("America/New_York")
        _now_et = datetime.now(_et)
        if _now_et.hour < 10:
            logger.info(f"Scratch check skipped — before 10 AM ET ({_now_et.strftime('%H:%M')} ET)")
            return 0
    except Exception:
        pass
    logger.info("Checking for scratches...")
    races = get_todays_races()
    checked_tracks = set()
    scratch_count = 0

    # Build lookup: (track_code, race_num) -> race_id
    race_lookup = {}
    for race in races:
        race_lookup[(race["track_code"], race["race_num"])] = race["id"]

    for race in races:
        track_code = race["track_code"]
        if track_code in checked_tracks:
            continue
        checked_tracks.add(track_code)

        # Use desktop Equibase (explicit SCR markers) — fallback to mobile for non-USA tracks
        CANADIAN_TRACKS = {'WO', 'WOT', 'WOD', 'HST', 'GLD'}
        if track_code in CANADIAN_TRACKS:
            scratches = get_scratches(track_code)
        else:
            scratches = get_scratches_desktop(track_code)
        for scratch in scratches:
            race_num = scratch.get("race_num")
            prog_num = scratch.get("program_num", "")
            matched_race_id = race_lookup.get((track_code, race_num))
            if matched_race_id and prog_num:
                mark_scratched(matched_race_id, prog_num)
                scratch_count += 1
            else:
                logger.warning(f"Scratch not matched: {track_code} R{race_num} #{prog_num}")

    logger.info(f"Found {scratch_count} scratches")
    return scratch_count

    """
    Live odds from TVG/TwinSpires — skipped for now.
    Morning line odds are already included in Equibase entries.
    Phase 2 will add live tote odds.
    """
    logger.info("Odds update skipped — using morning line odds from entries")
    return 0


def fetch_todays_race_results():
    """Fetch and save results for all completed races today."""
    logger.info("Fetching today's race results...")
    tracks = get_todays_tracks()
    results = get_todays_results_all_tracks(tracks)
    saved = 0

    races = get_todays_races()
    for result in results:
        try:
            for race in races:
                if (race["track_code"] == result["track_code"] and
                    race["race_num"]   == result["race_num"]):
                    save_result(race["id"], result)
                    grade_agent_picks(race["id"], result)
                    # Scratches handled by check_scratches() via Equibase desktop
                    # Results-based absence detection removed — was causing false positives
                    saved += 1
                    break
        except Exception as e:
            logger.warning(f"Error saving result: {e}")

    logger.info(f"Saved {saved} results")
    return saved


def save_todays_picks():
    """Save role-based picks (WIN/PLACE/SHOW) for all of today's races.
    Now also saves score, win_prob (softmax), and morning_line per pick
    for Benter-style probability calibration analysis."""
    from core.handicapper import handicap_race, get_top_pick, role_ranked_picks
    from core.probabilities import scores_to_probabilities
    races = get_todays_races()
    saved = 0
    skipped_done = 0
    for race in races:
        # TAINTED_PARSE_REGEN: if existing rank-1 pick is TAINTED_PARSE, the
        # field now has >= 4 active entries, and no result yet, force re-handicap.
        # Evaluated before the freeze block because the post-time freeze fires early
        # for PM races stored without AM/PM (e.g. "4:40" parsed as 04:40 AM).
        _force_regen = False
        _regen_old_n = 0
        _regen_new_n = 0
        try:
            with get_conn() as _tc:
                if not _tc.execute(
                    "SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race["id"],)
                ).fetchone():
                    _tp_dq = _tc.execute(
                        "SELECT data_quality FROM agent_picks "
                        "WHERE race_id=? AND rank=1", (race["id"],)
                    ).fetchone()
                    if _tp_dq and _tp_dq["data_quality"] == "TAINTED_PARSE":
                        _regen_new_n = _tc.execute(
                            "SELECT COUNT(*) FROM entries "
                            "WHERE race_id=? AND scratched=0", (race["id"],)
                        ).fetchone()[0]
                        if _regen_new_n >= 4:
                            _regen_old_n = _tc.execute(
                                "SELECT COUNT(*) FROM entries WHERE race_id=?",
                                (race["id"],)
                            ).fetchone()[0]
                            _force_regen = True
        except Exception:
            pass

        # FREEZE_SKIP_APPLIED: skip races whose results are already posted
        # OR whose post time has already passed (POST_TIME_FREEZE).
        try:
            from db.database import get_conn
            import pytz, re as _re
            _et = pytz.timezone("America/New_York")
            _now_et = datetime.now(_et)
            with get_conn() as _c:
                _done = _c.execute(
                    "SELECT 1 FROM results WHERE race_id=? LIMIT 1",
                    (race["id"],),
                ).fetchone()
            if _done:
                skipped_done += 1
                continue
            # Also skip if post time has passed
            _pt = (race.get("post_time") or "").strip()
            _rd = race.get("race_date") or ""
            if _pt and _rd:
                _m = _re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", _pt, _re.IGNORECASE)
                if _m:
                    _hr, _min = int(_m.group(1)), int(_m.group(2))
                    _ampm = (_m.group(3) or "").upper()
                    if _ampm == "PM" and _hr != 12:
                        _hr += 12
                    elif _ampm == "AM" and _hr == 12:
                        _hr = 0
                    elif not _ampm and _hr < 8:
                        _hr += 12  # no AM/PM stored; times < 8 are PM (no US racing at 1-7 AM)
                    from datetime import datetime as _dtt
                    _post_dt = _et.localize(
                        _dtt.strptime(_rd, "%Y-%m-%d").replace(hour=_hr, minute=_min)
                    )
                    from datetime import timedelta as _td2
                    _freeze_dt2 = _post_dt - _td2(minutes=30)
                    if _now_et >= _freeze_dt2 and not _force_regen:
                        skipped_done += 1
                        continue
        except Exception:
            pass

        # Archive stale TAINTED_PARSE picks before overwriting
        if _force_regen:
            try:
                with get_conn() as _ac:
                    _old_picks = _ac.execute(
                        "SELECT rank, program_num, horse_name, confidence, role "
                        "FROM agent_picks WHERE race_id=? ORDER BY rank",
                        (race["id"],)
                    ).fetchall()
                    _arc_ts = datetime.now().isoformat()
                    for _op in _old_picks:
                        _ac.execute(
                            "INSERT INTO agent_picks_history "
                            "(race_id, rank, program_num, horse_name, confidence, "
                            "role, rendered_ts, trigger, data_quality) "
                            "VALUES (?,?,?,?,?,?,?,?,?)",
                            (race["id"], _op["rank"], _op["program_num"],
                             _op["horse_name"], _op["confidence"] or "",
                             _op["role"] or "", _arc_ts,
                             "tainted_parse_superseded", "TAINTED_PARSE")
                        )
            except Exception:
                pass

        try:
            entries = db_get_race_entries(race["id"])
            entry_dicts = [dict(e) for e in entries]
            scored  = handicap_race(
                entry_dicts,
                race["conditions"] or "",
                race["track_code"] or "",
                race["distance"] or ""
            )
            if not scored:
                continue

            # Compute win probabilities via softmax over active (non-scratched) horses
            active_scored = [s for s in scored if not s.get("scratched")]
            # DATA_QUALITY_FLAG
            _n_active = len(active_scored)
            _n_total  = len(scored)
            if _n_active < 3:
                _data_quality = "TAINTED_SCRATCH"
                logger.warning(f"TAINTED_SCRATCH: only {_n_active} active of {_n_total} total")
            elif _n_total < 4:
                _data_quality = "TAINTED_PARSE"
                logger.warning(f"TAINTED_PARSE: only {_n_total} entries in DB")
            else:
                _data_quality = "OK"
            scores_to_probabilities(active_scored, temperature=8.0)
            # Build a lookup so we can attach win_prob to picks below
            prob_map = {s["program_num"]: s.get("win_prob", 0.0) for s in active_scored}

            # Apply isotonic calibration if calibrator file exists
            calibrated_map = {}
            try:
                from core.calibrator import IsotonicCalibrator
                _cal = IsotonicCalibrator.load("models/calibrator_pick1.json")
                calibrated_map = {pgm: _cal.transform(p) for pgm, p in prob_map.items()}
            except Exception as _e:
                logger.warning(f"Calibrator unavailable: {_e}")

            # Build a morning_line lookup from entries
            ml_map = {e.get("program_num"): e.get("morning_line") for e in entry_dicts}

            # Get confidence for top pick
            top = get_top_pick(scored)
            confidence = top.get("confidence", "LOW") if top else "LOW"
            scored[0]["confidence"] = confidence

            # Get role-based picks
            roles = role_ranked_picks(scored)
            picks = []
            for i, horse in enumerate(roles["all"]):
                pgm = horse["program_num"]
                picks.append({
                    "rank":             i + 1,
                    "program_num":      pgm,
                    "horse_name":       horse["horse_name"],
                    "confidence":       confidence if i == 0 else "",
                    "role":             horse.get("role", ""),
                    "score":            horse.get("score"),
                    "win_prob":         prob_map.get(pgm),
                    "morning_line":     ml_map.get(pgm),
                    "calibrated_prob":  calibrated_map.get(pgm),
                })
            for _p in picks:
                _p["data_quality"] = _data_quality
            save_agent_picks(race["id"], picks)
            if _force_regen:
                logger.info(
                    f"Regenerating picks {race['track_code']} R{race['race_num']}: "
                    f"was TAINTED_PARSE with {_regen_old_n} entries, "
                    f"now {_regen_new_n} active entries, new dq={_data_quality}"
                )
            try:
                with get_conn() as _ac:
                    _ea = _ac.execute(
                        "SELECT COUNT(*) n, "
                        "SUM(CASE WHEN scratched=0 THEN 1 ELSE 0 END) active, "
                        "MIN(first_fetched_ts) first_ts, MAX(fetched_ts) last_ts "
                        "FROM entries WHERE race_id=?",
                        (race["id"],)
                    ).fetchone()
                logger.info(
                    f"Entry audit {race['track_code']} R{race['race_num']}: "
                    f"{_ea['n']} entries ({_ea['active']} active) | "
                    f"first_fetched={(_ea['first_ts'] or 'none')[:19]} "
                    f"last_fetched={(_ea['last_ts'] or 'none')[:19]} | "
                    f"picks_created={datetime.now().isoformat()[:19]}"
                )
            except Exception:
                pass
            saved += 1
        except Exception as e:
            logger.warning(f"Pick save error for {race['track_name']} R{race['race_num']}: {e}")
    logger.info(f"Saved role-based picks for {saved} races")


def generate_dashboard():
    """Generate the racing dashboard HTML."""
    # PICK34_WIRED: Generate Pick 3/4 sequence recommendations
    try:
        from core.pick4_picker import recommend_sequences_for_date
        from datetime import date as _dt
        _recs = recommend_sequences_for_date(_dt.today().isoformat(), verbose=False)
        _n_rec = sum(1 for _r in _recs if _r.get('recommended'))
        if _n_rec > 0:
            logger.info(f'Pick 3/4: {_n_rec} recommended sequences')
    except Exception as _e:
        logger.warning(f'Pick 3/4 sequence generation failed: {_e}')

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
        print(f"\n  Race {race['race_num']} — Post: {race.get('post_time','TBD')} | {len(entries)} entries ({scratches} scratched)")

        for entry in entries:
            scratch_flag = " [SCR]" if entry["scratched"] else ""
            odds = f" ML:{entry['morning_line']}" if entry.get("morning_line") else ""
            live = f" Live:{entry['live_odds']}" if entry.get("live_odds") else ""
            print(f"    #{entry['program_num']:2} {entry['horse_name']:<25}{scratch_flag}{odds}{live}")
            if entry.get("jockey"):
                print(f"         J: {entry['jockey']}  T: {entry.get('trainer','?')}")


def main():
    parser = argparse.ArgumentParser(description="Horse Racing Research Agent")
    parser.add_argument("--once",      action="store_true", help="Single run then exit")
    parser.add_argument("--tracks",    action="store_true", help="List today's active tracks")
    parser.add_argument("--dashboard", action="store_true", help="Generate dashboard only")
    parser.add_argument("--card",      action="store_true", help="Print today's card")
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
        import socket, webbrowser, os as _os
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
    print(f"  Entries refresh every {SCRAPE_INTERVAL_MIN} min")
    print(f"  Results check every {SCRAPE_INTERVAL_MIN} min")
    print(f"  Dashboard: http://100.68.82.83:8081/racing.html")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*55}\n")

    # Start dashboard server on port 8081
    import subprocess, os
    os.system("lsof -ti:8081 | xargs kill -9 2>/dev/null")
    subprocess.Popen(
        ["python3", "-m", "http.server", "8081",
         "--bind", "0.0.0.0",
         "--directory", os.path.expanduser("~/Documents/racing-agent/dashboard")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    logger.info("Dashboard server started on port 8081")

    # Start scratch override server on port 8082
    os.system("lsof -ti:8082 | xargs kill -9 2>/dev/null")
    subprocess.Popen(
        ["python3", os.path.expanduser("~/Documents/racing-agent/scratch_server.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    logger.info("Scratch override server started on port 8082")

    # Auto-backup database each morning
    import shutil
    from pathlib import Path
    try:
        backup_dir = Path.home() / "Documents/racing-agent/backups"
        backup_dir.mkdir(exist_ok=True)
        db_path = Path.home() / "Documents/racing-agent/db/racing.db"
        if db_path.exists():
            backup_path = backup_dir / f"racing_{datetime.now().strftime('%Y-%m-%d')}.db"
            if not backup_path.exists():
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backed up → {backup_path.name}")
    except Exception as e:
        logger.warning(f"Backup failed: {e}")

    # Initial fetch
    fetch_todays_entries()
    save_todays_picks()
    fetch_todays_race_results()
    generate_dashboard()

    if args.once:
        print_todays_card()
        return

    last_scratch = datetime.now()
    last_odds    = datetime.now()
    last_entries = datetime.now()

    scan_count = 0
    while True:
        try:
            now = datetime.now()
            scan_count += 1

            if (now - last_scratch).seconds >= SCRAPE_INTERVAL_MIN * 60:
                check_scratches()
                # Real-time scratches from Equibase late-changes feed (faster than entries refresh)
                try:
                    from core.scratch_fetcher import fetch_and_mark_scratches_for_today
                    fetch_and_mark_scratches_for_today()
                except Exception as e:
                    logger.warning(f"Scratch fetcher error: {e}")
                fetch_todays_race_results()
                fetch_all_todays_charts()
                save_todays_picks()
                last_scratch = now

            # Fetch entries every 30 min before 2pm ET, hourly after
            et_now = now.astimezone(pytz.timezone("US/Eastern")) if now.tzinfo else datetime.now(pytz.timezone("US/Eastern"))
            entry_interval = 1800 if et_now.hour < 14 else 3600
            if (now - last_entries).seconds >= entry_interval:
                fetch_todays_entries()
                last_entries = now

            generate_dashboard()
            logger.info(f"Dashboard updated — scan #{scan_count}")
            
            # Sleep in 30s slices, watching for manual-scratch regen flag
            regen_flag = Path.home() / "Documents/racing-agent/.regen_now"
            sleep_total = ODDS_INTERVAL_MIN * 60
            slice_seconds = 30
            slept = 0
            logger.info(f"Sleeping up to {ODDS_INTERVAL_MIN} min (watching for manual scratches)...")
            while slept < sleep_total:
                time.sleep(min(slice_seconds, sleep_total - slept))
                slept += slice_seconds
                if regen_flag.exists():
                    try:
                        regen_flag.unlink()
                    except FileNotFoundError:
                        pass
                    logger.info("Manual scratch detected — regenerating dashboard")
                    generate_dashboard()
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
