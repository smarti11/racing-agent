#!/usr/bin/env python3
"""
chart_verify.py — Validates a freshly-parsed chart in racing.db.

Usage:
    python3 chart_verify.py --track LRL --date 20260516

Prints a summary report showing what was parsed, useful as a sanity check
after running chart_parser.py.
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "Documents" / "racing-agent" / "db" / "racing.db"


def main() -> int:
    p = argparse.ArgumentParser(description="Verify chart_parser output")
    p.add_argument("--track", required=True, help="Track code (e.g., LRL)")
    p.add_argument("--date", required=True, help="Date YYYYMMDD")
    p.add_argument("--db", default=str(DB_PATH))
    args = p.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    print(f"\n{'='*70}")
    print(f"  CHART VERIFY — {args.track} {args.date}")
    print(f"{'='*70}\n")

    # 1. Race summary
    races = list(db.execute(
        "SELECT id, race_num, race_type, surface, distance_raw, "
        "       track_condition, off_time, purse "
        "FROM chart_races WHERE track_code=? AND race_date=? "
        "ORDER BY race_num",
        (args.track, args.date),
    ))
    if not races:
        print(f"  ⚠️  No races found for {args.track} {args.date}")
        print("  Run: python3 chart_parser.py --track {} --date {}".format(args.track, args.date))
        return 1

    print(f"  Races parsed: {len(races)}\n")
    print(f"  {'#':>3} {'Type':32s} {'Surf':5s} {'Dist':18s} {'Cond':5s} {'Off':6s} {'Purse':>9s}")
    print(f"  {'-'*3} {'-'*32} {'-'*5} {'-'*18} {'-'*5} {'-'*6} {'-'*9}")
    for r in races:
        rt = (r["race_type"] or "")[:32]
        purse = f"${r['purse']:,}" if r["purse"] else "-"
        print(f"  {r['race_num']:>3} {rt:32s} {r['surface'] or '-':5s} "
              f"{r['distance_raw'] or '-':18s} {r['track_condition'] or '-':5s} "
              f"{r['off_time'] or '-':6s} {purse:>9s}")

    # 2. Coverage stats
    print(f"\n  {'='*60}")
    print(f"  Coverage Stats")
    print(f"  {'='*60}")
    for r in races:
        n_horses = db.execute(
            "SELECT COUNT(*) FROM chart_horses WHERE chart_race_id=?", (r["id"],)
        ).fetchone()[0]
        n_trips = db.execute(
            "SELECT COUNT(*) FROM chart_trips WHERE chart_race_id=?", (r["id"],)
        ).fetchone()[0]
        n_payouts = db.execute(
            "SELECT COUNT(*) FROM chart_payouts WHERE chart_race_id=?", (r["id"],)
        ).fetchone()[0]
        frac = db.execute(
            "SELECT final_time FROM chart_fractions WHERE chart_race_id=?", (r["id"],)
        ).fetchone()
        coverage = f"{n_horses} horses, {n_trips} trips, {n_payouts} payouts"
        if frac and frac["final_time"]:
            coverage += f", final {frac['final_time']:.2f}"
        print(f"  R{r['race_num']:>2}: {coverage}")

    # 3. Winner check
    print(f"\n  {'='*60}")
    print(f"  Winners + WIN payouts")
    print(f"  {'='*60}")
    winners = list(db.execute("""
        SELECT cr.race_num, h.horse_name, h.jockey, h.odds,
               (SELECT payout FROM chart_payouts WHERE chart_race_id=cr.id
                AND bet_type='WIN' LIMIT 1) AS win_payout
        FROM chart_horses h JOIN chart_races cr ON h.chart_race_id=cr.id
        WHERE h.finish_position=1
          AND cr.track_code=? AND cr.race_date=?
        ORDER BY cr.race_num
    """, (args.track, args.date)))
    for w in winners:
        wp = f"${w['win_payout']:.2f}" if w["win_payout"] else "?"
        print(f"  R{w['race_num']:>2}: {w['horse_name']:25s} ({w['jockey']:18s}) "
              f"odds={w['odds']:5.2f}  WIN payout={wp}")

    # 4. Trip notes diagnostic
    print(f"\n  {'='*60}")
    print(f"  Trip Diagnostics (MAJOR/MINOR trouble)")
    print(f"  {'='*60}")
    troubled = list(db.execute("""
        SELECT cr.race_num, h.finish_position, t.horse_name, h.odds,
               t.trouble_score, t.pace_role, t.trip_notes_summary
        FROM chart_trips t
        JOIN chart_races cr ON t.chart_race_id=cr.id
        JOIN chart_horses h ON h.chart_race_id=cr.id AND h.horse_name=t.horse_name
        WHERE t.trouble_score IN ('MAJOR','MINOR')
          AND cr.track_code=? AND cr.race_date=?
        ORDER BY cr.race_num, h.finish_position
    """, (args.track, args.date)))
    for t in troubled[:25]:  # cap to 25 rows
        sym = "🔴" if t["trouble_score"] == "MAJOR" else "🟡"
        print(f"  {sym} R{t['race_num']:>2} #{t['finish_position']} {t['horse_name']:22s} "
              f"({t['odds']:>5.2f}) [{t['trouble_score']:5s}] pace={t['pace_role'] or '-'}")
        if t["trip_notes_summary"]:
            print(f"       └─ {t['trip_notes_summary'][:90]}")

    print(f"\n{'='*70}\n")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
