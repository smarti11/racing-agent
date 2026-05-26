#!/usr/bin/env python3
"""Daily Performance Report. Run from ~/Documents/racing-agent/"""
from db.database import get_conn
conn = get_conn()

date = "2026-04-25"
print("=" * 65)
print("DAILY PERFORMANCE REPORT — %s (Saturday)" % date)
print("=" * 65)

# Pick 1, 2, 3
total = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=1 AND ap.result IS NOT NULL", (date,)).fetchone()[0]
print("\nALL 3 PICKS:")
for rank in [1, 2, 3]:
    t = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=? AND ap.result IS NOT NULL", (date, rank)).fetchone()[0]
    w = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=? AND ap.result='WIN'", (date, rank)).fetchone()[0]
    wp = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=? AND ap.result IN ('WIN','PLACE','SHOW')", (date, rank)).fetchone()[0]
    if t:
        print("  Pick #%d: %d races | %d W (%.1f%%) | %d WPS (%.1f%%)" % (rank, t, w, w/t*100, wp, wp/t*100))

print("\nBY CONFIDENCE (Pick #1):")
for conf in ["HIGH", "MEDIUM", "LOW"]:
    ct = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=1 AND ap.result IS NOT NULL AND ap.confidence=?", (date, conf)).fetchone()[0]
    cw = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=1 AND ap.result='WIN' AND ap.confidence=?", (date, conf)).fetchone()[0]
    cwps = conn.execute("SELECT COUNT(*) FROM agent_picks ap JOIN races r ON r.id=ap.race_id WHERE r.race_date=? AND ap.rank=1 AND ap.result IN ('WIN','PLACE','SHOW') AND ap.confidence=?", (date, conf)).fetchone()[0]
    if ct:
        print("  %-8s: %3d races | %3d W (%.1f%%) | %3d WPS (%.1f%%)" % (conf, ct, cw, cw/ct*100, cwps, cwps/ct*100))

print("\nBY TRACK (Pick #1):")
tracks = conn.execute(
    "SELECT r.track_name, COUNT(*) as races, "
    "SUM(CASE WHEN ap.result='WIN' THEN 1 ELSE 0 END) as wins, "
    "SUM(CASE WHEN ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date=? AND ap.rank=1 AND ap.result IS NOT NULL "
    "GROUP BY r.track_name ORDER BY races DESC", (date,)
).fetchall()
for t in tracks:
    print("  %-25s %2d races | %2d W (%4.0f%%) | %2d WPS (%4.0f%%)" % (t[0], t[1], t[2], t[2]/t[1]*100, t[3], t[3]/t[1]*100))

# ROI
print("\nROI:")
roi = conn.execute(
    "SELECT COUNT(DISTINCT ap.race_id), "
    "SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) "
    "FROM agent_picks ap JOIN results res ON res.race_id=ap.race_id "
    "JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date=? AND ap.rank=1 AND ap.result IS NOT NULL", (date,)
).fetchone()
if roi[0]:
    wagered = roi[0] * 2.0
    returned = roi[1] or 0
    print("  All Pick #1:  $%.0f wagered, $%.0f returned, %+.1f%%" % (wagered, returned, (returned-wagered)/wagered*100))

hroi = conn.execute(
    "SELECT COUNT(DISTINCT ap.race_id), "
    "SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) "
    "FROM agent_picks ap JOIN results res ON res.race_id=ap.race_id "
    "JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date=? AND ap.rank=1 AND ap.confidence='HIGH' AND ap.result IS NOT NULL", (date,)
).fetchone()
if hroi[0]:
    wagered = hroi[0] * 2.0
    returned = hroi[1] or 0
    print("  HIGH only:    $%.0f wagered, $%.0f returned, %+.1f%%" % (wagered, returned, (returned-wagered)/wagered*100))

