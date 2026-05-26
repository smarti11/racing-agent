"""Jockey leaderboard and ML accuracy analytics for dashboard."""


def get_jockey_leaderboard(days_back=30, min_starts=1, top_n=20):
    try:
        from db.database import get_conn
        import datetime as _dt
        cutoff = '2026-05-23'  # Clean baseline start date
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT e.jockey,
                    COUNT(*) AS starts,
                    SUM(CASE WHEN e.horse_name = res.winner_name
                             OR res.winner_name LIKE e.horse_name||'%'
                             THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN e.horse_name = res.second_name
                             OR res.second_name LIKE e.horse_name||'%'
                             THEN 1 ELSE 0 END) AS places,
                    SUM(CASE WHEN e.horse_name = res.third_name
                             OR res.third_name LIKE e.horse_name||'%'
                             THEN 1 ELSE 0 END) AS shows
                FROM entries e
                JOIN races r ON r.id = e.race_id
                JOIN results res ON res.race_id = r.id
                WHERE e.jockey IS NOT NULL AND e.jockey != ''
                  AND r.race_date >= ?
                GROUP BY e.jockey
                HAVING starts >= ?
                ORDER BY wins DESC
                LIMIT ?
            """, (cutoff, min_starts, top_n)).fetchall()
            out = []
            for row in rows:
                r = dict(row)
                s = r['starts'] or 1
                r['win_pct'] = round(100.0 * r['wins'] / s, 1)
                r['itm_pct'] = round(100.0 * (r['wins'] + r['places'] + r['shows']) / s, 1)
                out.append(r)
            return out
    except Exception:
        return []


def get_jockey_tracks(days_back=30, min_starts=1):
    """Get track breakdown for each jockey."""
    try:
        from db.database import get_conn
        import datetime as _dt
        cutoff = '2026-05-23'  # Clean baseline start date
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT e.jockey,
                    r.track_name,
                    COUNT(*) AS starts,
                    SUM(CASE WHEN e.horse_name = res.winner_name
                             OR res.winner_name LIKE e.horse_name||'%'
                             THEN 1 ELSE 0 END) AS wins,
                    ROUND(100.0*SUM(CASE WHEN e.horse_name = res.winner_name
                             OR res.winner_name LIKE e.horse_name||'%'
                             THEN 1 ELSE 0 END)/COUNT(*),1) AS win_pct
                FROM entries e
                JOIN races r ON r.id = e.race_id
                JOIN results res ON res.race_id = r.id
                WHERE e.jockey IS NOT NULL AND e.jockey != ''
                  AND r.race_date >= ?
                GROUP BY e.jockey, r.track_name
                HAVING starts >= ?
                ORDER BY e.jockey, wins DESC
            """, (cutoff, min_starts)).fetchall()
            # Group by jockey
            track_map = {}
            for row in rows:
                r = dict(row)
                j = r['jockey']
                if j not in track_map:
                    track_map[j] = []
                track_map[j].append(r)
            return track_map
    except Exception:
        return {}


