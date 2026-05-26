#!/usr/bin/env python3
"""
Daily Double What-If Analysis — Pick #1
Run from ~/Documents/racing-agent/

Checks every consecutive race pair at each track to see if Pick #1
won both legs. Estimates DD payout from win prices.

DD payout approximation: (win1/2) * (win2/2) * 2
This is conservative — actual DD pools often pay MORE than the
parlay of two win bets because the DD pool has less public money.
"""
from db.database import get_conn
conn = get_conn()

print("=" * 70)
print("DAILY DOUBLE WHAT-IF ANALYSIS — PICK #1 (Apr 12-24)")
print("$1 Daily Double on Pick #1 in consecutive races")
print("=" * 70)

# Get all tracks and dates
track_dates = conn.execute(
    "SELECT DISTINCT r.track_name, r.track_code, r.race_date "
    "FROM races r WHERE r.race_date >= '2026-04-12' AND r.race_date <= '2026-04-19' "
    "ORDER BY r.race_date, r.track_name"
).fetchall()

total_dds = 0       # total DD opportunities
total_hits = 0      # both legs won
total_wagered = 0.0
total_returned = 0.0
hits_list = []
by_track = {}

for td in track_dates:
    track_name = td["track_name"]
    track_code = td["track_code"]
    race_date = td["race_date"]

    # Get all races for this track/date with results, ordered by race number
    races = conn.execute(
        "SELECT r.id, r.race_num, res.winner_num, res.winner_win_payout "
        "FROM races r JOIN results res ON res.race_id = r.id "
        "WHERE r.track_code = ? AND r.race_date = ? "
        "AND res.winner_num IS NOT NULL "
        "ORDER BY r.race_num",
        (track_code, race_date)
    ).fetchall()

    if len(races) < 2:
        continue

    # Check each consecutive pair
    for i in range(len(races) - 1):
        r1 = races[i]
        r2 = races[i + 1]

        # Only count if they're actually consecutive race numbers
        if r2["race_num"] != r1["race_num"] + 1:
            continue

        # Get Pick #1 for each race
        p1 = conn.execute(
            "SELECT program_num, horse_name, confidence, result "
            "FROM agent_picks WHERE race_id = ? AND rank = 1",
            (r1["id"],)
        ).fetchone()
        p2 = conn.execute(
            "SELECT program_num, horse_name, confidence, result "
            "FROM agent_picks WHERE race_id = ? AND rank = 1",
            (r2["id"],)
        ).fetchone()

        if not p1 or not p2:
            continue

        total_dds += 1
        total_wagered += 1.00  # $1 DD

        leg1_won = p1["result"] == "WIN"
        leg2_won = p2["result"] == "WIN"

        if leg1_won and leg2_won:
            total_hits += 1
            # Estimate DD payout: (win1/2) * (win2/2) * 2
            w1 = r1["winner_win_payout"] or 0
            w2 = r2["winner_win_payout"] or 0
            if w1 > 0 and w2 > 0:
                est_dd = (w1 / 2.0) * (w2 / 2.0) * 2.0
                # DD pools often pay 10-20% more than parlay
                est_dd = round(est_dd * 1.10, 2)  # conservative 10% premium
            else:
                est_dd = 0
            total_returned += est_dd

            # Track confidence of both legs
            conf = "%s/%s" % (p1["confidence"], p2["confidence"])
            hits_list.append((race_date, track_name, r1["race_num"], r2["race_num"],
                             p1["horse_name"], p2["horse_name"], w1, w2, est_dd, conf))

        # Track by track
        if track_name not in by_track:
            by_track[track_name] = {"dds": 0, "hits": 0, "wagered": 0, "returned": 0}
        by_track[track_name]["dds"] += 1
        by_track[track_name]["wagered"] += 1.0
        if leg1_won and leg2_won:
            by_track[track_name]["hits"] += 1
            w1 = r1["winner_win_payout"] or 0
            w2 = r2["winner_win_payout"] or 0
            if w1 > 0 and w2 > 0:
                est_dd = round((w1 / 2.0) * (w2 / 2.0) * 2.0 * 1.10, 2)
                by_track[track_name]["returned"] += est_dd