# Exacta
print("\nEXACTA BOX (Top 3 Picks, $1 box = $6/race):")
races = conn.execute(
    "SELECT r.id, r.track_name, r.race_num, res.winner_num, res.second_num, res.exacta_payout "
    "FROM races r JOIN results res ON res.race_id=r.id "
    "WHERE r.race_date=? AND res.winner_num IS NOT NULL AND res.second_num IS NOT NULL", (date,)
).fetchall()
ex_total = ex_hits = 0
ex_wagered = ex_returned = 0.0
ex_hit_list = []
for race in races:
    picks = conn.execute("SELECT program_num FROM agent_picks WHERE race_id=? AND rank<=3 ORDER BY rank", (race[0],)).fetchall()
    if len(picks) < 2:
        continue
    pick_nums = [str(p[0]) for p in picks]
    ex_total += 1
    ex_wagered += 6.0
    if str(race[3]) in pick_nums and str(race[4]) in pick_nums:
        ex_hits += 1
        if race[5]:
            ret = race[5] / 2.0
            ex_returned += ret
            ex_hit_list.append((race[1], race[2], race[3], race[4], race[5], ret))
if ex_total:
    print("  %d races | %d hits (%.1f%%) | $%.0f wagered | $%.0f returned | %+.1f%% ROI" % (
        ex_total, ex_hits, ex_hits/ex_total*100, ex_wagered, ex_returned, (ex_returned-ex_wagered)/ex_wagered*100))
    for h in ex_hit_list:
        print("    %s R%d: #%s-#%s $2 exacta=$%.2f, $1 return=$%.2f" % (h[0], h[1], h[2], h[3], h[4], h[5]))

# Daily Double
print("\nDAILY DOUBLE (Pick #1 consecutive pairs):")
dd_tracks = conn.execute("SELECT DISTINCT r.track_name, r.track_code FROM races r WHERE r.race_date=?", (date,)).fetchall()
dd_total = dd_hits = 0
dd_wagered = dd_returned = 0.0
dd_hit_list = []
for td in dd_tracks:
    trs = conn.execute(
        "SELECT r.id, r.race_num, res.winner_num, res.winner_win_payout "
        "FROM races r JOIN results res ON res.race_id=r.id "
        "WHERE r.track_code=? AND r.race_date=? AND res.winner_num IS NOT NULL "
        "ORDER BY r.race_num", (td[1], date)
    ).fetchall()
    for i in range(len(trs)-1):
        r1, r2 = trs[i], trs[i+1]
        if r2[1] != r1[1] + 1:
            continue
        p1 = conn.execute("SELECT result FROM agent_picks WHERE race_id=? AND rank=1", (r1[0],)).fetchone()
        p2 = conn.execute("SELECT result FROM agent_picks WHERE race_id=? AND rank=1", (r2[0],)).fetchone()
        if not p1 or not p2:
            continue
        dd_total += 1
        dd_wagered += 1.0
        if p1[0] == "WIN" and p2[0] == "WIN":
            dd_hits += 1
            w1, w2 = r1[3] or 0, r2[3] or 0
            if w1 > 0 and w2 > 0:
                est = round((w1/2)*(w2/2)*2*1.10, 2)
                dd_returned += est
                dd_hit_list.append((td[0], r1[1], r2[1], w1, w2, est))
if dd_total:
    print("  %d DDs | %d hits (%.1f%%) | $%.0f wagered | $%.0f returned | %+.1f%% ROI" % (
        dd_total, dd_hits, dd_hits/dd_total*100, dd_wagered, dd_returned, (dd_returned-dd_wagered)/dd_wagered*100))
    for h in dd_hit_list:
        print("    %s R%d-R%d: $%.2f + $%.2f = est DD $%.2f" % (h[0], h[1], h[2], h[3], h[4], h[5]))

# Any top 3 won
any_won = conn.execute(
    "SELECT COUNT(DISTINCT ap.race_id) FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date=? AND ap.rank<=3 AND ap.result='WIN'", (date,)
).fetchone()[0]
if total:
    print("\nANY TOP 3 PICK WON: %d of %d races (%.1f%%)" % (any_won, total, any_won/total*100))

# Scratches
scr = conn.execute(
    "SELECT COUNT(*) FROM entries e JOIN races r ON r.id=e.race_id "
    "WHERE r.race_date=? AND e.scratched=1", (date,)
).fetchone()[0]
print("SCRATCHES DETECTED: %d" % scr)

conn.close()
print("\n" + "=" * 65)
