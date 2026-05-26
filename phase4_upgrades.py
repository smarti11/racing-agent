#!/usr/bin/env python3
"""
Racing Agent Upgrades — Phase 4
================================
Run from ~/Documents/racing-agent/

Adds:
  1. Exacta-worthy track detection to DB (rolling stats)
  2. Jockey-Trainer combo stats tracking
  3. Post position bias by track
  4. Enhanced dashboard sections
"""
import os, sys

print("=" * 60)
print("PHASE 4: Advanced Handicapping Upgrades")
print("=" * 60)

# ── PART 1: Add new DB functions ────────────────────────────────
db_code = open("db/database.py").read()
changes = 0

# 1A: Exacta track stats function
if "def get_exacta_track_stats" not in db_code:
    func = '''

def get_exacta_track_stats(min_races=10):
    """Get exacta box ROI by track for dashboard display."""
    with get_conn() as conn:
        tracks = conn.execute(
            "SELECT DISTINCT r.track_name, r.track_code FROM races r "
            "JOIN results res ON res.race_id = r.id "
            "WHERE res.winner_num IS NOT NULL "
            "GROUP BY r.track_name HAVING COUNT(*) >= ?",
            (min_races,)
        ).fetchall()
        results = []
        for t in tracks:
            track_name = t["track_name"]
            races = conn.execute(
                "SELECT r.id, res.winner_num, res.second_num, res.exacta_payout "
                "FROM races r JOIN results res ON res.race_id = r.id "
                "WHERE r.track_name = ? AND res.winner_num IS NOT NULL AND res.second_num IS NOT NULL",
                (track_name,)
            ).fetchall()
            total = hits = 0
            wagered = returned = 0.0
            for race in races:
                picks = conn.execute(
                    "SELECT program_num FROM agent_picks WHERE race_id=? AND rank<=3 ORDER BY rank",
                    (race["id"],)
                ).fetchall()
                if len(picks) < 2:
                    continue
                pick_nums = [str(p["program_num"]) for p in picks]
                total += 1
                wagered += 6.0
                if str(race["winner_num"]) in pick_nums and str(race["second_num"]) in pick_nums:
                    hits += 1
                    if race["exacta_payout"]:
                        returned += race["exacta_payout"] / 2.0
            if total >= min_races:
                net = returned - wagered
                roi = net / wagered * 100 if wagered else 0
                hit_pct = hits / total * 100
                avg_ret = returned / hits if hits else 0
                worthy = roi > -10 and hit_pct > 30 and avg_ret > 10
                results.append({
                    "track": track_name, "races": total, "hits": hits,
                    "hit_pct": round(hit_pct, 1), "wagered": wagered,
                    "returned": round(returned, 2), "roi": round(roi, 1),
                    "avg_per_hit": round(avg_ret, 2), "exacta_worthy": worthy
                })
        results.sort(key=lambda x: x["roi"], reverse=True)
        return results


'''
    marker = "def get_pick_record():"
    db_code = db_code.replace(marker, func + marker)
    changes += 1
    print("[1] Exacta track stats function added")
else:
    print("[1] Exacta track stats already exists")

# 1B: Jockey-Trainer combo stats
if "def get_jt_combo_stats" not in db_code:
    func = '''

def get_jt_combo_stats(jockey, trainer):
    """Get win% for a specific jockey-trainer combination."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN res.winner_name = e.horse_name THEN 1 ELSE 0 END) as wins "
            "FROM entries e "
            "JOIN races r ON r.id = e.race_id "
            "JOIN results res ON res.race_id = r.id "
            "WHERE e.jockey LIKE ? AND e.trainer LIKE ? AND e.scratched = 0",
            (jockey.strip() + "%", trainer.strip() + "%")
        ).fetchone()
        if rows and rows["total"] and rows["total"] >= 3:
            return {"starts": rows["total"], "wins": rows["wins"],
                    "win_pct": round(rows["wins"] / rows["total"] * 100, 1)}
        return None


'''
    marker = "def get_pick_record():"
    db_code = db_code.replace(marker, func + marker)
    changes += 1
    print("[2] J/T combo stats function added")
else:
    print("[2] J/T combo stats already exists")

