"""
Adds a new 'TRACK ROI BY CONFIDENCE' section to dashboard/builder.py
Run from ~/Documents/racing-agent directory.
"""

text = open("dashboard/builder.py").read()

# 1. Update import
old_import = "from db.database import get_todays_races, get_race_entries, get_pick_record, get_todays_results, get_agent_pick_stats, get_todays_agent_picks, get_roi_stats, get_optimized_roi_stats, get_stats_by_track, get_stats_by_field_size"
new_import = "from db.database import get_todays_races, get_race_entries, get_pick_record, get_todays_results, get_agent_pick_stats, get_todays_agent_picks, get_roi_stats, get_optimized_roi_stats, get_stats_by_track, get_stats_by_field_size, get_track_roi_by_confidence"

if old_import in text and "get_track_roi_by_confidence" not in text[:text.index("def cc")]:
    text = text.replace(old_import, new_import)
    print("Import updated")
else:
    print("Import already updated or marker missing")

# 2. Add data fetch
old_fetch = "    field_stats  = get_stats_by_field_size()"
new_fetch = """    field_stats  = get_stats_by_field_size()
    track_roi    = get_track_roi_by_confidence()"""

if old_fetch in text and "track_roi    = get_track_roi_by_confidence" not in text:
    text = text.replace(old_fetch, new_fetch)
    print("Fetch added")
else:
    print("Fetch already present")

# 3. Build HTML section and inject before roi_html marker
section = '''
    # Track ROI by Confidence section
    track_roi_html = ""
    if track_roi:
        rows_html = ""
        for track_name in sorted(track_roi.keys()):
            confs = track_roi[track_name]
            total_races = sum(c["races"] for c in confs.values())
            total_wagered = sum(c["wagered"] for c in confs.values())
            total_returned = sum(c["returned"] for c in confs.values())
            total_roi = ((total_returned - total_wagered) / total_wagered * 100) if total_wagered else 0
            t_color = "#00c896" if total_roi >= 0 else "#ff4d6d"
            cells_html = ""
            for conf in ["HIGH", "MEDIUM", "LOW"]:
                c = confs.get(conf)
                if c:
                    c_color = "#00c896" if c["roi_pct"] >= 0 else "#ff4d6d"
                    cells_html += f'<td style="padding:5px 8px;text-align:center;color:#4a6080;font-size:10px">{c["races"]}</td>'
                    cells_html += f'<td style="padding:5px 8px;text-align:center;color:{c_color};font-weight:700;font-size:10px">{c["win_pct"]}%</td>'
                    cells_html += f'<td style="padding:5px 8px;text-align:right;color:{c_color};font-weight:700;font-size:10px">{c["roi_pct"]:+.1f}%</td>'
                else:
                    cells_html += '<td colspan="3" style="padding:5px 8px;text-align:center;color:#2a3a5a;font-size:10px">-</td>'
            rows_html += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:5px 8px;color:#c8d8f0;font-weight:700;font-size:11px">{track_name}</td>'
                f'<td style="padding:5px 8px;text-align:center;color:#4a6080;font-size:10px">{total_races}</td>'
                f'<td style="padding:5px 8px;text-align:right;color:{t_color};font-weight:700;font-size:11px">{total_roi:+.1f}%</td>'
                + cells_html +
                f'</tr>'
            )
        track_roi_html = (
            '<div style="margin:0 0 20px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:16px 20px">'
            '<div style="font-size:11px;font-weight:700;color:#00c896;letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;border-bottom:0.5px solid #00c89633">'
            'TRACK ROI BY CONFIDENCE ($2 WIN on Pick #1)</div>'
            '<table style="width:100%;border-collapse:collapse;font-size:10px">'
            '<thead><tr style="background:#162038">'
            '<th rowspan="2" style="padding:6px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">TRACK</th>'
            '<th rowspan="2" style="padding:6px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">TOTAL RACES</th>'
            '<th rowspan="2" style="padding:6px 8px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">OVERALL ROI</th>'
            '<th colspan="3" style="padding:4px 8px;text-align:center;color:#00c896;font-size:9px;font-weight:700;border-left:1px solid #1e2d4a">HIGH CONF</th>'
            '<th colspan="3" style="padding:4px 8px;text-align:center;color:#ffd60a;font-size:9px;font-weight:700;border-left:1px solid #1e2d4a">MEDIUM CONF</th>'
            '<th colspan="3" style="padding:4px 8px;text-align:center;color:#ff8c42;font-size:9px;font-weight:700;border-left:1px solid #1e2d4a">LOW CONF</th>'
            '</tr><tr style="background:#162038">'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400;border-left:1px solid #1e2d4a">RACES</th>'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WIN%</th>'
            '<th style="padding:4px 6px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ROI</th>'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400;border-left:1px solid #1e2d4a">RACES</th>'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WIN%</th>'
            '<th style="padding:4px 6px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ROI</th>'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400;border-left:1px solid #1e2d4a">RACES</th>'
            '<th style="padding:4px 6px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WIN%</th>'
            '<th style="padding:4px 6px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ROI</th>'
            '</tr></thead><tbody>' + rows_html + '</tbody></table></div>'
        )

'''

marker = "    # ── End ROI Report"
if marker in text and 'track_roi_html = ""' not in text:
    text = text.replace(marker, section + marker)
    print("HTML section added")
else:
    print("Section already present")

# 4. Update the main div to include the new section
old_main = '<div class="main">{opt_html}{analysis_html}{roi_html}{race_html}</div>'
new_main = '<div class="main">{opt_html}{analysis_html}{track_roi_html}{roi_html}{race_html}</div>'
if old_main in text:
    text = text.replace(old_main, new_main)
    print("Main div updated")
else:
    print("Main div already updated or different")

open("dashboard/builder.py", "w").write(text)
print("\nSUCCESS - builder.py patched")
