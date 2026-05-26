#!/usr/bin/env python3
"""Add Daily Double tracking to dashboard. Run from ~/Documents/racing-agent/"""

# Step 1: Add DD stats function to database.py
db_code = open("db/database.py").read()

if "def get_dd_track_stats" not in db_code:
    func = '''

def get_dd_track_stats(min_dds=5):
    """Get Daily Double ROI by track for dashboard."""
    with get_conn() as conn:
        track_dates = conn.execute(
            "SELECT DISTINCT r.track_name, r.track_code, r.race_date "
            "FROM races r JOIN results res ON res.race_id = r.id "
            "WHERE res.winner_num IS NOT NULL "
            "ORDER BY r.race_date"
        ).fetchall()

        by_track = {}
        for td in track_dates:
            tn = td["track_name"]
            tc = td["track_code"]
            rd = td["race_date"]
            races = conn.execute(
                "SELECT r.id, r.race_num, res.winner_num, res.winner_win_payout "
                "FROM races r JOIN results res ON res.race_id = r.id "
                "WHERE r.track_code=? AND r.race_date=? AND res.winner_num IS NOT NULL "
                "ORDER BY r.race_num", (tc, rd)
            ).fetchall()
            if len(races) < 2:
                continue
            for i in range(len(races) - 1):
                r1, r2 = races[i], races[i + 1]
                if r2["race_num"] != r1["race_num"] + 1:
                    continue
                p1 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r1["id"],)
                ).fetchone()
                p2 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r2["id"],)
                ).fetchone()
                if not p1 or not p2:
                    continue
                if tn not in by_track:
                    by_track[tn] = {"dds": 0, "hits": 0, "wagered": 0, "returned": 0}
                by_track[tn]["dds"] += 1
                by_track[tn]["wagered"] += 1.0
                if p1["result"] == "WIN" and p2["result"] == "WIN":
                    by_track[tn]["hits"] += 1
                    w1 = r1["winner_win_payout"] or 0
                    w2 = r2["winner_win_payout"] or 0
                    if w1 > 0 and w2 > 0:
                        est = round((w1/2) * (w2/2) * 2 * 1.10, 2)
                        by_track[tn]["returned"] += est

        results = []
        for t, d in by_track.items():
            if d["dds"] >= min_dds:
                net = d["returned"] - d["wagered"]
                roi = net / d["wagered"] * 100 if d["wagered"] else 0
                hit_pct = d["hits"] / d["dds"] * 100
                avg_ret = d["returned"] / d["hits"] if d["hits"] else 0
                worthy = roi > 0
                results.append({
                    "track": t, "dds": d["dds"], "hits": d["hits"],
                    "hit_pct": round(hit_pct, 1), "wagered": d["wagered"],
                    "returned": round(d["returned"], 2), "roi": round(roi, 1),
                    "avg_per_hit": round(avg_ret, 2), "dd_worthy": worthy
                })
        results.sort(key=lambda x: x["roi"], reverse=True)
        return results


'''
    marker = "def get_pick_record():"
    db_code = db_code.replace(marker, func + marker)
    open("db/database.py", "w").write(db_code)
    print("[1] DD track stats function added to database.py")
else:
    print("[1] DD track stats already exists")


# Step 2: Add DD section to dashboard builder
builder_code = open("dashboard/builder.py").read()

if "DAILY DOUBLE" not in builder_code:
    marker = '    Path(DASHBOARD_OUTPUT).write_text(html)'
    if marker not in marker:
        pass  # will check below

    dd_section = r'''
    # ── DAILY DOUBLE PERFORMANCE BY TRACK ─────────────────────────
    try:
        from db.database import get_dd_track_stats
        dd_stats = get_dd_track_stats(min_dds=5)
        if dd_stats:
            html += '<div style="margin:20px 0;padding:15px;border:1px solid #333;border-radius:8px;background:#1a1a2e">'
            html += '<h3 style="color:#00ff88;margin:0 0 10px">DAILY DOUBLE PERFORMANCE ($1 DD on Pick #1, Rolling)</h3>'
            total_w = sum(s["wagered"] for s in dd_stats)
            total_r = sum(s["returned"] for s in dd_stats)
            total_h = sum(s["hits"] for s in dd_stats)
            total_d = sum(s["dds"] for s in dd_stats)
            total_roi = (total_r - total_w) / total_w * 100 if total_w else 0
            roi_color = "#00ff88" if total_roi > 0 else "#ff4444"
            html += '<div style="margin-bottom:10px;color:#ddd">'
            html += 'Total: %d DDs | %d hits (%.1f%%%%) | ' % (total_d, total_h, total_h/total_d*100 if total_d else 0)
            html += 'Wagered $%.0f | Returned $%.0f | ' % (total_w, total_r)
            html += '<span style="color:%s;font-weight:bold">ROI %+.1f%%%%</span></div>' % (roi_color, total_roi)
            html += '<table width="100%%" style="border-collapse:collapse;font-size:13px">'
            html += '<tr style="color:#888"><td>TRACK</td><td>DDs</td><td>HITS</td><td>HIT%%</td><td>AVG/HIT</td><td>ROI</td><td>STATUS</td></tr>'
            for s in dd_stats:
                roi_c = "#00ff88" if s["roi"] > 0 else "#ffaa00" if s["roi"] > -20 else "#ff4444"
                status = "BET" if s["dd_worthy"] else "SKIP"
                status_c = "#00ff88" if s["dd_worthy"] else "#ff4444"
                html += '<tr>'
                html += '<td style="color:#ddd">%s</td>' % s["track"]
                html += '<td>%d</td>' % s["dds"]
                html += '<td>%d</td>' % s["hits"]
                html += '<td>%.1f%%%%</td>' % s["hit_pct"]
                html += '<td>$%.2f</td>' % s["avg_per_hit"]
                html += '<td style="color:%s">%+.1f%%%%</td>' % (roi_c, s["roi"])
                html += '<td style="color:%s;font-weight:bold">%s</td>' % (status_c, status)
                html += '</tr>'
            html += '</table></div>'
    except Exception:
        pass

'''

    if marker in builder_code:
        builder_code = builder_code.replace(marker, dd_section + marker)
        open("dashboard/builder.py", "w").write(builder_code)
        print("[2] Daily Double section added to dashboard")
    else:
        print("[2] ERROR: Could not find write marker in builder.py")
else:
    print("[2] Daily Double section already exists")


print("\nDone! Restart the agent to see DD tracking on the dashboard:")
print("  pkill -f racing_agent.py")
print("  python3 racing_agent.py &")