def get_ml_accuracy():
    try:
        from db.database import get_conn
        with get_conn() as conn:
            ag = conn.execute("""
                SELECT COUNT(*) AS races,
                       SUM(CASE WHEN ap.finish_position=1 THEN 1 ELSE 0 END) AS wins
                FROM agent_picks ap
                WHERE ap.rank=1 AND ap.finish_position IS NOT NULL
                  AND ap.data_quality IN ('OK','UNVERIFIED')
            """).fetchone()
            ml = conn.execute("""
                WITH parsed AS (
                    SELECT e.race_id, e.program_num,
                        CASE WHEN e.morning_line LIKE '%/%' THEN
                            CAST(SUBSTR(e.morning_line,1,INSTR(e.morning_line,'/')-1) AS REAL) /
                            NULLIF(CAST(SUBSTR(e.morning_line,INSTR(e.morning_line,'/')+1) AS REAL),0)
                        ELSE CAST(e.morning_line AS REAL) END AS odds_dec,
                        ROW_NUMBER() OVER (PARTITION BY e.race_id ORDER BY
                            CASE WHEN e.morning_line LIKE '%/%' THEN
                                CAST(SUBSTR(e.morning_line,1,INSTR(e.morning_line,'/')-1) AS REAL) /
                                NULLIF(CAST(SUBSTR(e.morning_line,INSTR(e.morning_line,'/')+1) AS REAL),0)
                            ELSE CAST(e.morning_line AS REAL) END ASC) AS rn
                    FROM entries e
                    WHERE e.morning_line IS NOT NULL
                      AND e.morning_line != ''
                      AND e.scratched = 0
                )
                SELECT COUNT(*) AS races,
                       SUM(CASE WHEN p.program_num = res.winner_num THEN 1 ELSE 0 END) AS wins
                FROM parsed p
                JOIN results res ON res.race_id = p.race_id
                WHERE p.rn = 1
            """).fetchone()
            ag_r = ag[0] or 0; ag_w = ag[1] or 0
            ml_r = ml[0] or 0; ml_w = ml[1] or 0
            return {
                'agent_races':   ag_r, 'agent_wins': ag_w,
                'agent_win_pct': round(100.0*ag_w/ag_r,1) if ag_r else 0,
                'ml_races':      ml_r, 'ml_wins': ml_w,
                'ml_win_pct':    round(100.0*ml_w/ml_r,1) if ml_r else 0,
            }
    except Exception:
        return {}


