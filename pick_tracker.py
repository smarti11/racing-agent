#!/usr/bin/env python3
"""
Pick Tracker
=============
Log picks and results, track ROI over time.

Usage:
    python pick_tracker.py record                       # Full record
    python pick_tracker.py today                        # Today's picks
    python pick_tracker.py result KEE 3 6 WIN 8.40     # Log result (program#, result, payout)
    python pick_tracker.py result KEE 3 6 LOSS         # Log loss
"""

import sys
import sqlite3
from datetime import datetime, date
from pathlib import Path
from config.settings import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_race(conn, track_code, race_num):
    today = date.today().isoformat()
    row = conn.execute("""
        SELECT id, track_name FROM races
        WHERE track_code=? AND race_date=? AND race_num=?
    """, (track_code.upper(), today, int(race_num))).fetchone()
    return row


def log_result(track_code, race_num, winner_num, result_type, payout=0.0):
    """Log a race result and auto-grade any agent picks."""
    conn = get_conn()
    race = find_race(conn, track_code, race_num)

    if not race:
        print(f"Race not found: {track_code} R{race_num} today")
        conn.close()
        return

    # Find horse name
    entry = conn.execute("""
        SELECT horse_name FROM entries
        WHERE race_id=? AND program_num=?
    """, (race["id"], str(winner_num))).fetchone()
    horse_name = entry["horse_name"] if entry else f"Horse #{winner_num}"

    # Save result
    try:
        conn.execute("""
            INSERT OR REPLACE INTO results
            (race_id, winner_num, winner_name, posted_ts)
            VALUES (?,?,?,?)
        """, (race["id"], str(winner_num), horse_name, datetime.now().isoformat()))
    except Exception as e:
        print(f"Error saving result: {e}")
        conn.close()
        return

    # Save as pick with result
    conn.execute("""
        INSERT INTO picks
        (race_id, program_num, horse_name, bet_type, result, payout, created_ts)
        VALUES (?,?,?,'WIN',?,?,?)
    """, (race["id"], str(winner_num), horse_name,
          result_type.upper(), float(payout),
          datetime.now().isoformat()))

    conn.commit()
    conn.close()

    win_str = f" — ${payout:.2f} payout" if result_type.upper() == "WIN" and payout else ""
    print(f"Logged: {track_code} R{race_num} #{winner_num} {horse_name} → {result_type.upper()}{win_str}")


def show_record(days=None):
    conn = get_conn()
    where = f"AND p.created_ts >= date('now', '-{days} days')" if days else ""

    picks = conn.execute(f"""
        SELECT p.*, r.track_name, r.race_num, r.race_date
        FROM picks p
        JOIN races r ON r.id = p.race_id
        WHERE p.result IS NOT NULL {where}
        ORDER BY p.created_ts DESC
    """).fetchall()
    conn.close()

    if not picks:
        print("\nNo results logged yet.")
        print("Use: python pick_tracker.py result <TRACK> <RACE#> <HORSE#> <WIN|LOSS> [payout]")
        return

    total   = len(picks)
    wins    = sum(1 for p in picks if p["result"] == "WIN")
    places  = sum(1 for p in picks if p["result"] == "PLACE")
    shows   = sum(1 for p in picks if p["result"] == "SHOW")
    payouts = sum(p["payout"] or 0 for p in picks)
    losses  = total - wins - places - shows
    roi     = ((payouts - total) / total * 100) if total else 0

    print(f"\n{'='*55}")
    print(f"  PICK TRACKER RECORD")
    print(f"{'='*55}")
    print(f"  Total picks  : {total}")
    print(f"  Wins         : {wins} ({round(wins/total*100,1)}%)" if total else "  Wins: 0")
    print(f"  Place (2nd)  : {places}")
    print(f"  Show (3rd)   : {shows}")
    print(f"  Losses       : {losses}")
    print(f"  Total payout : ${payouts:.2f}")
    print(f"  ROI          : {roi:+.1f}%")
    print(f"{'='*55}")
    print(f"\n  {'DATE':<12} {'TRACK':<6} {'R#':<4} {'HORSE':<25} {'RESULT':<8} {'PAYOUT'}")
    print(f"  {'-'*65}")

    for p in picks[:25]:
        date_str   = str(p["race_date"])[:10] if p["race_date"] else "?"
        result_str = p["result"] or "?"
        payout_str = f"${p['payout']:.2f}" if p["payout"] else "—"
        result_color = "✓" if result_str == "WIN" else ("·" if result_str in ["PLACE","SHOW"] else "✗")
        print(f"  {date_str:<12} {str(p['track_name'])[:5]:<6} {str(p['race_num']):<4} {str(p['horse_name'])[:24]:<25} {result_color} {result_str:<7} {payout_str}")


def show_today():
    conn = get_conn()
    today = date.today().isoformat()

    picks = conn.execute("""
        SELECT p.*, r.track_name, r.race_num
        FROM picks p
        JOIN races r ON r.id = p.race_id
        WHERE r.race_date = ?
        ORDER BY r.track_name, r.race_num
    """, (today,)).fetchall()
    conn.close()

    if not picks:
        print(f"\nNo picks logged today ({today}).")
        return

    print(f"\nToday's picks ({today}):")
    for p in picks:
        result  = p["result"] or "PENDING"
        payout  = f" ${p['payout']:.2f}" if p["payout"] else ""
        marker  = "✓" if result == "WIN" else ("·" if result in ["PLACE","SHOW"] else ("✗" if result == "LOSS" else "?"))
        print(f"  {p['track_name']} R{p['race_num']} #{p['program_num']} {p['horse_name']} → {marker} {result}{payout}")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "record":
        show_record()
        return

    if args[0] == "today":
        show_today()
        return

    if args[0] == "result" and len(args) >= 5:
        track    = args[1]
        race_num = args[2]
        prog_num = args[3]
        result   = args[4]
        payout   = float(args[5]) if len(args) > 5 else 0.0
        log_result(track, race_num, prog_num, result, payout)
        return

    print("Usage:")
    print("  python pick_tracker.py record")
    print("  python pick_tracker.py today")
    print("  python pick_tracker.py result KEE 3 6 WIN 8.40")
    print("  python pick_tracker.py result KEE 3 6 LOSS")


if __name__ == "__main__":
    main()