print("\nTotal DD opportunities: %d" % total_dds)
print("DD hits (both legs won): %d" % total_hits)
if total_dds:
    print("Hit rate: %.1f%%" % (total_hits / total_dds * 100))
print("\nWagered: $%.2f ($1/DD x %d)" % (total_wagered, total_dds))
print("Est. Returned: $%.2f" % total_returned)
net = total_returned - total_wagered
print("Est. Net P/L: $%+.2f" % net)
if total_wagered:
    print("Est. ROI: %+.1f%%" % (net / total_wagered * 100))
if total_hits:
    print("Avg DD payout: $%.2f" % (total_returned / total_hits))

# DD hits detail
print("\n" + "-" * 70)
print("DD HITS:")
print("-" * 70)
for h in hits_list:
    print("  %s %-20s R%d-R%d: %s ($%.2f) + %s ($%.2f) = DD ~$%.2f [%s]" % (
        h[0], h[1], h[2], h[3], h[4], h[6], h[5], h[7], h[8], h[9]))

# By confidence combo
print("\n" + "-" * 70)
print("DD HITS BY CONFIDENCE COMBO:")
print("-" * 70)
conf_combos = {}
for h in hits_list:
    c = h[9]
    if c not in conf_combos:
        conf_combos[c] = {"hits": 0, "returned": 0}
    conf_combos[c]["hits"] += 1
    conf_combos[c]["returned"] += h[8]
for c in sorted(conf_combos.keys()):
    d = conf_combos[c]
    print("  %-12s: %3d hits, est. returned $%.2f, avg $%.2f/hit" % (
        c, d["hits"], d["returned"], d["returned"] / d["hits"]))

# By track
print("\n" + "-" * 70)
print("DD PERFORMANCE BY TRACK:")
print("-" * 70)
track_results = []
for t, d in by_track.items():
    if d["dds"] >= 3:
        net_t = d["returned"] - d["wagered"]
        roi_t = net_t / d["wagered"] * 100 if d["wagered"] else 0
        hit_pct = d["hits"] / d["dds"] * 100
        avg_pay = d["returned"] / d["hits"] if d["hits"] else 0
        track_results.append((t, d["dds"], d["hits"], hit_pct, d["wagered"], d["returned"], net_t, roi_t, avg_pay))
track_results.sort(key=lambda x: x[7], reverse=True)

print("%-25s %4s %4s %6s %8s %9s %9s %7s %7s" % (
    "TRACK", "DDs", "HITS", "HIT%", "WAGER", "RETURN", "NET", "ROI", "AVG/HIT"))
for r in track_results:
    roi_str = "%+.0f%%" % r[7]
    print("%-25s %4d %4d %5.1f%% %7.0f %9.2f %9.2f %7s %7.2f" % (
        r[0], r[1], r[2], r[3], r[4], r[5], r[6], roi_str, r[8]))

# Recommendation
print("\n" + "-" * 70)
print("PROFITABLE DD TRACKS (positive ROI):")
profitable = [r for r in track_results if r[7] > 0]
for r in profitable:
    print("  %s: %+.0f%% ROI (%d hits / %d DDs, avg $%.2f/hit)" % (r[0], r[7], r[2], r[1], r[8]))

# One leg hit analysis
print("\n" + "-" * 70)
print("SINGLE LEG HIT RATE:")
print("-" * 70)
leg1_wins = conn.execute(
    "SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date >= '2026-04-12' AND ap.rank=1 AND ap.result='WIN'"
).fetchone()[0]
total_picks = conn.execute(
    "SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date >= '2026-04-12' AND ap.rank=1 AND ap.result IS NOT NULL"
).fetchone()[0]
if total_picks:
    single_pct = leg1_wins / total_picks * 100
    # Expected DD hit rate = single_pct^2 / 100
    expected_dd = (single_pct * single_pct) / 100
    actual_dd = total_hits / total_dds * 100 if total_dds else 0
    print("  Single leg win%%: %.1f%%" % single_pct)
    print("  Expected DD hit%% (independent): %.1f%%" % expected_dd)
    print("  Actual DD hit%%: %.1f%%" % actual_dd)
    if actual_dd > expected_dd:
        print("  Agent picks are POSITIVELY CORRELATED across consecutive races")
    else:
        print("  Agent picks are independent or slightly negatively correlated")

conn.close()
print("\n" + "=" * 70)