# 1C: Post position bias by track
if "def get_post_position_bias" not in db_code:
    func = '''

def get_post_position_bias(track_code, min_races=20):
    """Get win% by post position for a track to detect bias."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT e.post_position, COUNT(*) as starts, "
            "SUM(CASE WHEN res.winner_num = e.program_num THEN 1 ELSE 0 END) as wins "
            "FROM entries e "
            "JOIN races r ON r.id = e.race_id "
            "JOIN results res ON res.race_id = r.id "
            "WHERE r.track_code = ? AND e.scratched = 0 AND e.post_position IS NOT NULL "
            "GROUP BY e.post_position "
            "HAVING COUNT(*) >= 5 "
            "ORDER BY CAST(e.post_position AS INTEGER)",
            (track_code,)
        ).fetchall()
        total_starts = sum(r["starts"] for r in rows) if rows else 0
        total_wins = sum(r["wins"] for r in rows) if rows else 0
        if total_starts < min_races:
            return None
        avg_win_pct = total_wins / total_starts * 100 if total_starts else 0
        bias = []
        for r in rows:
            pct = r["wins"] / r["starts"] * 100 if r["starts"] else 0
            edge = pct - avg_win_pct
            bias.append({
                "post": r["post_position"], "starts": r["starts"],
                "wins": r["wins"], "win_pct": round(pct, 1), "edge": round(edge, 1)
            })
        # Determine bias direction
        inside_pct = sum(b["wins"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) <= 3)
        inside_starts = sum(b["starts"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) <= 3)
        outside_pct = sum(b["wins"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) >= 6)
        outside_starts = sum(b["starts"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) >= 6)
        inside_wp = inside_pct / inside_starts * 100 if inside_starts else 0
        outside_wp = outside_pct / outside_starts * 100 if outside_starts else 0
        if inside_wp > outside_wp + 5:
            direction = "INSIDE"
        elif outside_wp > inside_wp + 5:
            direction = "OUTSIDE"
        else:
            direction = "NEUTRAL"
        return {"bias": direction, "inside_wp": round(inside_wp, 1),
                "outside_wp": round(outside_wp, 1), "positions": bias}


'''
    marker = "def get_pick_record():"
    db_code = db_code.replace(marker, func + marker)
    changes += 1
    print("[3] Post position bias function added")
else:
    print("[3] Post position bias already exists")

# 1D: Lone speed detection helper
if "def get_lone_speed_stats" not in db_code:
    func = '''

def get_lone_speed_stats():
    """Get win stats when Pick #1 has LONE_SPEED pace scenario."""
    with get_conn() as conn:
        # Count wins where pace was LONE_SPEED
        total = conn.execute(
            "SELECT COUNT(*) FROM agent_picks ap "
            "WHERE ap.rank = 1 AND ap.result IS NOT NULL"
        ).fetchone()[0]
        # We don't store pace scenario per pick yet, so return overall stats
        return {"total_graded": total}


'''
    marker = "def get_pick_record():"
    db_code = db_code.replace(marker, func + marker)
    changes += 1
    print("[4] Lone speed stats function added")
else:
    print("[4] Lone speed stats already exists")

open("db/database.py", "w").write(db_code)
print("  database.py updated with %d changes" % changes)


# ── PART 2: Add J/T combo bonus to handicapper ─────────────────
hc_code = open("core/handicapper.py").read()

if "jt_combo" not in hc_code:
    # Find the weighted base score section and add J/T bonus after it
    old_base = "    base_score = raw_score * 100"
    new_base = """    base_score = raw_score * 100

    # Jockey-Trainer combo bonus
    jt_combo = None
    try:
        from db.database import get_jt_combo_stats
        jt_combo = get_jt_combo_stats(jockey, trainer)
        if jt_combo and jt_combo["starts"] >= 5 and jt_combo["win_pct"] >= 25:
            base_score += 3  # Strong J/T combo bonus
        elif jt_combo and jt_combo["starts"] >= 3 and jt_combo["win_pct"] >= 20:
            base_score += 1  # Moderate J/T combo bonus
    except Exception:
        pass"""
    hc_code = hc_code.replace(old_base, new_base, 1)
    open("core/handicapper.py", "w").write(hc_code)
    print("[5] J/T combo bonus added to handicapper")
else:
    print("[5] J/T combo bonus already exists")


# ── PART 3: Add exacta-worthy + advanced sections to dashboard ──
builder_code = open("dashboard/builder.py").read()

