#!/usr/bin/env python3
"""Add exacta-worthy and bias sections to dashboard. Run from ~/Documents/racing-agent/"""

code = open("dashboard/builder.py").read()

if "EXACTA-WORTHY" in code:
    print("Already added")
    exit()

marker = '    Path(DASHBOARD_OUTPUT).write_text(html)'
if marker not in code:
    print("ERROR: Could not find write marker")
    exit(1)

section = r'''
    # ── EXACTA-WORTHY TRACKS ──────────────────────────────────────
    try:
        from db.database import get_exacta_track_stats
        ex_stats = get_exacta_track_stats(min_races=10)
        if ex_stats:
            html += '<div style="margin:20px 0;padding:15px;border:1px solid #333;border-radius:8px;background:#1a1a2e">'
            html += '<h3 style="color:#00ff88;margin:0 0 10px">EXACTA-WORTHY TRACKS ($1 Box Top 3 Picks)</h3>'
            html += '<table width="100%%" style="border-collapse:collapse;font-size:13px">'
            html += '<tr style="color:#888"><td>TRACK</td><td>RACES</td><td>HITS</td><td>HIT%%</td><td>AVG/HIT</td><td>ROI</td><td>STATUS</td></tr>'
            for s in ex_stats:
                roi_color = "#00ff88" if s["roi"] > 0 else "#ffaa00" if s["roi"] > -15 else "#ff4444"
                status = "BET" if s["exacta_worthy"] else "SKIP"
                status_color = "#00ff88" if s["exacta_worthy"] else "#ff4444"
                html += '<tr>'
                html += '<td style="color:#ddd">%s</td>' % s["track"]
                html += '<td>%d</td>' % s["races"]
                html += '<td>%d</td>' % s["hits"]
                html += '<td>%.1f%%%%</td>' % s["hit_pct"]
                html += '<td>$%.2f</td>' % s["avg_per_hit"]
                html += '<td style="color:%s">%+.1f%%%%</td>' % (roi_color, s["roi"])
                html += '<td style="color:%s;font-weight:bold">%s</td>' % (status_color, status)
                html += '</tr>'
            html += '</table></div>'
    except Exception:
        pass

    # ── TRACK BIAS ALERTS ─────────────────────────────────────────
    try:
        from db.database import get_post_position_bias, get_todays_races
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
                html += '<div style="margin:5px 0;color:#ddd">'
                html += '%s: <span style="color:#ffaa00;font-weight:bold">%s BIAS</span> ' % (tc, b["bias"])
                html += '(Inside: %.1f%%%% | Outside: %.1f%%%%)</div>' % (b["inside_wp"], b["outside_wp"])
            html += '</div>'
    except Exception:
        pass

'''

code = code.replace(marker, section + marker)
open("dashboard/builder.py", "w").write(code)
print("Dashboard sections added: EXACTA-WORTHY + TRACK BIAS")
