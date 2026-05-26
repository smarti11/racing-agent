#!/usr/bin/env python3
"""Weekend Performance Report. Run from ~/Documents/racing-agent/"""
from db.database import get_conn
conn = get_conn()

print("=" * 60)
print("WEEKEND PERFORMANCE REPORT (Apr 17-19)")
print("=" * 60)

# Overall by date
rows = conn.execute(
    "SELECT r.race_date, COUNT(DISTINCT ap.race_id) as races, "
    "SUM(CASE WHEN ap.rank=1 AND ap.result='WIN' THEN 1 ELSE 0 END) as wins, "
    "SUM(CASE WHEN ap.rank=1 AND ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date >= '2026-04-17' AND ap.result IS NOT NULL "
    "GROUP BY r.race_date ORDER BY r.race_date"
).fetchall()

print("\nBy Date (Pick #1):")
total_r = total_w = total_wps = 0
for r in rows:
    wp = r[2]/r[1]*100 if r[1] else 0
    wpsp = r[3]/r[1]*100 if r[1] else 0
    print("  %s: %3d races | %3d wins (%.1f%%) | %3d WPS (%.1f%%)" % (r[0], r[1], r[2], wp, r[3], wpsp))
    total_r += r[1]
    total_w += r[2]
    total_wps += r[3]
if total_r:
    print("  TOTAL:      %3d races | %3d wins (%.1f%%) | %3d WPS (%.1f%%)" % (total_r, total_w, total_w/total_r*100, total_wps, total_wps/total_r*100))

# By confidence
rows2 = conn.execute(
    "SELECT ap.confidence, COUNT(*) as races, "
    "SUM(CASE WHEN ap.result='WIN' THEN 1 ELSE 0 END) as wins, "
    "SUM(CASE WHEN ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date >= '2026-04-17' AND ap.rank=1 AND ap.result IS NOT NULL "
    "GROUP BY ap.confidence"
).fetchall()

print("\nBy Confidence (Pick #1):")
for r in rows2:
    wp = r[2]/r[1]*100 if r[1] else 0
    wpsp = r[3]/r[1]*100 if r[1] else 0
    print("  %-8s: %3d races | %3d wins (%.1f%%) | %3d WPS (%.1f%%)" % (r[0], r[1], r[2], wp, r[3], wpsp))

# By track
rows3 = conn.execute(
    "SELECT r.track_name, COUNT(*) as races, "
    "SUM(CASE WHEN ap.result='WIN' THEN 1 ELSE 0 END) as wins, "
    "SUM(CASE WHEN ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "WHERE r.race_date >= '2026-04-17' AND ap.rank=1 AND ap.result IS NOT NULL "
    "GROUP BY r.track_name ORDER BY races DESC"
).fetchall()

print("\nBy Track (Pick #1):")
for r in rows3:
    wp = r[2]/r[1]*100 if r[1] else 0
    wpsp = r[3]/r[1]*100 if r[1] else 0
    print("  %-25s %3d races | %3d W (%.1f%%) | %3d WPS (%.1f%%)" % (r[0], r[1], r[2], wp, r[3], wpsp))

# ROI
roi = conn.execute(
    "SELECT COUNT(DISTINCT ap.race_id), "
    "SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "JOIN results res ON res.race_id=ap.race_id "
    "WHERE r.race_date >= '2026-04-17' AND ap.rank=1 AND ap.result IS NOT NULL"
).fetchone()

if roi[0]:
    wagered = roi[0] * 2.00
    returned = roi[1] or 0
    net = returned - wagered
    pct = net/wagered*100 if wagered else 0
    print("\nROI ($2 WIN on every Pick #1):")
    print("  Wagered:  $%.2f" % wagered)
    print("  Returned: $%.2f" % returned)
    print("  Net:      $%+.2f" % net)
    print("  ROI:      %+.1f%%" % pct)

# HIGH conf only ROI
hroi = conn.execute(
    "SELECT COUNT(DISTINCT ap.race_id), "
    "SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) "
    "FROM agent_picks ap JOIN races r ON r.id=ap.race_id "
    "JOIN results res ON res.race_id=ap.race_id "
    "WHERE r.race_date >= '2026-04-17' AND ap.rank=1 AND ap.confidence='HIGH' AND ap.result IS NOT NULL"
).fetchone()

if hroi[0]:
    wagered = hroi[0] * 2.00
    returned = hroi[1] or 0
    net = returned - wagered
    pct = net/wagered*100 if wagered else 0
    print("\nROI ($2 WIN on HIGH confidence only):")
    print("  Wagered:  $%.2f" % wagered)
    print("  Returned: $%.2f" % returned)
    print("  Net:      $%+.2f" % net)
    print("  ROI:      %+.1f%%" % pct)

# Scratches
scr = conn.execute(
    "SELECT COUNT(*) FROM entries e JOIN races r ON r.id=e.race_id "
    "WHERE r.race_date >= '2026-04-17' AND e.scratched=1"
).fetchone()[0]
print("\nScratches detected: %d" % scr)

# Chart times collected
ct = conn.execute(
    "SELECT COUNT(*) FROM chart_times WHERE race_date >= '2026-04-17'"
).fetchone()[0]
print("Chart times collected: %d" % ct)

conn.close()
print("\n" + "=" * 60)
