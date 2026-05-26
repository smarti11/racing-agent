#!/usr/bin/env python3
"""Exacta Box ROI by Track. Run from ~/Documents/racing-agent/"""
from db.database import get_conn
conn = get_conn()

print("=" * 70)
print("EXACTA BOX ROI BY TRACK — TOP 3 PICKS ($1 Box = $6/race)")
print("Weekend Apr 17-19, 2026")
print("=" * 70)

tracks = conn.execute(
    "SELECT DISTINCT r.track_name FROM races r "
    "WHERE r.race_date >= '2026-04-17' AND r.race_date <= '2026-04-19' "
    "ORDER BY r.track_name"
).fetchall()

results = []
for track_row in tracks:
    track = track_row[0]
    races = conn.execute(
        "SELECT r.id, res.winner_num, res.second_num, res.exacta_payout "
        "FROM races r JOIN results res ON res.race_id = r.id "
        "WHERE r.race_date >= '2026-04-17' AND r.race_date <= '2026-04-19' "
        "AND r.track_name = ? AND res.winner_num IS NOT NULL AND res.second_num IS NOT NULL",
        (track,)
    ).fetchall()

    total = 0
    hits = 0
    wagered = 0.0
    returned = 0.0
    avg_pay = 0.0

    for race in races:
        race_id = race[0]
        winner = str(race[1])
        second = str(race[2])
        exacta_pay = race[3]

        picks = conn.execute(
            "SELECT program_num FROM agent_picks "
            "WHERE race_id = ? AND rank <= 3 ORDER BY rank",
            (race_id,)
        ).fetchall()
        if len(picks) < 2:
            continue

        pick_nums = [str(p[0]) for p in picks]
        total += 1
        wagered += 6.00

        if winner in pick_nums and second in pick_nums:
            hits += 1
            if exacta_pay:
                ret = exacta_pay / 2.0
                returned += ret

    if total > 0:
        net = returned - wagered
        roi = net / wagered * 100 if wagered else 0
        hit_pct = hits / total * 100
        avg_ret = returned / hits if hits else 0
        results.append((track, total, hits, hit_pct, wagered, returned, net, roi, avg_ret))

# Sort by ROI descending
results.sort(key=lambda x: x[7], reverse=True)

print("\n%-25s %5s %5s %6s %9s %9s %9s %7s %7s" % (
    "TRACK", "RACES", "HITS", "HIT%", "WAGERED", "RETURNED", "NET", "ROI", "AVG/HIT"))
print("-" * 95)
for r in results:
    roi_str = "%+.1f%%" % r[7]
    print("%-25s %5d %5d %5.1f%% %8.0f %9.2f %9.2f %7s %7.2f" % (
        r[0], r[1], r[2], r[3], r[4], r[5], r[6], roi_str, r[8]))

# Summary
profitable = [r for r in results if r[7] > 0]
breakeven = [r for r in results if r[7] > -15]
print("\n" + "-" * 70)
print("PROFITABLE tracks (positive ROI): %d of %d" % (len(profitable), len(results)))
for r in profitable:
    print("  %s: %+.1f%% ROI (%d hits / %d races, avg $%.2f/hit)" % (r[0], r[7], r[2], r[1], r[8]))

print("\nNEAR BREAK-EVEN tracks (ROI > -15%%): %d of %d" % (len(breakeven), len(results)))
for r in breakeven:
    if r[7] <= 0:
        print("  %s: %+.1f%% ROI (%d hits / %d races, avg $%.2f/hit)" % (r[0], r[7], r[2], r[1], r[8]))

conn.close()
print("\n" + "=" * 70)
