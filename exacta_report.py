#!/usr/bin/env python3
"""Exacta Box Analysis — Top 3 Picks. Run from ~/Documents/racing-agent/"""
from db.database import get_conn
conn = get_conn()

print("=" * 60)
print("EXACTA BOX ANALYSIS — TOP 3 PICKS (Apr 17-19)")
print("$1 Box on Top 3 = 6 combos = $6.00/race")
print("=" * 60)

# Get all races with results and picks for the weekend
races = conn.execute(
    "SELECT DISTINCT r.id, r.track_name, r.race_num, r.race_date, "
    "res.winner_num, res.second_num, res.exacta_payout "
    "FROM races r "
    "JOIN results res ON res.race_id = r.id "
    "WHERE r.race_date >= '2026-04-17' AND r.race_date <= '2026-04-19' "
    "AND res.winner_num IS NOT NULL AND res.second_num IS NOT NULL "
    "ORDER BY r.race_date, r.track_name, r.race_num"
).fetchall()

total_races = 0
total_hits = 0
total_wagered = 0.0
total_returned = 0.0
hits_list = []

for race in races:
    race_id = race[0]
    track = race[1]
    rnum = race[2]
    rdate = race[3]
    winner = str(race[4])
    second = str(race[5])
    exacta_pay = race[6]  # This is the $1 or $2 exacta payout

    # Get top 3 picks for this race
    picks = conn.execute(
        "SELECT program_num, horse_name, rank FROM agent_picks "
        "WHERE race_id = ? AND rank <= 3 ORDER BY rank",
        (race_id,)
    ).fetchall()

    if len(picks) < 2:
        continue

    pick_nums = [str(p[0]) for p in picks]

    total_races += 1
    total_wagered += 6.00  # $1 box = 6 combos

    # Check if winner AND second are both in our top 3
    if winner in pick_nums and second in pick_nums:
        total_hits += 1
        # Exacta payout — need to determine base amount
        # Equibase reports exacta as $2 base typically
        if exacta_pay:
            # $1 box pays half the $2 exacta payout
            returned = exacta_pay / 2.0
            total_returned += returned
            pick_names = {str(p[0]): p[1] for p in picks}
            hits_list.append((rdate, track, rnum, winner, second, exacta_pay, returned))

print("\nRaces analyzed: %d" % total_races)
print("Exacta hits: %d" % total_hits)
if total_races:
    print("Hit rate: %.1f%%" % (total_hits / total_races * 100))
print("\nWagered: $%.2f ($6.00/race x %d races)" % (total_wagered, total_races))
print("Returned: $%.2f" % total_returned)
net = total_returned - total_wagered
print("Net P/L: $%+.2f" % net)
if total_wagered:
    print("ROI: %+.1f%%" % (net / total_wagered * 100))

print("\n" + "-" * 60)
print("EXACTA HITS:")
print("-" * 60)
for h in hits_list:
    print("  %s %-20s R%d: #%s-#%s  $2 Exacta=$%.2f  $1 return=$%.2f" % (
        h[0], h[1], h[2], h[3], h[4], h[5], h[6]))

# Also break down by confidence of Pick #1
print("\n" + "-" * 60)
print("EXACTA HITS BY PICK #1 CONFIDENCE:")
print("-" * 60)
for conf in ["HIGH", "MEDIUM", "LOW"]:
    conf_races = 0
    conf_hits = 0
    conf_wagered = 0.0
    conf_returned = 0.0
    for race in races:
        race_id = race[0]
        winner = str(race[4])
        second = str(race[5])
        exacta_pay = race[6]

        picks = conn.execute(
            "SELECT program_num, rank, confidence FROM agent_picks "
            "WHERE race_id = ? AND rank <= 3 ORDER BY rank",
            (race_id,)
        ).fetchall()
        if len(picks) < 2:
            continue

        # Check if Pick #1 is this confidence
        p1_conf = picks[0][2] if picks else None
        if p1_conf != conf:
            continue

        pick_nums = [str(p[0]) for p in picks]
        conf_races += 1
        conf_wagered += 6.00

        if winner in pick_nums and second in pick_nums:
            conf_hits += 1
            if exacta_pay:
                conf_returned += exacta_pay / 2.0

    if conf_races:
        conf_net = conf_returned - conf_wagered
        print("  %-8s: %3d races | %3d hits (%.1f%%) | Wagered $%.0f | Returned $%.0f | ROI %+.1f%%" % (
            conf, conf_races, conf_hits, conf_hits/conf_races*100,
            conf_wagered, conf_returned, conf_net/conf_wagered*100))

conn.close()
print("\n" + "=" * 60)