def build_jockey_html():
    jockeys    = get_jockey_leaderboard()
    track_map  = get_jockey_tracks()
    ml         = get_ml_accuracy()

    rows = ""
    for idx, j in enumerate(jockeys):
        clr      = "#00c896" if j["win_pct"] >= 20 else "#c8d8f0"
        jid      = "jt_" + str(idx)
        tracks   = track_map.get(j["jockey"], [])

        # Track breakdown sub-rows
        track_html = ""
        if tracks:
            track_cells = ""
            for t in tracks[:6]:  # top 6 tracks per jockey
                tw  = t["wins"]
                ts  = t["starts"]
                twp = t["win_pct"]
                tc  = "#00c896" if twp >= 25 else "#ffd60a" if twp >= 15 else "#4a6080"
                tname = t["track_name"]
                if len(tname) > 18:
                    tname = tname[:16] + ".."
                track_cells += (
                    "<span style='display:inline-block;margin:2px 4px 2px 0;"
                    "background:#162038;border-radius:4px;padding:2px 6px;"
                    "font-size:9px;color:" + tc + "'>"
                    + tname + " " + str(tw) + "/" + str(ts) +
                    " (" + str(twp) + "%)</span>"
                )
            track_html = (
                "<tr id='" + jid + "' style='display:none;background:#0a1020'>"
                "<td colspan='5' style='padding:4px 8px 8px 24px'>"
                "<span style='font-size:9px;color:#4a6080;margin-right:6px'>TRACKS:</span>"
                + track_cells +
                "</td></tr>"
            )

        toggle = "onclick=\"var r=document.getElementById('" + jid + "');r.style.display=r.style.display==='none'?'':'none';\""

        rows += (
            "<tr style='border-bottom:0.5px solid #1e2d4a22;cursor:pointer' " + toggle + ">"
            "<td style='padding:5px 8px;color:#c8d8f0'>"
            + ("<span style='font-size:9px;color:#4a6080;margin-right:4px'>&#9660;</span>" if tracks else "") +
            j["jockey"] + "</td>"
            "<td style='padding:5px 8px;text-align:right;color:#4a6080'>" + str(j["starts"]) + "</td>"
            "<td style='padding:5px 8px;text-align:right;color:" + clr + ";font-weight:700'>" + str(j["win_pct"]) + "%</td>"
            "<td style='padding:5px 8px;text-align:right;color:#ffd60a'>" + str(j["itm_pct"]) + "%</td>"
            "<td style='padding:5px 8px;text-align:right;color:#4a6080'>" +
            str(j["wins"]) + "/" + str(j["places"]) + "/" + str(j["shows"]) + "</td>"
            "</tr>"
            + track_html
        )

    if not rows:
        rows = "<tr><td colspan='5' style='color:#4a6080;padding:10px'>No jockey data yet</td></tr>"

    ag_pct = ml.get("agent_win_pct", 0)
    ml_pct = ml.get("ml_win_pct", 0)
    edge   = round(ag_pct - ml_pct, 1)
    ec     = "#00c896" if edge >= 0 else "#ff4d6d"
    edge_s = ("+" if edge >= 0 else "") + str(edge) + "%"

    return (
        "<details style='margin:16px 0'>"
        "<summary style='cursor:pointer;background:#0f1829;border:0.5px solid #1e2d4a;"
        "border-radius:8px;padding:12px 16px;font-size:12px;font-weight:700;"
        "color:#00c896;letter-spacing:.05em;list-style:none'>"
        "&#127943; JOCKEY LEADERBOARD &mdash; LAST 30 DAYS &nbsp;"
        "<span style='font-size:10px;font-weight:400;color:#4a6080'>"
        "(click to expand &bull; click jockey row for track breakdown)</span>"
        "</summary>"
        "<div style='background:#0a1020;border:0.5px solid #1e2d4a;"
        "border-top:none;border-radius:0 0 8px 8px;padding:14px'>"
        "<table style='width:100%;border-collapse:collapse;font-size:11px;margin-bottom:16px'>"
        "<thead><tr style='color:#4a6080;border-bottom:0.5px solid #1e2d4a'>"
        "<th style='padding:5px 8px;text-align:left'>JOCKEY</th>"
        "<th style='padding:5px 8px;text-align:right'>STARTS</th>"
        "<th style='padding:5px 8px;text-align:right'>WIN%</th>"
        "<th style='padding:5px 8px;text-align:right'>ITM%</th>"
        "<th style='padding:5px 8px;text-align:right'>W/P/S</th>"
        "</tr></thead>"
        "<tbody>" + rows + "</tbody></table>"
        "<div style='font-size:10px;font-weight:700;color:#7eb6ff;margin-bottom:8px'>"
        "&#128202; MODEL vs MORNING LINE ACCURACY</div>"
        "<div style='display:flex;gap:10px;flex-wrap:wrap'>"
        "<div style='background:#162038;border-radius:6px;padding:10px 14px'>"
        "<div style='font-size:9px;color:#4a6080;margin-bottom:4px'>ML FAV WIN%</div>"
        "<div style='font-size:20px;font-weight:700;color:#c8d8f0'>" + str(ml_pct) + "%</div>"
        "<div style='font-size:9px;color:#4a6080'>" + str(ml.get("ml_races", 0)) + " races</div></div>"
        "<div style='background:#162038;border-radius:6px;padding:10px 14px'>"
        "<div style='font-size:9px;color:#4a6080;margin-bottom:4px'>AGENT PICK #1</div>"
        "<div style='font-size:20px;font-weight:700;color:#c8d8f0'>" + str(ag_pct) + "%</div>"
        "<div style='font-size:9px;color:#4a6080'>" + str(ml.get("agent_races", 0)) + " races</div></div>"
        "<div style='background:#162038;border-radius:6px;padding:10px 14px'>"
        "<div style='font-size:9px;color:#4a6080;margin-bottom:4px'>AGENT EDGE vs ML</div>"
        "<div style='font-size:20px;font-weight:700;color:" + ec + "'>" + edge_s + "</div>"
        "<div style='font-size:9px;color:#4a6080'>vs ML fav</div></div>"
        "</div>"
        "</div></details>"
    )