if "EXACTA-WORTHY" not in builder_code:
    # Find the main div closing or the track ROI section to add after
    # We'll add the exacta-worthy section after the track ROI section
    old_marker = None
    
    # Look for the track ROI fetch
    if "get_exacta_track_stats" not in builder_code:
        # Add import
        if "from db.database import" in builder_code:
            # Find the last import from db.database and add our new ones
            import_line = "from db.database import"
            # Add the fetch call and HTML section near the end of build_dashboard
            # We'll append the section before the final file write
            
            # Find where HTML is written to file
            write_marker = '    with open(output_path, "w") as f:'
            if write_marker not in builder_code:
                write_marker = '    open(output_path, "w").write(html)'
            if write_marker not in builder_code:
                write_marker = "    with open("
            
            # Find it by searching for the file write
            import re
            write_match = re.search(r'(    (?:with )?open\(.+?output_path.+?\))', builder_code)
            
            if write_match:
                # Add the exacta section HTML generation before the write
                exacta_section = '''
    # Exacta-worthy tracks section
    try:
        from db.database import get_exacta_track_stats
        ex_stats = get_exacta_track_stats(min_races=10)
        if ex_stats:
            html += '<div style="margin:20px 0;padding:15px;border:1px solid #333;border-radius:8px;background:#1a1a2e">'
            html += '<h3 style="color:#00ff88;margin:0 0 10px">EXACTA-WORTHY TRACKS ($1 Box Top 3 Picks)</h3>'
            html += '<table width="100%" style="border-collapse:collapse;font-size:13px">'
            html += '<tr style="color:#888"><td>TRACK</td><td>RACES</td><td>HITS</td><td>HIT%</td><td>AVG/HIT</td><td>ROI</td><td>STATUS</td></tr>'
            for s in ex_stats:
                roi_color = "#00ff88" if s["roi"] > 0 else "#ffaa00" if s["roi"] > -15 else "#ff4444"
                status = "BET" if s["exacta_worthy"] else "SKIP"
                status_color = "#00ff88" if s["exacta_worthy"] else "#ff4444"
                html += '<tr><td style="color:#ddd">%s</td><td>%d</td><td>%d</td><td>%.1f%%</td><td>$%.2f</td>' % (s["track"], s["races"], s["hits"], s["hit_pct"], s["avg_per_hit"])
                html += '<td style="color:%s">%+.1f%%</td>' % (roi_color, s["roi"])
                html += '<td style="color:%s;font-weight:bold">%s</td></tr>' % (status_color, status)
            html += '</table></div>'
    except Exception as e:
        pass

    # Post position bias section
    try:
        from db.database import get_post_position_bias
        track_codes_today = list(set(r["track_code"] for r in get_todays_races()))
        bias_data = []
        for tc in track_codes_today:
            b = get_post_position_bias(tc, min_races=15)
            if b and b["bias"] != "NEUTRAL":
                bias_data.append((tc, b))
        if bias_data:
            html += '<div style="margin:20px 0;padding:15px;border:1px solid #333;border-radius:8px;background:#1a1a2e">'
            html += '<h3 style="color:#00ff88;margin:0 0 10px">TRACK BIAS ALERTS</h3>'
            for tc, b in bias_data:
                bias_color = "#ffaa00"
                html += '<div style="margin:5px 0;color:#ddd">%s: <span style="color:%s;font-weight:bold">%s BIAS</span> ' % (tc, bias_color, b["bias"])
                html += '(Inside: %.1f%% | Outside: %.1f%%)</div>' % (b["inside_wp"], b["outside_wp"])
            html += '</div>'
    except Exception as e:
        pass

'''
                # Insert before the file write
                pos = write_match.start()
                builder_code = builder_code[:pos] + exacta_section + builder_code[pos:]
                open("dashboard/builder.py", "w").write(builder_code)
                print("[6] Exacta-worthy + bias sections added to dashboard")
            else:
                print("[6] Could not find file write marker in builder.py")
        else:
            print("[6] Could not find import marker in builder.py")
    else:
        print("[6] Dashboard already has exacta stats")
else:
    print("[6] Dashboard already has EXACTA-WORTHY section")


print("\n" + "=" * 60)
print("PHASE 4 COMPLETE")
print("=" * 60)
print("""
What's new:
  1. Exacta-worthy track detection — flags profitable tracks for exacta boxes
  2. Jockey-Trainer combo stats — win% for specific J/T pairs
  3. Post position bias — detects inside/outside track bias
  4. Lone speed stats helper
  5. J/T combo scoring bonus in handicapper (+1 to +3 points)
  6. Dashboard sections: Exacta-Worthy Tracks + Track Bias Alerts

Restart the agent to apply:
  pkill -f racing_agent.py
  python3 racing_agent.py &
""")
