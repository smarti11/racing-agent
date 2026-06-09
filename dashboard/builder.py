#!/usr/bin/env python3
"""Furbo Fox Racing — Phase 3"""

import os
import webbrowser
from datetime import datetime
import logging
from pathlib import Path
from db.database import get_todays_races, get_race_entries, get_pick_record, get_todays_results, get_agent_pick_stats, get_todays_agent_picks, get_roi_stats, get_optimized_roi_stats, get_stats_by_track, get_stats_by_field_size, get_track_roi_by_confidence, get_todays_entry_scores, get_todays_race_analyses
from config.settings import DASHBOARD_OUTPUT


def cc(conf):
    return {"HIGH":"#00c896","MEDIUM":"#ffd60a","LOW":"#ff8c42"}.get(conf,"#4a6080")


def render_bet_slate_html(slate):
    """Render today's bet slate as an HTML table block."""
    if not slate:
        return ""
    
    upcoming = [s for s in slate if s["status"] == "upcoming"]
    completed = [s for s in slate if s["status"] != "upcoming"]
    
    # Header
    html = '<div style="margin:16px 0;padding:14px 16px;background:#0f1828;border:0.5px solid #1e2d4a;border-radius:8px">'
    html += '<div style="display:flex;align-items:baseline;gap:14px;margin-bottom:10px">'
    html += '<div style="font-size:13px;font-weight:700;color:#00c896;letter-spacing:.05em">TODAY\'S BET SLATE</div>'
    html += f'<div style="font-size:11px;color:#4a6080">{len(upcoming)} upcoming · {len(completed)} graded · HIGH CONF only · Bolton-Chapman validated</div>'
    html += '</div>'
    
    # Table
    html += '<table style="width:100%;border-collapse:collapse;font-size:12px">'
    html += '<tr style="color:#4a6080;text-align:left;border-bottom:0.5px solid #1e2d4a">'
    html += '<th style="padding:6px 8px;font-weight:600">TRACK</th>'
    html += '<th style="padding:6px 8px;font-weight:600">RACE</th>'
    html += '<th style="padding:6px 8px;font-weight:600">POST</th>'
    html += '<th style="padding:6px 8px;font-weight:600">PICK</th>'
    html += '<th style="padding:6px 8px;font-weight:600">HORSE</th>'
    html += '<th style="padding:6px 8px;font-weight:600">CONF</th>'
    html += '<th style="padding:6px 8px;font-weight:600">BET</th>'
    html += '<th style="padding:6px 8px;font-weight:600;text-align:right">MODEL%</th>'
    html += '<th style="padding:6px 8px;font-weight:600;text-align:right">MKT%</th>'
    html += '<th style="padding:6px 8px;font-weight:600;text-align:right">EDGE</th>'
    html += '<th style="padding:6px 8px;font-weight:600;text-align:right">TRK ROI</th>'
    html += '<th style="padding:6px 8px;font-weight:600">STATUS</th>'
    html += '</tr>'
    
    def conf_color(c):
        return {"HIGH":"#00c896","MEDIUM":"#ffd60a","LOW":"#ff8c42"}.get(c, "#4a6080")
    
    def market_prob_from_ml(ml):
        """Convert morning line like '5/2' or '7-1' to implied probability."""
        if not ml: return None
        try:
            text = str(ml).strip().replace("-", "/")
            if "/" in text:
                num, denom = text.split("/")
                num_f = float(num.strip())
                denom_f = float(denom.strip())
                if num_f + denom_f == 0: return None
                return denom_f / (num_f + denom_f)
            odds = float(text)
            if odds <= 0: return None
            return 1.0 / (odds + 1.0)
        except: return None
    
    def render_edge_cells(model_prob, ml):
        """Returns three <td>: MODEL%, MKT%, EDGE."""
        mkt = market_prob_from_ml(ml)
        if model_prob is None:
            model_str = "—"
        else:
            model_str = f"{model_prob*100:.1f}%"
        if mkt is None:
            mkt_str = "—"
        else:
            mkt_str = f"{mkt*100:.1f}%"
        if model_prob is None or mkt is None or mkt == 0:
            edge_str = "—"
            edge_c = "#4a6080"
        else:
            edge = (model_prob - mkt) / mkt * 100
            edge_str = f"{edge:+.0f}%"
            if edge > 20: edge_c = "#00c896"
            elif edge > 0: edge_c = "#a3e635"
            elif edge > -20: edge_c = "#ff8c42"
            else: edge_c = "#ff4d6d"
        return (
            f'<td style="padding:6px 8px;color:#c8d8f0;text-align:right;font-family:Courier,monospace">{model_str}</td>'
            f'<td style="padding:6px 8px;color:#4a6080;text-align:right;font-family:Courier,monospace">{mkt_str}</td>'
            f'<td style="padding:6px 8px;color:{edge_c};text-align:right;font-family:Courier,monospace;font-weight:700">{edge_str}</td>'
        )
    
    def status_color(s):
        if s == "upcoming": return "#4a6080"
        if s == "WON": return "#00c896"
        if s in ("place", "show"): return "#ffd60a"
        if s in ("lost", "MISS"): return "#ff4d6d"
        return "#4a6080"
    
    def status_display(s):
        if s == "upcoming": return "—"
        if s == "WON": return "WON"
        return s.upper()
    
    # Upcoming first
    for s in upcoming:
        html += f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["track"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">R{s["race_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["post_time"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">#{s["program_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["horse_name"]}</td>'
        html += f'<td style="padding:6px 8px;color:{conf_color(s["confidence"])};font-weight:700">{s["confidence"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["bet_type"]}</td>'
        html += render_edge_cells(s.get("calibrated_prob"), s.get("morning_line"))
        roi = s["track_roi"]
        roi_c = "#00c896" if roi > 0 else "#ff4d6d"
        html += f'<td style="padding:6px 8px;color:{roi_c};text-align:right">{roi:+.1f}%</td>'
        html += f'<td style="padding:6px 8px;color:{status_color(s["status"])}">{status_display(s["status"])}</td>'
        html += '</tr>'
    
    # Divider
    if completed:
        html += '<tr><td colspan="12" style="padding:8px;color:#4a6080;font-size:10px;border-top:0.5px solid #1e2d4a">— GRADED —</td></tr>'
    
    # Completed
    for s in completed:
        html += f'<tr style="border-bottom:0.5px solid #1e2d4a22;opacity:0.75">'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["track"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">R{s["race_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["post_time"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">#{s["program_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["horse_name"]}</td>'
        html += f'<td style="padding:6px 8px;color:{conf_color(s["confidence"])};font-weight:700">{s["confidence"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{s["bet_type"]}</td>'
        html += render_edge_cells(s.get("calibrated_prob"), s.get("morning_line"))
        roi = s["track_roi"]
        roi_c = "#00c896" if roi > 0 else "#ff4d6d"
        html += f'<td style="padding:6px 8px;color:{roi_c};text-align:right">{roi:+.1f}%</td>'
        html += f'<td style="padding:6px 8px;color:{status_color(s["status"])};font-weight:700">{status_display(s["status"])}</td>'
        html += '</tr>'
    
    html += '</table>'
    html += '</div>'
    return html


def pace_badge(role):
    c = {"E":"#ff4d6d","EP":"#ff6b35","P":"#ff8c42","S":"#ffd60a","C":"#00c896","U":"#4a6080"}.get(role,"#4a6080")
    l = {"E":"E-SPD","EP":"E-PRS","P":"PRESS","S":"STALK","C":"CLOSE","U":"UNK"}.get(role,"?")
    return f'<span style="background:{c}22;color:{c};padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid {c}44">{l}</span>'


def form_badge(form_str):
    if not form_str or form_str == "---":
        return '<span style="color:#4a6080;font-size:10px">—</span>'
    parts = form_str.split("-")
    html = ""
    for p in parts[:3]:
        c = "#00c896" if p=="1" else "#ffd60a" if p=="2" else "#ff8c42" if p=="3" else "#4a6080"
        html += f'<span style="color:{c};font-weight:700;font-size:11px">{p}</span><span style="color:#2a3a5a;font-size:10px">-</span>'
    return f'<span style="font-family:Courier,monospace">{html.rstrip("</span>").rstrip("-")}</span>'


def class_badge(change):
    if change == "DROP":
        return '<span style="background:#00c89622;color:#00c896;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">↓ CLASS</span>'
    elif change == "RISE":
        return '<span style="background:#ff4d6d22;color:#ff4d6d;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">↑ CLASS</span>'
    return ""


def trainer_badge(hot):
    if hot == "HOT":
        return '<span style="background:#00c89622;color:#00c896;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">🔥 HOT</span>'
    elif hot == "COLD":
        return '<span style="background:#4a608022;color:#4a6080;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">❄ COLD</span>'
    return ""


def layoff_badge(flag, days):
    if flag == "LONG_LAYOFF":
        return f'<span style="background:#ff4d6d22;color:#ff4d6d;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">{days}d LAY</span>'
    elif flag == "LAYOFF":
        return f'<span style="background:#ffd60a22;color:#ffd60a;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">{days}d OFF</span>'
    elif flag == "FRESH":
        return f'<span style="background:#00c89622;color:#00c896;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">{days}d</span>'
    return f'<span style="color:#4a6080;font-size:10px">{days}d</span>' if days else ""


def value_badge(value):
    if value >= 5:
        return '<span style="background:#00c89622;color:#00c896;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid #00c89644">VALUE</span>'
    elif value >= 2:
        return '<span style="background:#ffd60a22;color:#ffd60a;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid #ffd60a44">WATCH</span>'
    return ""


def score_bar(score):
    pct = min(100, max(0, score))
    color = "#00c896" if pct >= 65 else "#ffd60a" if pct >= 50 else "#ff4d6d"
    return f'<div style="display:flex;align-items:center;gap:5px"><div style="width:55px;height:5px;background:#1e2d4a;border-radius:3px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{color};border-radius:3px"></div></div><span style="font-size:10px;color:{color};font-weight:700">{score:.0f}</span></div>'


def pct_display(pct, starts):
    if pct is None or starts < 5:
        return '<span style="color:#2a3a5a;font-size:9px">—</span>'
    c = "#00c896" if pct >= 20 else "#ffd60a" if pct >= 14 else "#4a6080"
    return f'<span style="color:{c};font-size:10px;font-weight:700">{pct:.0f}%</span>'


def get_todays_high_picks():
    """Return ALL today's HIGH-confidence rank-1 picks (no track-profitability filter).
    Pulls from agent_picks_history (latest snapshot per race) so it reflects the
    live dashboard state during racing hours; falls back to agent_picks otherwise.
    """
    from datetime import datetime as _dt
    try:
        import pytz
        EASTERN = pytz.timezone("US/Eastern")
        today = _dt.now(EASTERN).date().isoformat()
    except Exception:
        today = _dt.now().date().isoformat()

    from db.database import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            WITH latest_picks AS (
                SELECT aph.race_id, aph.program_num, aph.horse_name, aph.confidence,
                       aph.rendered_ts,
                       ROW_NUMBER() OVER (
                         PARTITION BY aph.race_id ORDER BY aph.rendered_ts DESC
                       ) AS rn
                FROM agent_picks_history aph
                JOIN races r ON aph.race_id = r.id
                WHERE r.race_date = ? AND aph.rank = 1
            )
            SELECT r.id AS race_id, r.track_name, r.race_num, r.post_time,
                   lp.program_num, lp.horse_name, lp.confidence,
                   res.winner_num,
                   CASE WHEN res.winner_num = lp.program_num THEN 'WIN'
                        WHEN res.second_num = lp.program_num THEN 'PLACE'
                        WHEN res.third_num  = lp.program_num THEN 'SHOW'
                        WHEN res.winner_num IS NOT NULL THEN 'MISS'
                        ELSE NULL END AS result_status
            FROM latest_picks lp
            JOIN races r ON lp.race_id = r.id
            LEFT JOIN results res ON res.race_id = r.id
            WHERE lp.rn = 1 AND lp.confidence = 'HIGH'
            ORDER BY r.post_time, r.track_name, r.race_num
        """, (today,)).fetchall()

        if not rows:
            rows = conn.execute("""
                SELECT r.id AS race_id, r.track_name, r.race_num, r.post_time,
                       ap.program_num, ap.horse_name, ap.confidence,
                       res.winner_num,
                       CASE WHEN res.winner_num = ap.program_num THEN 'WIN'
                            WHEN res.second_num = ap.program_num THEN 'PLACE'
                            WHEN res.third_num  = ap.program_num THEN 'SHOW'
                            WHEN res.winner_num IS NOT NULL THEN 'MISS'
                            ELSE NULL END AS result_status
                FROM agent_picks ap
                JOIN races r ON ap.race_id = r.id
                LEFT JOIN results res ON res.race_id = r.id
                WHERE r.race_date = ? AND ap.rank = 1 AND ap.confidence = 'HIGH'
                ORDER BY r.post_time, r.track_name, r.race_num
            """, (today,)).fetchall()

        return [dict(r) for r in rows]


def render_high_picks_html(rows):
    """Render every HIGH-confidence rank-1 pick today as a compact table.
    Unlike the bet slate, this is NOT filtered to profitable tracks — its
    purpose is to give a complete view of what the model rates HIGH today."""
    if not rows:
        return ""

    upcoming = [r for r in rows if r.get("result_status") is None]
    graded   = [r for r in rows if r.get("result_status") is not None]
    wins     = sum(1 for r in graded if r.get("result_status") == "WIN")

    def status_cell(s):
        if s is None:
            return '<td style="padding:6px 8px;color:#4a6080">—</td>'
        color = {"WIN":"#00c896","PLACE":"#ffd60a","SHOW":"#ff8c42","MISS":"#ff4d6d"}.get(s, "#4a6080")
        return f'<td style="padding:6px 8px;color:{color};font-weight:700">{s}</td>'

    html  = '<div style="margin:16px 0;padding:14px 16px;background:#0f1828;border:0.5px solid #00c89633;border-radius:8px">'
    html += '<div style="display:flex;align-items:baseline;gap:14px;margin-bottom:10px">'
    html += '<div style="font-size:13px;font-weight:700;color:#00c896;letter-spacing:.05em">TODAY\'S HIGH-CONFIDENCE PICKS</div>'
    sub = f'{len(rows)} race{"s" if len(rows)!=1 else ""} · {len(upcoming)} upcoming · {len(graded)} graded'
    if graded:
        sub += f' · {wins}/{len(graded)} winners ({wins/len(graded)*100:.0f}%)'
    sub += " · all tracks (unfiltered)"
    html += f'<div style="font-size:11px;color:#4a6080">{sub}</div>'
    html += '</div>'

    html += '<table style="width:100%;border-collapse:collapse;font-size:12px">'
    html += '<tr style="color:#4a6080;text-align:left;border-bottom:0.5px solid #1e2d4a">'
    for h in ("TRACK","RACE","POST","PICK","HORSE","STATUS"):
        align = "left"
        html += f'<th style="padding:6px 8px;font-weight:600;text-align:{align}">{h}</th>'
    html += '</tr>'

    for r in upcoming + graded:
        opacity = "1" if r.get("result_status") is None else "0.75"
        html += f'<tr style="border-bottom:0.5px solid #1e2d4a22;opacity:{opacity}">'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{r["track_name"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">R{r["race_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{r.get("post_time") or "—"}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">#{r["program_num"]}</td>'
        html += f'<td style="padding:6px 8px;color:#c8d8f0">{r["horse_name"]}</td>'
        html += status_cell(r.get("result_status"))
        html += '</tr>'

    html += '</table></div>'
    return html


def get_data_quality_stats(today):
    """Data quality breakdown for today rank-1 picks. DATA_QUALITY_TILE"""
    try:
        from db.database import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT COALESCE(ap.data_quality, 'UNVERIFIED') AS q,
                       COUNT(*) AS n
                FROM agent_picks ap
                JOIN races r ON r.id = ap.race_id
                WHERE r.race_date = ? AND ap.rank = 1
                GROUP BY q ORDER BY n DESC
            """, (today,)).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def build_dashboard():
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    races = [dict(r) for r in get_todays_races()]
    pick_record  = get_pick_record()
    agent_stats  = get_agent_pick_stats()
    
    # Today's bet slate (HIGH/MEDIUM CONF Pick #1 at profitable tracks)
    try:
        from db.database import get_todays_bet_slate
        _slate = get_todays_bet_slate()
        bet_slate_html = render_bet_slate_html(_slate)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Bet slate render failed: %s" % _e)
        bet_slate_html = ""

    # Today's HIGH conf picks — full list, no track-profitability filter.
    # Lets the user see exactly which races the agent is calling HIGH right now.
    try:
        _high = get_todays_high_picks()
        high_picks_html = render_high_picks_html(_high)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("HIGH picks render failed: %s" % _e)
        high_picks_html = ""

    # PICK34_INJECTED: Pick 3 / Pick 4 strategy panels
    try:
        pick34_html = build_pick34_section()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Pick 3/4 section failed: %s" % _e)
        pick34_html = ""
    # DATA_QUALITY_TILE
    try:
        from datetime import date as _dqdate
        dq_stats = get_data_quality_stats(_dqdate.today().isoformat())
    except Exception:
        dq_stats = {}
    roi_stats    = get_roi_stats(bet_amount=0.50)
    opt_stats    = get_optimized_roi_stats()
    try:  # DASHBOARD_V2_APPLIED
        from dashboard.jockey_analytics import build_jockey_html
        jockey_html = build_jockey_html()
    except Exception as _je:
        jockey_html = ''
    picks_today  = get_todays_agent_picks()
    track_stats  = get_stats_by_track()
    field_stats  = get_stats_by_field_size()
    track_roi    = get_track_roi_by_confidence()
    # Build lookup: race_id -> {rank: result}
    picks_map = {}
    for p in picks_today:
        rid = p["race_id"]
        if rid not in picks_map:
            picks_map[rid] = {}
        picks_map[rid][p["rank"]] = dict(p)

    entry_scores  = get_todays_entry_scores()   # {race_id: {program_num: score_dict}}
    race_analyses = get_todays_race_analyses()  # {race_id: analysis_dict}

    tracks = {}
    for race in races:
        t = race["track_name"]
        if t not in tracks:
            tracks[t] = []
        tracks[t].append(race)

    try:
        results_today = get_todays_results()
        results_map = {r["race_id"]: dict(r) for r in results_today}
    except Exception:
        results_map = {}

    total_races     = len(races)

    # Baseline progress: count graded HIGH CONF races from agent_picks
    # (clean post-freeze data only)
    try:
        from db.database import get_conn as _bp_conn
        with _bp_conn() as _bp_c:
            _bp_clean = _bp_c.execute(
                "SELECT COUNT(DISTINCT race_id) FROM agent_picks "
                "WHERE confidence=? AND result IS NOT NULL",
                ("HIGH",),
            ).fetchone()[0] or 0
    except Exception:
        _bp_clean = 0
    _bp_target = 1000
    _bp_pct = min(100.0, 100.0 * _bp_clean / _bp_target) if _bp_target else 0
    if _bp_clean < _bp_target:
        baseline_banner_html = (
            f'<div style="background:linear-gradient(90deg,#3d1f00,#5c2e00);'
            f'border:1px solid #ff8c00;border-radius:6px;padding:12px 16px;'
            f'margin:12px 0;display:flex;align-items:center;gap:14px">'
            f'<span style="font-size:18px">⚠</span>'
            f'<div style="flex:1">'
            f'<div style="font-size:13px;font-weight:700;color:#ffb86b;'
            f'letter-spacing:.05em">BASELINE IN PROGRESS — '
            f'{_bp_clean:,} / {_bp_target:,} HIGH CONF races collected ({_bp_pct:.1f}%)</div>'
            f'<div style="font-size:11px;color:#c8a070;margin-top:3px">'
            f'Performance stats below are early indicators; not yet publishing-ready. '
            f'Historical (pre-freeze) data has been cleared due to a data-integrity bug '
            f'that allowed post-race picks to overwrite live picks.</div>'
            f'<div style="background:#1a1003;border-radius:3px;height:6px;'
            f'margin-top:6px;overflow:hidden">'
            f'<div style="background:linear-gradient(90deg,#ff8c00,#ffb86b);'
            f'height:100%;width:{_bp_pct:.1f}%"></div>'
            f'</div></div></div>'
        )
    else:
        baseline_banner_html = ""
    total_scratches = sum(race["scratch_count"] or 0 for race in races)
    top_picks_count = 0
    # ── ROI Report ─────────────────────────────────────────
    r = roi_stats
    if r["total_races"] > 0:
        profit_color = "#00c896" if r["net_profit"] >= 0 else "#ff4d6d"
        roi_color    = "#00c896" if r["roi_pct"] >= 0 else "#ff4d6d"
        by_conf      = r.get("by_confidence", {})

        conf_rows = ""
        for conf, d in by_conf.items():
            if d.get("races", 0) == 0:
                continue
            pc = "#00c896" if d.get("roi_pct",0) >= 0 else "#ff4d6d"
            conf_rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:6px 10px;color:#c8d8f0;font-weight:700">{conf}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080">{d["races"]}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:#4a6080">${d["wagered"]:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:#4a6080">${d["returned"]:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:{pc};font-weight:700">${d["net_profit"]:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:{pc};font-weight:700">{d["roi_pct"]:+.1f}%</td>'
                f'</tr>'
            )

        recent_rows = ""
        for race in r.get("recent_races", [])[:10]:
            pc = "#00c896" if race.get("profit",0) >= 0 else "#ff4d6d"
            rc = {"WIN":"#00c896","PLACE":"#ffd60a","SHOW":"#ff8c42","MISS":"#ff4d6d"}.get(race.get("result",""),"#4a6080")
            recent_rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:5px 8px;color:#4a6080;font-size:11px">{race.get("date", race.get("race_date","?"))}</td>'
                f'<td style="padding:5px 8px;color:#4a6080;font-size:11px">{race["track"][:10]} R{race.get("race_num","?")}</td>'
                f'<td style="padding:5px 8px;color:#c8d8f0;font-size:11px">{race.get("horse", race.get("horse_name","?"))[:20]}</td>'
                f'<td style="padding:5px 8px;text-align:center"><span style="background:{rc}22;color:{rc};padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700">{race.get("result","")}</span></td>'
                f'<td style="padding:5px 8px;text-align:right;color:#4a6080;font-size:11px">${race.get("wagered",0):.2f}</td>'
                f'<td style="padding:5px 8px;text-align:right;color:{pc};font-size:11px;font-weight:700">{race.get("profit",0):+.2f}</td>'
                f'</tr>'
            )

        bbt = r.get("by_bet_type", {})
        by_rank = r.get("by_rank", {})

        rank_rows = ""
        rank_labels = {1: "★ Pick #1", 2: "· Pick #2", 3: "· Pick #3"}
        for rnk in [1,2,3]:
            d = by_rank.get(rnk, {})
            if not d.get("races"): continue
            pc = "#00c896" if d.get("roi_pct",0) >= 0 else "#ff4d6d"
            rank_rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:6px 10px;color:#ffd60a;font-weight:700;font-size:11px">{rank_labels[rnk]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{d["races"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#00c896;font-size:11px">{d.get("win_hits",0)}</td>'  # PHASE2B_RANK_BODY
                f'<td style="padding:6px 10px;text-align:right;color:#4a6080;font-size:11px">${d["wagered"]:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:#4a6080;font-size:11px">${d["returned"]:.2f}</td>'
                f'<td style="padding:6px 10px;text-align:right;color:{pc};font-weight:700;font-size:11px">{d.get("roi_pct",0):+.1f}%</td>'
                "</tr>"
            )

        roi_title = f'$.50 ATB ALL 3 PICKS — {r["total_races"]} RACES — $4.50/RACE ($1.50 per pick)'

        # Optimized strategy section
        o = opt_stats
        opt_html = ""
        if o.get("total_races", 0) > 0:
            oc = "#00c896" if o["net_profit"] >= 0 else "#ff4d6d"
            or_ = "#00c896" if o["roi_pct"] >= 0 else "#ff4d6d"
            conf_rows_opt = ""
            for conf, d in o.get("by_confidence", {}).items():
                if d.get("races", 0) == 0:
                    continue
                pc = "#00c896" if d.get("roi_pct",0) >= 0 else "#ff4d6d"
                bet_desc = "$2.00 WIN" if conf=="HIGH" else "tracked, not bet"  # PHASE2B_BET_DESC
                hits_str = f'{d.get("win_hits",d.get("place_hits",d.get("show_hits",0)))} hits'
                conf_rows_opt += (
                    f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                    f'<td style="padding:6px 10px;color:#c8d8f0;font-weight:700;font-size:11px">{conf}</td>'
                    f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{bet_desc}</td>'
                    f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{d["races"]}</td>'
                    f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{hits_str}</td>'
                    f'<td style="padding:6px 10px;text-align:right;color:#4a6080;font-size:11px">${d["wagered"]:.2f}</td>'
                    f'<td style="padding:6px 10px;text-align:right;color:#4a6080;font-size:11px">${d["returned"]:.2f}</td>'
                    f'<td style="padding:6px 10px;text-align:right;color:{pc};font-weight:700;font-size:11px">{d.get("roi_pct",0):+.1f}%</td>'
                    f'</tr>'
                )
            oe = o.get("exacta", {})
            ec = "#00c896" if oe.get("roi_pct",0) >= 0 else "#ff4d6d"
            opt_html = (
                '<div style="margin:0 0 20px 0;background:#0f1729;border:0.5px solid #00c89633;'
                'border-radius:10px;padding:16px 20px">'
                '<div style="font-size:11px;font-weight:700;color:#00c896;letter-spacing:.08em;'
                'text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;'
                'border-bottom:0.5px solid #00c89633">'
                f'⭐ OPTIMIZED STRATEGY — {o["total_races"]} RACES — HIGH CONF: $2 WIN · EXACTA BOX: $2 (top-2)' + '<span style="margin-left:10px;padding:2px 8px;background:#0a2540;border:1px solid #4a90e2;border-radius:10px;color:#7eb6ff;font-size:9px;font-weight:600;letter-spacing:.05em;vertical-align:middle">📊 BOLTON-CHAPMAN VALIDATED</span>'  # BC_BADGE_APPLIED
                '</div>'
                '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px">'
                f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896">'
                f'<div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Total Wagered</div>'
                f'<div style="font-size:18px;font-weight:700;color:#fff">${o["total_wagered"]:.2f}</div>'
                f'<div style="font-size:10px;color:#4a6080">{o["total_races"]} races</div></div>'
                f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896">'
                f'<div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Total Returned</div>'
                f'<div style="font-size:18px;font-weight:700;color:#fff">${o["total_returned"]:.2f}</div></div>'
                f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896">'
                f'<div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Net Profit</div>'
                f'<div style="font-size:18px;font-weight:700;color:{oc}">${o["net_profit"]:+.2f}</div></div>'
                f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896">'
                f'<div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">ROI</div>'
                f'<div style="font-size:18px;font-weight:700;color:{or_}">{o["roi_pct"]:+.1f}%</div></div>'
                '</div>'
                + (f'<div style="margin-bottom:12px"><table style="width:100%;border-collapse:collapse">'
                   f'<thead><tr style="background:#162038">'
                   f'<th style="padding:6px 10px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">CONF</th>'
                   f'<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">BET</th>'
                   f'<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">RACES</th>'
                   f'<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">HITS</th>'
                   f'<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">WAGERED</th>'
                   f'<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">RETURNED</th>'
                   f'<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ROI%</th>'
                   f'</tr></thead><tbody>' + conf_rows_opt + '</tbody></table></div>' if conf_rows_opt else '')
                + f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ffd60a">'
                f'<div style="font-size:9px;color:#4a6080;margin-bottom:3px">EXACTA BOX ($3.00/race)</div>'
                f'<div style="font-size:14px;font-weight:700;color:#fff">{oe.get("hits",0)} hits</div>'
                f'<div style="font-size:11px;color:{ec}">${oe.get("returned",0):.2f} ret · {oe.get("roi_pct",0):+.1f}%</div></div>'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px">'
                f'<div style="font-size:9px;color:#4a6080;margin-bottom:3px">PICK #2 ROLE</div>'
                f'<div style="font-size:11px;color:#4a6080">Informational only</div>'
                f'<div style="font-size:10px;color:#4a6080">No ATB bet</div></div>'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px">'
                f'<div style="font-size:9px;color:#4a6080;margin-bottom:3px">PICK #3 ROLE</div>'
                f'<div style="font-size:11px;color:#4a6080">Informational only</div>'
                f'<div style="font-size:10px;color:#4a6080">No ATB bet</div></div>'
                '</div></div>'
            )
        roi_html = (
            '<div style="margin:0 0 20px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:16px 20px">'
            '<div style="font-size:11px;font-weight:700;color:#4a6080;letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;border-bottom:0.5px solid #1e2d4a">'
            + roi_title +
            '</div>'
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">'
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px"><div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Total Wagered</div><div style="font-size:18px;font-weight:700;color:#fff">${r["total_wagered"]:.2f}</div><div style="font-size:10px;color:#4a6080">{r["total_races"]} races</div></div>'
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px"><div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Total Returned</div><div style="font-size:18px;font-weight:700;color:#fff">${r["total_returned"]:.2f}</div></div>'
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px"><div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">Net Profit</div><div style="font-size:18px;font-weight:700;color:{profit_color}">${r["net_profit"]:+.2f}</div></div>'
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px"><div style="font-size:9px;color:#4a6080;text-transform:uppercase;margin-bottom:4px">ROI</div><div style="font-size:18px;font-weight:700;color:{roi_color}">{r["roi_pct"]:+.1f}%</div></div>'
            '</div>'
            '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px">'  # PHASE2B_HITS_PANEL
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896"><div style="font-size:9px;color:#4a6080;margin-bottom:4px">WIN HITS</div><div style="font-size:14px;font-weight:700;color:#fff">{r["win_hits"]}</div><div style="font-size:11px;color:#4a6080">${bbt.get("win",{}).get("returned",0):.2f} returned</div></div>'
            f'<div style="background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #ffd60a"><div style="font-size:9px;color:#4a6080;margin-bottom:4px">EXACTA HITS</div><div style="font-size:14px;font-weight:700;color:#fff">{r.get("exacta_box",{}).get("hits",0)}</div><div style="font-size:11px;color:#4a6080">${r.get("exacta_box",{}).get("returned",0):.2f} returned</div></div>'
            '</div>'
            + ('<div style="margin-bottom:14px"><div style="font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700">ROI BY PICK RANK</div>'
               '<table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:#162038">'
               '<th style="padding:6px 10px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">PICK</th>'
               '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">RACES</th>'
               '<th style="padding:6px 10px;text-align:center;color:#00c896;font-size:9px;font-weight:400">WIN HITS</th>'  # PHASE2B_RANK_HEAD
               '<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">WAGERED</th>'
               '<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">RETURNED</th>'
               '<th style="padding:6px 10px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ROI%</th>'
               '</tr></thead><tbody>' + rank_rows + '</tbody></table></div>' if rank_rows else "")
            # Exacta + Trifecta box sections
            + (lambda eb, tb: (
                # Exacta Box
                '<div style="margin-bottom:10px">'
                '<div style="font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700;letter-spacing:.06em">'
                f'EXACTA BOX — TOP 3 PICKS &nbsp;·&nbsp; 6 combos × ${r["bet_amount"]:.2f} = ${eb.get("cost_per_race",3.00):.2f}/race'
                '</div>'
                '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ffd60a"><div style="font-size:9px;color:#4a6080;margin-bottom:3px">WAGERED</div><div style="font-size:16px;font-weight:700;color:#fff">${eb.get("wagered",0):.2f}</div></div>'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ffd60a"><div style="font-size:9px;color:#4a6080;margin-bottom:3px">RETURNED</div><div style="font-size:16px;font-weight:700;color:#fff">${eb.get("returned",0):.2f}</div></div>'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ffd60a"><div style="font-size:9px;color:#4a6080;margin-bottom:3px">NET P&L</div><div style="font-size:16px;font-weight:700;color:{"#00c896" if eb.get("net_profit",0)>=0 else "#ff4d6d"}">${eb.get("net_profit",0):+.2f}</div></div>'
                f'<div style="background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ffd60a"><div style="font-size:9px;color:#4a6080;margin-bottom:3px">HITS / ROI</div><div style="font-size:16px;font-weight:700;color:{"#00c896" if eb.get("roi_pct",0)>=0 else "#ff4d6d"}">{eb.get("hits",0)} / {eb.get("roi_pct",0):+.1f}%</div></div>'
                '</div>'
                # Trifecta panel removed by PHASE2B (no longer in strategy)
                ''
                '</div>'
            ))(r.get("exacta_box", {}), r.get("trifecta_box", {})) if r.get("exacta_box") else ""

            + (f'<div><div style="font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700">RECENT RACE RESULTS</div>'
               f'<table style="width:100%;border-collapse:collapse"><thead><tr style="background:#162038">'
               '<th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">DATE</th>'
               '<th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">RACE</th>'
               '<th style="padding:5px 8px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">WAGERED</th>'
               '<th style="padding:5px 8px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">RETURNED</th>'
               '<th style="padding:5px 8px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">P&L</th>'
               '</tr></thead><tbody>' + recent_rows + '</tbody></table></div>' if recent_rows else "")
            + '</div>'
        )
    else:
        roi_html = (
            '<div style="margin:0 0 20px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:16px 20px;text-align:center;color:#4a6080;font-size:12px">'
            '$.50 Across the Board ROI Tracker — No graded races yet. Results will appear as races finish today.'
            '</div>'
        )

    # ── Track & Field Size Analysis ────────────────────────────
    analysis_html = ""
    if track_stats or field_stats:
        track_rows = ""
        # Sort tracks by win% desc (primary) then races desc (tie-breaker so a 1/1
        # track doesn't leapfrog a 50/200 track at the same headline percentage).
        for tname, ts in sorted(
            track_stats.items(),
            key=lambda x: (x[1].get("win_pct", 0) or 0, x[1].get("races", 0) or 0),
            reverse=True,
        ):
            if ts["races"] < 1:
                continue
            wc = "#00c896" if ts["win_pct"] >= 30 else "#ffd60a" if ts["win_pct"] >= 20 else "#ff4d6d"
            wps_c = "#00c896" if ts["wps_pct"] >= 55 else "#ffd60a" if ts["wps_pct"] >= 40 else "#ff4d6d"
            track_rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:6px 10px;color:#c8d8f0;font-weight:700;font-size:11px">{tname}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{ts["races"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{ts["wins"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:{wc};font-weight:700;font-size:11px">{ts["win_pct"]}%</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{ts["wps"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:{wps_c};font-weight:700;font-size:11px">{ts["wps_pct"]}%</td>'
                f'</tr>'
            )

        field_rows = ""
        for bucket in ["Small (2-5)", "Medium (6-8)", "Large (9+)"]:
            fs = field_stats.get(bucket)
            if not fs:
                continue
            wc = "#00c896" if fs["win_pct"] >= 30 else "#ffd60a" if fs["win_pct"] >= 20 else "#ff4d6d"
            wps_c = "#00c896" if fs["wps_pct"] >= 55 else "#ffd60a" if fs["wps_pct"] >= 40 else "#ff4d6d"
            field_rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:6px 10px;color:#c8d8f0;font-weight:700;font-size:11px">{bucket}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{fs["races"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{fs["avg_field"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{fs["wins"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:{wc};font-weight:700;font-size:11px">{fs["win_pct"]}%</td>'
                f'<td style="padding:6px 10px;text-align:center;color:#4a6080;font-size:11px">{fs["wps"]}</td>'
                f'<td style="padding:6px 10px;text-align:center;color:{wps_c};font-weight:700;font-size:11px">{fs["wps_pct"]}%</td>'
                f'</tr>'
            )

        analysis_html = (
            '<div style="margin:0 0 20px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:16px 20px">'
            '<div style="font-size:11px;font-weight:700;color:#00c896;letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;border-bottom:0.5px solid #00c89633">'
            'PERFORMANCE BY TRACK & FIELD SIZE</div>'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">'
            # Track table
            '<div><div style="font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700">BY TRACK (Pick #1)</div>'
            '<table style="width:100%;border-collapse:collapse"><thead><tr style="background:#162038">'
            '<th style="padding:6px 10px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">TRACK</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">RACES</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WINS</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WIN%</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WPS</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WPS%</th>'
            '</tr></thead><tbody>' + track_rows + '</tbody></table></div>'
            # Field size table
            '<div><div style="font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700">BY FIELD SIZE (Pick #1)</div>'
            '<table style="width:100%;border-collapse:collapse"><thead><tr style="background:#162038">'
            '<th style="padding:6px 10px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">SIZE</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">RACES</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">AVG</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WINS</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WIN%</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WPS</th>'
            '<th style="padding:6px 10px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">WPS%</th>'
            '</tr></thead><tbody>' + field_rows + '</tbody></table></div>'
            '</div></div>'
        )


    # Track ROI by Confidence section
    track_roi_html = ""
    if track_roi:
        rows_html = ""

        # Pre-compute overall ROI for each track so we can order the table
        # high-to-low — most profitable tracks at the top.
        def _track_overall_roi(confs):
            tw = sum(c["wagered"] for c in confs.values())
            tr = sum(c["returned"] for c in confs.values())
            return ((tr - tw) / tw * 100) if tw else 0

        ordered_tracks = sorted(
            track_roi.keys(),
            key=lambda t: (
                _track_overall_roi(track_roi[t]),
                sum(c["races"] for c in track_roi[t].values()),
            ),
            reverse=True,
        )

        for track_name in ordered_tracks:
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

    # ── End ROI Report ───────────────────────────────────────
    race_html       = ""

    if not tracks:
        race_html = '<div style="text-align:center;padding:48px;color:#4a6080;font-size:13px">No races found. Run the agent to fetch entries.</div>'
    else:
        for track_name, track_races in tracks.items():
            track_id = track_name.replace(" ", "_").replace("'","")
            race_html += (
                '<div style="margin-bottom:28px">'
                '<div onclick="toggleTrack(\'' + track_id + '\')" '
                'style="font-size:13px;font-weight:700;color:#fff;margin-bottom:10px;'
                'padding:8px 14px;background:#162038;border-radius:8px;'
                'border-left:3px solid #00c896;display:flex;justify-content:space-between;'
                'align-items:center;cursor:pointer;user-select:none">'
                f'<span>{track_name}</span>'
                '<div style="display:flex;align-items:center;gap:10px">'
                f'<span style="font-size:10px;font-weight:400;color:#4a6080">{len(track_races)} races</span>'
                f'<span id="arrow_{track_id}" style="color:#4a6080;font-size:12px;transition:transform .2s">&#9654;</span>'
                '</div></div>'
                f'<div id="track_{track_id}" style="display:none">'
            )

            for race in track_races:
                entries    = get_race_entries(race["id"])
                active     = [e for e in entries if not e["scratched"]]
                scratched  = [e for e in entries if e["scratched"]]
                conditions = race["conditions"] or ""
                distance   = race["distance"] or ""
                track_code = race["track_code"] or ""

                # Renderer reads from agent_picks (frozen by the agent loop).
                # No live re-handicap; no writes to agent_picks_history.
                _rp = picks_map.get(race["id"], {})
                role_top3 = [v for _, v in sorted(_rp.items())]
                # Drop any picks whose horse was scratched after the freeze
                _scr_nums = {e["program_num"] for e in scratched}
                role_top3 = [p for p in role_top3 if p.get("program_num") not in _scr_nums]
                top_pick = role_top3[0] if role_top3 else None
                if top_pick:
                    top_picks_count += 1

                # Per-race score map from stored entry scores (all active runners)
                score_map = entry_scores.get(race["id"], {})

                # Pace scenario from stored race analysis
                _ra = race_analyses.get(race["id"], {})
                pace_scenario_name  = _ra.get("pace_scenario_name", "")
                pace_scenario_notes = _ra.get("pace_scenario_notes", "")
                pace_post_bias      = _ra.get("pace_post_bias", "")
                lone_speed          = bool(_ra.get("lone_speed"))

                scenario_colors = {
                    "LONE_SPEED":   "#ff4d6d",
                    "CONTESTED":    "#ffd60a",
                    "HONEST":       "#00c896",
                    "CLOSERS_RACE": "#00c896",
                }
                scenario_color = scenario_colors.get(pace_scenario_name, "#4a6080")

                surface       = race["surface"] or "Dirt"
                surface_color = "#00c896" if surface.lower() in ["turf","grass"] else "#ffd60a"
                post_time     = race["post_time"] or "TBD"
                cond_short    = (conditions[:45]+"...") if len(conditions)>45 else conditions

                # Result badge
                result_data   = results_map.get(race["id"])
                result_badge  = ""
                if result_data:
                    wn   = result_data.get("winner_name","?")
                    wnum = result_data.get("winner_num","?")
                    wpay = result_data.get("winner_win_payout")
                    snum = result_data.get("second_num","")
                    sn   = result_data.get("second_name","")
                    tnum = result_data.get("third_num","")
                    tn   = result_data.get("third_name","")
                    pay_str   = f" (${wpay:.2f})" if wpay else ""
                    place_str = f" · 2nd:#{snum} {sn}" if snum else ""
                    show_str  = f" · 3rd:#{tnum} {tn}" if tnum else ""
                    epay = result_data.get("exacta_payout")
                    tpay = result_data.get("trifecta_payout")
                    exact_str = f" · EX:${epay:.2f}" if epay else ""
                    tri_str   = f" · TRI:${tpay:.2f}" if tpay else ""
                    result_badge = f'<span style="background:#00c89622;color:#00c896;padding:3px 10px;border-radius:3px;font-size:10px;font-weight:700;border:0.5px solid #00c89644">✓ #{wnum} {wn}{pay_str}{place_str}{show_str}{exact_str}{tri_str}</span>'

                # Top 3 picks banner
                # Get saved pick grades for this race
                race_picks = picks_map.get(race["id"], {})

                pick_banner = ""
                if role_top3:
                    top3 = role_top3
                    conf_str = f'<span style="background:{cc(top_pick["confidence"])}22;color:{cc(top_pick["confidence"])};padding:2px 7px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid {cc(top_pick["confidence"])}44">{top_pick["confidence"]} CONF</span>' if top_pick else ""
                    picks_html = ""
                    for i, p in enumerate(top3):
                        _psc = score_map.get(str(p.get("program_num", "")), {})
                        vb = value_badge(_psc.get("value", 0))
                        star = "★" if i==0 else "·"
                        fw = "700" if i==0 else "400"
                        fc = "#fff" if i==0 else "#c8d8f0"
                        cb = class_badge(_psc.get("class_change", ""))
                        # Grade badge + P&L from saved picks
                        saved_pick = race_picks.get(i+1, {})
                        grade = saved_pick.get('result', '')
                        grade_colors = {'WIN':'#00c896','PLACE':'#ffd60a','SHOW':'#ff8c42','MISS':'#ff4d6d'}
                        grade_html = ''
                        pnl_html = ''
                        if grade and result_data:
                            gc = grade_colors.get(grade, '#4a6080')
                            scale = 0.50 / 2.0
                            prog = str(p['program_num'])
                            wnum = str(result_data.get('winner_num',''))
                            pnum = str(result_data.get('second_num','') or '')
                            snum = str(result_data.get('third_num','') or '')
                            returned = 0.0
                            if prog == wnum:
                                returned += (result_data.get('winner_win_payout') or 0) * scale
                                returned += (result_data.get('winner_place_payout') or 0) * scale
                                returned += (result_data.get('winner_show_payout') or 0) * scale
                            elif prog == pnum:
                                returned += (result_data.get('second_place_payout') or 0) * scale
                                returned += (result_data.get('second_show_payout') or 0) * scale
                            elif prog == snum:
                                returned += (result_data.get('third_show_payout') or 0) * scale
                            net = returned - 1.50  # $0.50 x 3 bets
                            net_color = '#00c896' if net >= 0 else '#ff4d6d'
                            net_str = f'{net:+.2f}'
                            grade_html = f'<span style="background:{gc}22;color:{gc};padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid {gc}44">{grade}</span>'
                            if grade != 'MISS':
                                pnl_html = f'<span style="color:{net_color};font-size:10px;font-weight:700">{net_str}</span>'
                        # Role badge
                        role = p.get("role","")
                        role_colors = {"WIN":"#00c896","PLACE":"#ffd60a","SHOW":"#ff8c42"}
                        role_html = f'<span style="background:{role_colors.get(role,"#4a6080")}22;color:{role_colors.get(role,"#4a6080")};padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid {role_colors.get(role,"#4a6080")}44">{role}</span>' if role else ""
                        # Bet recommendation
                        bet_rec = p.get("bet_recommendation","")
                        bet_html = f'<span style="color:#4a6080;font-size:9px">{bet_rec}</span>' if bet_rec else ""
                        picks_html += (
                            '<div style="display:flex;align-items:center;gap:5px;padding:4px 8px;background:#162038;border-radius:5px">'
                            f'<span style="color:#ffd60a">{star}</span>'
                            f'<span style="font-size:12px;font-weight:{fw};color:{fc}">#{p["program_num"]} {p["horse_name"]}</span>'
                            f'<span style="font-size:10px;color:#ffd60a">{p["morning_line"] or "—"}</span>'
                            + role_html + bet_html
                            + grade_html + pnl_html
                            + form_badge(_psc.get("form","---")) + cb + vb
                            + "</div>"
                        )

                    # Pace scenario banner
                    pace_info = ""
                    if pace_scenario_name:
                        pace_scenario_label = pace_scenario_name.replace("_", " ")
                        bias_html = ('<span style="font-size:9px;color:#4a6080">' + pace_post_bias + '</span>') if pace_post_bias else ''
                        pace_info = '<div style="margin-top:6px;padding:5px 8px;background:#162038;border-radius:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap"><span style="background:' + scenario_color + '22;color:' + scenario_color + ';padding:1px 7px;border-radius:3px;font-size:9px;font-weight:700;border:0.5px solid ' + scenario_color + '44">' + pace_scenario_label + '</span><span style="font-size:10px;color:#4a6080">' + pace_scenario_notes[:80] + '</span>' + bias_html + '</div>'

                    # Race-level P&L summary
                    race_pnl_html = ""
                    if result_data:
                        scale = 0.50 / 2.0
                        race_returned = 0.0
                        race_wagered  = 4.50  # 3 picks x $1.50
                        for saved_rank, sp in race_picks.items():
                            if not sp.get("result") or sp["result"] == "MISS":
                                continue
                            prog = str(sp.get("program_num",""))
                            wnum = str(result_data.get("winner_num",""))
                            pnum = str(result_data.get("second_num","") or "")
                            snum = str(result_data.get("third_num","") or "")
                            if prog == wnum:
                                race_returned += (result_data.get("winner_win_payout") or 0) * scale
                                race_returned += (result_data.get("winner_place_payout") or 0) * scale
                                race_returned += (result_data.get("winner_show_payout") or 0) * scale
                            elif prog == pnum:
                                race_returned += (result_data.get("second_place_payout") or 0) * scale
                                race_returned += (result_data.get("second_show_payout") or 0) * scale
                            elif prog == snum:
                                race_returned += (result_data.get("third_show_payout") or 0) * scale
                        race_net = race_returned - race_wagered
                        pnl_color = "#00c896" if race_net >= 0 else "#ff4d6d"
                        # Check if exacta box hit
                        pick_nums = {str(sp.get("program_num","")) for sp in race_picks.values()}
                        ex_winner = str(result_data.get("winner_num",""))
                        ex_second = str(result_data.get("second_num","") or "")
                        ex_hit = (ex_winner in pick_nums and ex_second in pick_nums and ex_winner != ex_second) if ex_second else False
                        ex_pay = result_data.get("exacta_payout") or 0
                        # $0.50 box: payout is per $2 straight, box splits evenly
                        ex_returned = (ex_pay / 2.0) * 0.50 if ex_hit else 0
                        ex_cost = 3.00  # 6 combos x $0.50
                        ex_net = ex_returned - ex_cost
                        ex_color = "#00c896" if ex_hit else "#4a6080"
                        ex_str = f"EX BOX HIT! ${ex_returned:.2f} ({ex_net:+.2f})" if ex_hit else "EX miss"

                        # Trifecta box hit check
                        ex_third = str(result_data.get("third_num","") or "")
                        tri_hit = (ex_winner in pick_nums and ex_second in pick_nums and
                                   ex_third in pick_nums and len({ex_winner, ex_second, ex_third}) == 3)
                        tri_pay = result_data.get("trifecta_payout") or 0
                        tri_returned = (tri_pay / 6.0) * 0.50 if tri_hit else 0
                        tri_cost = 3.00  # 6 combos x $0.50
                        tri_net = tri_returned - tri_cost
                        tri_color = "#00c896" if tri_hit else "#4a6080"
                        tri_str = f"TRI BOX HIT! ${tri_returned:.2f} ({tri_net:+.2f})" if tri_hit else "TRI miss"

                        race_pnl_html = (
                            f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;'
                            f'padding:5px 8px;background:#162038;border-radius:4px;font-size:10px;flex-wrap:wrap">'
                            f'<span style="color:#4a6080">ATB:</span>'
                            f'<span style="color:{pnl_color};font-weight:700">{race_net:+.2f}</span>'
                            f'<span style="color:#4a6080">($4.50·${race_returned:.2f})</span>'
                            f'<span style="color:#4a6080">|</span>'
                            f'<span style="color:{ex_color};font-weight:700">{ex_str}</span>'
                            f'<span style="color:#4a6080">|</span>'
                            f'<span style="color:{tri_color};font-weight:700">{tri_str}</span>'
                            f'</div>'
                        )

                    pick_banner = f'<div style="background:#0f1729;border:0.5px solid #00c89633;border-radius:6px;padding:8px 10px;margin-bottom:10px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><span style="font-size:9px;color:#00c896;font-weight:700;letter-spacing:.1em">TOP 3 PICKS</span>{conf_str}</div><div style="display:flex;gap:6px;flex-wrap:wrap">{picks_html}</div>{pace_info}</div>'

                scr_badge = ('<span style="color:#ff4d6d;font-size:10px">' + str(len(scratched)) + ' SCR</span>') if scratched else ""
                race_html += (
                    '<div style="background:#0f1729;border:0.5px solid #1e2d4a;border-radius:8px;padding:12px 14px;margin-bottom:10px">'
                    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px">'
                    '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                    f'<span style="font-size:13px;font-weight:700;color:#fff">Race {race.get("race_num","?")}</span>'
                    + result_badge +
                    f'<span style="background:{surface_color}22;color:{surface_color};padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;border:0.5px solid {surface_color}44">{surface}</span>'
                    f'<span style="font-size:10px;color:#4a6080">{distance}</span>'
                    f'<span style="font-size:10px;color:#4a6080;font-style:italic">{cond_short}</span>'
                    '</div>'
                    f'<div style="display:flex;align-items:center;gap:8px"><span style="font-size:11px;color:#4a6080">Post: {post_time}</span><span style="font-size:10px;color:#4a6080">{len(active)} runners</span>'
                    + scr_badge +
                    '</div></div>'
                    + pick_banner
                )

                # Table header
                race_html += '<table style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr style="background:#162038"><th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400;width:20px">#</th><th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">HORSE</th><th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">JOCKEY</th><th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">TRAINER</th><th style="padding:5px 8px;text-align:right;color:#4a6080;font-size:9px;font-weight:400">ML</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">PACE</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">FORM</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">DAYS</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">J%</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">T%</th><th style="padding:5px 8px;text-align:left;color:#4a6080;font-size:9px;font-weight:400">SCORE</th><th style="padding:5px 8px;text-align:center;color:#4a6080;font-size:9px;font-weight:400">FLAGS</th></tr></thead><tbody>'

                for entry in entries:
                    entry = dict(entry)
                    prog  = entry["program_num"]
                    sc    = score_map.get(prog, {})
                    ss    = "opacity:0.3;text-decoration:line-through;" if entry["scratched"] else ""
                    is_winner = result_data and prog == result_data.get("winner_num")
                    is_top    = top_pick and prog == top_pick["program_num"]
                    rb        = "background:#00c89615;" if is_winner else ("background:#00c89608;" if is_top else "")
                    nc        = "#00c896" if (is_winner or is_top) else "#fff"
                    fw        = "700" if (is_winner or is_top) else "400"
                    hc        = "#00c896" if is_winner else "#fff" if is_top else "#c8d8f0"

                    # Fix jockey/trainer display
                    jockey  = (entry.get("jockey") or "—")
                    trainer = (entry.get("trainer") or "—")
                    if "Trainer:" in jockey:
                        parts   = jockey.split("Trainer:")
                        jockey  = parts[0].strip()
                        trainer = parts[1].strip() if len(parts) > 1 else trainer

                    # Form flags
                    flags_html = ""
                    if sc:
                        flags_html += class_badge(sc.get("class_change",""))
                        flags_html += trainer_badge(sc.get("trainer_hot",""))
                        flags_html += value_badge(sc.get("value",0))

                    j_pct_html = pct_display(sc.get("j_win_pct_db"), sc.get("j_win_pct_db") and 5 or 0) if sc else "—"
                    t_pct_html = pct_display(sc.get("t_win_pct_db"), sc.get("t_win_pct_db") and 5 or 0) if sc else "—"

                    days = sc.get("days_since") if sc else None
                    layoff = sc.get("layoff_flag","") if sc else ""
                    days_html = layoff_badge(layoff, days) if days else '<span style="color:#2a3a5a;font-size:10px">—</span>'

                    # Scratched horse styling: strikethrough + gray + SCR badge
                    is_scratched = bool(entry.get("scratched"))
                    if is_scratched:
                        scr_style = "text-decoration:line-through;opacity:0.45;"
                        scr_badge = ' <span style="color:#ff4d6d;font-size:9px;font-weight:700;letter-spacing:0.05em;background:#3a1020;padding:1px 5px;border-radius:3px;margin-left:4px">SCR</span>'
                        scr_color = "#6a7a90"
                    else:
                        scr_style = ""
                        scr_badge = ""
                        scr_color = hc

                    race_html += f'<tr style="border-bottom:0.5px solid #1e2d4a22;{ss}{rb}{scr_style}"><td style="padding:6px 8px;color:{nc};font-weight:{fw};font-family:Courier,monospace">{prog}</td><td style="padding:6px 8px;color:{scr_color};font-weight:{fw}">{entry["horse_name"]}{scr_badge}</td><td style="padding:6px 8px;color:#4a6080;font-size:10px">{jockey[:18]}</td><td style="padding:6px 8px;color:#4a6080;font-size:10px">{trainer[:18]}</td><td style="padding:6px 8px;text-align:right;color:#ffd60a;font-family:Courier,monospace">{entry.get("morning_line") or "—"}</td><td style="padding:6px 8px;text-align:center">{pace_badge(sc.get("pace_role","U")) if sc else "—"}</td><td style="padding:6px 8px;text-align:center">{form_badge(sc.get("form","---")) if sc else "—"}</td><td style="padding:6px 8px;text-align:center">{days_html}</td><td style="padding:6px 8px;text-align:center">{j_pct_html}</td><td style="padding:6px 8px;text-align:center">{t_pct_html}</td><td style="padding:6px 8px">{score_bar(sc["score"]) if sc else "—"}</td><td style="padding:6px 8px;text-align:center;display:flex;gap:3px;flex-wrap:wrap">{flags_html}</td></tr>'

                race_html += "</tbody></table></div>"
            race_html += "</div></div>"  # close track_{id} div + outer div


    # COLLAPSIBLE_SECTIONS: wrap each section with <details><summary>
    if bet_slate_html:
        bet_slate_html = (
            "<details style='margin:8px 0'>"
            "<summary style='cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;"
            "border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;"
            "color:#00c896;letter-spacing:.05em;list-style:none;"
            "user-select:none'>"
            "💰 TODAY'S BET SLATE "
            "<span style='font-size:9px;font-weight:400;color:#4a6080'>(click to expand/collapse)</span>"
            "</summary>" + bet_slate_html + "</details>"
        )
    if pick34_html:
        pick34_html = (
            "<details style='margin:8px 0'>"
            "<summary style='cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;"
            "border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;"
            "color:#00c896;letter-spacing:.05em;list-style:none;"
            "user-select:none'>"
            "🎯 PICK 3 / PICK 4 STRATEGY "
            "<span style='font-size:9px;font-weight:400;color:#4a6080'>(click to expand/collapse)</span>"
            "</summary>" + pick34_html + "</details>"
        )
    if high_picks_html:
        high_picks_html = (
            "<details style='margin:8px 0'>"
            "<summary style='cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;"
            "border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;"
            "color:#00c896;letter-spacing:.05em;list-style:none;"
            "user-select:none'>"
            "⭐ TODAY'S HIGH-CONFIDENCE PICKS "
            "<span style='font-size:9px;font-weight:400;color:#4a6080'>(click to expand/collapse)</span>"
            "</summary>" + high_picks_html + "</details>"
        )
    opt_html = locals().get('opt_html') or ''
    if opt_html:
        opt_html = (
            "<details style='margin:8px 0'>"
            "<summary style='cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;"
            "border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;"
            "color:#00c896;letter-spacing:.05em;list-style:none;"
            "user-select:none'>"
            "📊 OPTIMIZED STRATEGY "
            "<span style='font-size:9px;font-weight:400;color:#4a6080'>(click to expand/collapse)</span>"
            "</summary>" + opt_html + "</details>"
        )

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="300">
<title>Furbo Fox Racing</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0f1e;color:#c8d8f0;font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px}}
.header{{background:#0f1729;border-bottom:1px solid #1e2d4a;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.title{{font-size:18px;font-weight:800;color:#fff}}
.subtitle{{font-size:11px;color:#00c896;margin-top:2px}}
.stats{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;padding:16px 24px}}
.stat{{background:#0f1729;border:0.5px solid #1e2d4a;border-radius:8px;padding:12px 14px}}
.stat-label{{font-size:9px;color:#4a6080;letter-spacing:.1em;text-transform:uppercase;margin-bottom:5px}}
.stat-val{{font-size:20px;font-weight:800}}
.stat-sub{{font-size:10px;color:#4a6080;margin-top:3px}}
.main{{padding:0 24px 32px}}
.legend{{display:flex;gap:12px;flex-wrap:wrap;padding:0 24px 10px;font-size:10px;color:#4a6080;line-height:1.8}}
@media(max-width:900px){{
  .stats{{grid-template-columns:repeat(3,1fr)}}
  .header,.main,.legend{{padding-left:12px;padding-right:12px}}
  table th:nth-child(9),table td:nth-child(9),
  table th:nth-child(10),table td:nth-child(10){{display:none}}
}}
@media(max-width:700px){{
  .stats{{grid-template-columns:repeat(2,1fr)}}
  .legend{{display:none}}
  table th:nth-child(3),table td:nth-child(3),
  table th:nth-child(4),table td:nth-child(4),
  table th:nth-child(8),table td:nth-child(8),
  table th:nth-child(9),table td:nth-child(9),
  table th:nth-child(10),table td:nth-child(10),
  table th:nth-child(12),table td:nth-child(12){{display:none}}
}}
@media(max-width:480px){{
  table th:nth-child(3),table td:nth-child(3),
  table th:nth-child(4),table td:nth-child(4),
  table th:nth-child(7),table td:nth-child(7),
  table th:nth-child(8),table td:nth-child(8),
  table th:nth-child(9),table td:nth-child(9),
  table th:nth-child(10),table td:nth-child(10),
  table th:nth-child(12),table td:nth-child(12){{display:none}}
  table{{font-size:10px}}
}}
</style></head><body>
<div class="header">
  
    
    <div><div class="title">FURBO FOX RACING</div><div class="subtitle">US THOROUGHBRED · DAILY CARD · EXPERT HANDICAPPING</div></div>
    {baseline_banner_html}  <!-- BASELINE_BANNER_APPLIED -->
  </div>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <span style="background:#00c89622;color:#00c896;border:0.5px solid #00c89644;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:700">LIVE</span>
    <span style="font-size:10px;color:#4a6080">Updated: {now}</span>
    <div style="display:flex;gap:6px">
      <button onclick="collapseAll()" style="background:#162038;color:#4a6080;border:0.5px solid #1e2d4a;padding:4px 10px;border-radius:4px;font-size:10px;cursor:pointer">Collapse All</button>
      <button onclick="expandAll()" style="background:#162038;color:#00c896;border:0.5px solid #00c89644;padding:4px 10px;border-radius:4px;font-size:10px;cursor:pointer">Expand All</button>
    </div>
  </div>
</div>
<div class="stats">
  <div class="stat"><div class="stat-label">Tracks Today</div><div class="stat-val" style="color:#00c896">{len(tracks)}</div><div class="stat-sub">active tracks</div></div>
  <div class="stat"><div class="stat-label">Total Races</div><div class="stat-val" style="color:#fff">{total_races}</div><div class="stat-sub">on the card</div></div>
  <div class="stat"><div class="stat-label">Top Picks</div><div class="stat-val" style="color:#ffd60a">{top_picks_count}</div><div class="stat-sub">generated</div></div>
  <div class="stat"><div class="stat-label">Scratches</div><div class="stat-val" style="color:#ff4d6d">{total_scratches}</div><div class="stat-sub">today</div></div>
  <div class="stat"><div class="stat-label">Top Pick WIN%</div><div class="stat-val" style="color:#ffd60a">{agent_stats["top_pick_win_pct"]}%</div><div class="stat-sub">{agent_stats["total_races"]} graded races</div></div>
  <div class="stat"><div class="stat-label">Top Pick WPS%</div><div class="stat-val" style="color:#00c896">{agent_stats["top_pick_wps_pct"]}%</div><div class="stat-sub">win/place/show</div></div>
  <div class="stat"><div class="stat-label">Any Pick WPS%</div><div class="stat-val" style="color:#00c896">{agent_stats["any_pick_wps_pct"]}%</div><div class="stat-sub">1 of 3 in top 3</div></div>
</div>
{bet_slate_html}
{pick34_html}
{high_picks_html}
<div class="legend">
  <span>Pace: <span style="color:#ff4d6d">E-SPD</span>=early · <span style="color:#ff8c42">PRESS</span>=presser · <span style="color:#ffd60a">STALK</span>=stalker · <span style="color:#00c896">CLOSE</span>=closer</span>
  <span>Form: <span style="color:#00c896">1</span>=win · <span style="color:#ffd60a">2</span>=place · <span style="color:#ff8c42">3</span>=show · last 3 races</span>
  <span>Days: days since last race · <span style="color:#ff4d6d">red=60+d layoff</span> · <span style="color:#ffd60a">yellow=31-60d</span></span>
  <span>J%/T%: jockey/trainer win % from our data (shows after 5+ starts)</span>
  <span><span style="color:#00c896">↓CLASS</span>=dropping in class (positive) · <span style="color:#ff4d6d">↑CLASS</span>=rising (harder)</span>
  <span><span style="color:#00c896">🔥HOT</span>=trainer winning 25%+ last 14d · <span style="color:#00c896">VALUE</span>=overlaid horse</span>
</div>
<div class="main">{opt_html or ""}{('<details style="margin:8px 0"><summary style="cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;color:#00c896;letter-spacing:.05em;list-style:none;user-select:none">📈 PERFORMANCE BY TRACK & FIELD SIZE <span style="font-size:9px;font-weight:400;color:#4a6080">(click to expand/collapse)</span></summary>' + analysis_html + '</details>') if analysis_html else ''}{('<details style="margin:8px 0"><summary style="cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;color:#00c896;letter-spacing:.05em;list-style:none;user-select:none">💵 TRACK ROI BY CONFIDENCE <span style="font-size:9px;font-weight:400;color:#4a6080">(click to expand/collapse)</span></summary>' + track_roi_html + '</details>') if track_roi_html else ''}{('<details style="margin:8px 0"><summary style="cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;color:#00c896;letter-spacing:.05em;list-style:none;user-select:none">🎲 EXACTA-WORTHY & DAILY DOUBLE <span style="font-size:9px;font-weight:400;color:#4a6080">(click to expand/collapse)</span></summary>' + roi_html + '</details>') if roi_html else ''}{race_html}</div>
<script>
var STORAGE_KEY = "racing_open_tracks";
function _saveState() {{
  var open = [];
  document.querySelectorAll('[id^="track_"]').forEach(function(el) {{
    if (el.style.display !== "none") open.push(el.id.replace("track_", ""));
  }});
  try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(open)); }} catch(e) {{}}
}}
function _restoreState() {{
  var saved;
  try {{ saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }} catch(e) {{ return; }}
  saved.forEach(function(id) {{
    var el = document.getElementById("track_" + id);
    var arrow = document.getElementById("arrow_" + id);
    if (el) {{ el.style.display = "block"; }}
    if (arrow) {{ arrow.innerHTML = "&#9660;"; }}
  }});
}}
function toggleTrack(id) {{
  var el = document.getElementById("track_" + id);
  var arrow = document.getElementById("arrow_" + id);
  if (!el) return;
  if (el.style.display === "none") {{
    el.style.display = "block";
    if (arrow) arrow.innerHTML = "&#9660;";
  }} else {{
    el.style.display = "none";
    if (arrow) arrow.innerHTML = "&#9654;";
  }}
  _saveState();
}}
function collapseAll() {{
  document.querySelectorAll('[id^="track_"]').forEach(function(el) {{
    el.style.display = "none";
  }});
  document.querySelectorAll('[id^="arrow_"]').forEach(function(el) {{
    el.innerHTML = "&#9654;";
  }});
  _saveState();
}}
function expandAll() {{
  document.querySelectorAll('[id^="track_"]').forEach(function(el) {{
    el.style.display = "block";
  }});
  document.querySelectorAll('[id^="arrow_"]').forEach(function(el) {{
    el.innerHTML = "&#9660;";
  }});
  _saveState();
}}
document.addEventListener("DOMContentLoaded", _restoreState);
</script>
{jockey_html}</body></html>"""

    Path(DASHBOARD_OUTPUT).parent.mkdir(exist_ok=True)

    # ── EXACTA-WORTHY TRACKS ──────────────────────────────────────
    try:
        from db.database import get_exacta_track_stats
        ex_stats = get_exacta_track_stats(min_races=10)
        if ex_stats:
            bet_tracks  = [s for s in ex_stats if s["exacta_worthy"]]
            watch_tracks = [s for s in ex_stats if not s["exacta_worthy"] and s["roi"] > -30]
            total_races  = sum(s["races"] for s in ex_stats)
            total_hits   = sum(s["hits"]  for s in ex_stats)
            total_wag    = sum(s["wagered"] for s in ex_stats)
            total_ret    = sum(s["returned"] for s in ex_stats)
            overall_roi  = round((total_ret - total_wag) / total_wag * 100, 1) if total_wag else 0
            overall_hit  = round(100.0 * total_hits / total_races, 1) if total_races else 0

            html += "<details style='margin:8px 0'>"
            html += ("<summary style='cursor:pointer;background:#0d1525;border:0.5px solid #1e2d4a;"
                     "border-radius:6px;padding:10px 14px;font-size:11px;font-weight:700;"
                     "color:#00c896;letter-spacing:.05em;list-style:none;user-select:none'>"
                     "&#127922; EXACTA BOX PERFORMANCE &mdash; TOP 3 PICKS "
                     "<span style='font-size:9px;font-weight:400;color:#4a6080'>"
                     "(click to expand/collapse)</span></summary>")
            html += "<div style='padding:14px;background:#0a1020;border:0.5px solid #1e2d4a;border-top:none;border-radius:0 0 6px 6px'>"

            # Summary bar
            roi_c = "#00c896" if overall_roi >= 0 else "#ff4d6d"
            html += ("<div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px'>"
                     "<div style='background:#162038;border-radius:6px;padding:8px 14px'>"
                     "<div style='font-size:9px;color:#4a6080'>TRACKS TRACKED</div>"
                     "<div style='font-size:18px;font-weight:700;color:#c8d8f0'>%d</div></div>"
                     "<div style='background:#162038;border-radius:6px;padding:8px 14px'>"
                     "<div style='font-size:9px;color:#4a6080'>OVERALL HIT%%</div>"
                     "<div style='font-size:18px;font-weight:700;color:#c8d8f0'>%.1f%%</div></div>"
                     "<div style='background:#162038;border-radius:6px;padding:8px 14px'>"
                     "<div style='font-size:9px;color:#4a6080'>OVERALL ROI</div>"
                     "<div style='font-size:18px;font-weight:700;color:%s'>%+.1f%%</div></div>"
                     "<div style='background:#162038;border-radius:6px;padding:8px 14px'>"
                     "<div style='font-size:9px;color:#4a6080'>BET TRACKS</div>"
                     "<div style='font-size:18px;font-weight:700;color:#00c896'>%d</div></div>"
                     "</div>") % (len(ex_stats), overall_hit, roi_c, overall_roi, len(bet_tracks))

            def _ex_table(tracks, title, title_color):
                if not tracks:
                    return ""
                t = ("<div style='font-size:10px;font-weight:700;color:%s;"
                     "letter-spacing:.05em;margin-bottom:6px'>%s</div>"
                     "<table style='width:100%%;border-collapse:collapse;"
                     "font-size:11px;margin-bottom:14px;table-layout:fixed'>"
                     "<colgroup>"
                     "<col style='width:35%%'><col style='width:12%%'>"
                     "<col style='width:13%%'><col style='width:22%%'>"
                     "<col style='width:18%%'>"
                     "</colgroup>"
                     "<thead><tr style='color:#4a6080;border-bottom:0.5px solid #1e2d4a'>"
                     "<th style='padding:4px 8px;text-align:left'>TRACK</th>"
                     "<th style='padding:4px 8px;text-align:right'>RACES</th>"
                     "<th style='padding:4px 8px;text-align:right'>HIT%%</th>"
                     "<th style='padding:4px 8px;text-align:right'>AVG PAYOUT</th>"
                     "<th style='padding:4px 8px;text-align:right'>ROI</th>"
                     "</tr></thead><tbody>") % (title_color, title)
                for s in tracks:
                    rc = "#00c896" if s["roi"] > 0 else "#ffd60a" if s["roi"] > -20 else "#ff4d6d"
                    t += ("<tr style='border-bottom:0.5px solid #1e2d4a22'>"
                          "<td style='padding:4px 8px;color:#c8d8f0'>%s</td>"
                          "<td style='padding:4px 8px;text-align:right;color:#4a6080'>%d</td>"
                          "<td style='padding:4px 8px;text-align:right;color:#c8d8f0'>%.1f%%</td>"
                          "<td style='padding:4px 8px;text-align:right;color:#c8d8f0'>$%.2f</td>"
                          "<td style='padding:4px 8px;text-align:right;color:%s;font-weight:700'>%+.1f%%</td>"
                          "</tr>") % (s["track"], s["races"], s["hit_pct"],
                                      s["avg_per_hit"], rc, s["roi"])
                t += "</tbody></table>"
                return t

            if bet_tracks:
                html += _ex_table(bet_tracks, "&#9989; BET TRACKS (positive ROI)", "#00c896")
            if watch_tracks:
                html += _ex_table(watch_tracks, "&#128065; WATCH TRACKS (ROI > -30%)", "#ffd60a")

            html += ("<div style='font-size:9px;color:#4a6080;margin-top:4px'>"
                     "Exacta box = top-3 picks in any order &middot; "
                     "$6/race (6 combos &times; $1) &middot; "
                     "Tracks below -30% ROI hidden &mdash; not actionable</div>")
            html += "</div></details>"
    except Exception:
        pass

    # ── TRACK BIAS ALERTS ─────────────────────────────────────────
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
                html += '<div style="margin:5px 0;color:#ddd">'
                html += '%s: <span style="color:#ffaa00;font-weight:bold">%s BIAS</span> ' % (tc, b["bias"])
                html += '(Inside: %.1f%% | Outside: %.1f%%)</div>' % (b["inside_wp"], b["outside_wp"])
            html += '</div>'
    except Exception:
        pass
    html += '</details>'


    # ── DAILY DOUBLE PERFORMANCE BY TRACK ───────────────────────────────────
    try:
        from db.database import get_dd_track_stats_hybrid, get_dd_spot_checks
        dd_stats = get_dd_track_stats_hybrid(min_dds_measured=10, min_dds_modeled=5)
        spot_checks = get_dd_spot_checks(limit=40)

        # Calibration multipliers per track (actual/model ratio)
        _cal = {}
        for sc in spot_checks:
            if sc["modeled"] > 0 and sc["measured"] > 0:
                _cal.setdefault(sc["track"], []).append(sc["measured"] / sc["modeled"])
        track_cal = {t: round(sum(v)/len(v),1) for t,v in _cal.items() if len(v) >= 3}

        if dd_stats:
            dd_measured = [s for s in dd_stats if s.get("source") == "measured"]
            dd_modeled  = [s for s in dd_stats if s.get("source") != "measured"]
            dd_bet      = [s for s in dd_measured if s.get("dd_worthy")]
            dd_watch    = [s for s in dd_measured if not s.get("dd_worthy") and s["hits"] > 0]
            dd_nodata   = [s for s in dd_measured if s["hits"] == 0]

            m_w   = sum(s["wagered"]  for s in dd_measured)
            m_r   = sum(s["returned"] for s in dd_measured)
            m_h   = sum(s["hits"]     for s in dd_measured)
            m_d   = sum(s["dds"]      for s in dd_measured)
            m_roi = (m_r - m_w) / m_w * 100 if m_w else 0

            html += "<details style='margin:8px 0'>"
            html += ("<summary style='cursor:pointer;background:#0d1525;"
                     "border:0.5px solid #1e2d4a;border-radius:6px;padding:10px 14px;"
                     "font-size:11px;font-weight:700;color:#00c896;"
                     "letter-spacing:.05em;list-style:none;user-select:none'>"
                     "&#128197; DAILY DOUBLE PERFORMANCE "
                     "<span style='font-size:9px;font-weight:400;color:#4a6080'>"
                     "(click to expand/collapse)</span></summary>")
            html += ("<div style='padding:14px;background:#0a1020;"
                     "border:0.5px solid #1e2d4a;border-top:none;"
                     "border-radius:0 0 6px 6px'>")

            # Summary tiles — measured only
            roi_c = "#00c896" if m_roi >= 0 else "#ff4d6d"
            html += "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px'>"
            for label, val in [
                ("MEASURED DDs",    str(m_d)),
                ("MEASURED TRACKS", str(len(dd_measured))),
                ("HIT RATE",        "%.1f%%" % (m_h/m_d*100 if m_d else 0)),
                ("MEASURED ROI",    "%+.1f%%" % m_roi),
                ("BET TRACKS",      str(len(dd_bet))),
            ]:
                vc = roi_c if label == "MEASURED ROI" else "#00c896" if label == "BET TRACKS" else "#c8d8f0"
                html += ("<div style='background:#162038;border-radius:6px;padding:8px 14px'>"
                         "<div style='font-size:9px;color:#4a6080'>%s</div>"
                         "<div style='font-size:18px;font-weight:700;color:%s'>%s</div>"
                         "</div>") % (label, vc, val)
            html += "</div>"

            # Table builder
            def _dd_tbl(rows, title, tc):
                if not rows: return ""
                out = ("<div style='font-size:10px;font-weight:700;color:%s;"
                       "letter-spacing:.05em;margin-bottom:6px'>%s</div>"
                       "<table style='width:100%%;border-collapse:collapse;"
                       "font-size:11px;margin-bottom:14px;table-layout:fixed'>"
                       "<colgroup>"
                       "<col style='width:26%%'><col style='width:10%%'>"
                       "<col style='width:9%%'><col style='width:11%%'>"
                       "<col style='width:16%%'><col style='width:14%%'>"
                       "<col style='width:14%%'>"
                       "</colgroup>"
                       "<thead><tr style='color:#4a6080;"
                       "border-bottom:0.5px solid #1e2d4a'>"
                       "<th style='padding:4px 6px;text-align:left'>TRACK</th>"
                       "<th style='padding:4px 6px;text-align:center'>SRC</th>"
                       "<th style='padding:4px 6px;text-align:right'>DDs</th>"
                       "<th style='padding:4px 6px;text-align:right'>HIT%%</th>"
                       "<th style='padding:4px 6px;text-align:right'>AVG PAY</th>"
                       "<th style='padding:4px 6px;text-align:right'>CAL</th>"
                       "<th style='padding:4px 6px;text-align:right'>ROI</th>"
                       "</tr></thead><tbody>") % (tc, title)
                for s in rows:
                    rc  = "#00c896" if s["roi"] > 0 else "#ffd60a" if s["roi"] > -30 else "#ff4d6d"
                    src = s.get("source","modeled")
                    sc  = "#00c896" if src == "measured" else "#ffd60a"
                    cal = track_cal.get(s["track"])
                    cal_s = ("%+.1fx" % cal) if cal else "—"
                    cal_c = "#00c896" if cal and cal > 1.5 else "#ffd60a" if cal else "#4a6080"
                    out += ("<tr style='border-bottom:0.5px solid #1e2d4a22'>"
                            "<td style='padding:4px 6px;color:#c8d8f0;"
                            "word-break:break-word'>%s</td>"
                            "<td style='padding:4px 6px;text-align:center;"
                            "color:%s;font-size:9px;font-weight:700'>%s</td>"
                            "<td style='padding:4px 6px;text-align:right;"
                            "color:#4a6080'>%d</td>"
                            "<td style='padding:4px 6px;text-align:right;"
                            "color:#c8d8f0'>%.1f%%</td>"
                            "<td style='padding:4px 6px;text-align:right;"
                            "color:#c8d8f0'>$%.2f</td>"
                            "<td style='padding:4px 6px;text-align:right;"
                            "color:%s;font-weight:700'>%s</td>"
                            "<td style='padding:4px 6px;text-align:right;"
                            "color:%s;font-weight:700'>%+.1f%%</td>"
                            "</tr>") % (
                                s["track"], sc, src.upper()[:3],
                                s["dds"], s["hit_pct"], s["avg_per_hit"],
                                cal_c, cal_s, rc, s["roi"])
                out += "</tbody></table>"
                return out

            if dd_bet:
                html += _dd_tbl(dd_bet, "&#9989; BET TRACKS", "#00c896")
            if dd_watch:
                html += _dd_tbl(dd_watch, "&#128065; WATCH TRACKS (has hits)", "#ffd60a")
            if dd_nodata:
                html += _dd_tbl(dd_nodata, "&#128202; NO HITS YET (building data)", "#4a6080")
            if dd_modeled:
                html += _dd_tbl(dd_modeled, "&#9881; MODELED (under 10 measured DDs)", "#2a4060")

            # Cal note
            if track_cal:
                html += ("<div style='font-size:9px;color:#4a6080;margin-bottom:10px'>"
                         "CAL = avg actual&divide;model over last 40 DDs. "
                         "+2.0x means track pays 2x the model estimate &mdash; "
                         "model underestimates value at this track."
                         "</div>")

            # Recent 10 spot checks
            recent10 = spot_checks[:10]
            if recent10:
                html += ("<div style='font-size:10px;font-weight:700;color:#4a6080;"
                         "letter-spacing:.05em;margin-bottom:6px'>"
                         "RECENT MODEL vs ACTUAL (last 10)</div>"
                         "<table style='width:100%;border-collapse:collapse;"
                         "font-size:11px;table-layout:fixed'>"
                         "<colgroup>"
                         "<col style='width:28%'><col style='width:7%'>"
                         "<col style='width:12%'><col style='width:12%'>"
                         "<col style='width:16%'><col style='width:16%'>"
                         "<col style='width:9%'>"
                         "</colgroup>"
                         "<thead><tr style='color:#4a6080;"
                         "border-bottom:0.5px solid #1e2d4a'>"
                         "<th style='padding:3px 6px;text-align:left'>TRACK</th>"
                         "<th style='padding:3px 6px;text-align:center'>R</th>"
                         "<th style='padding:3px 6px;text-align:right'>W1</th>"
                         "<th style='padding:3px 6px;text-align:right'>W2</th>"
                         "<th style='padding:3px 6px;text-align:right'>MODEL</th>"
                         "<th style='padding:3px 6px;text-align:right'>ACTUAL</th>"
                         "<th style='padding:3px 6px;text-align:right'>DIFF</th>"
                         "</tr></thead><tbody>")
                for sc in recent10:
                    diff = sc["diff_pct"]
                    dc = "#00c896" if abs(diff) < 20 else "#ffd60a" if abs(diff) < 60 else "#ff4d6d"
                    html += ("<tr style='border-bottom:0.5px solid #1e2d4a22'>"
                             "<td style='padding:3px 6px;color:#c8d8f0;"
                             "word-break:break-word'>%s</td>"
                             "<td style='padding:3px 6px;text-align:center;"
                             "color:#4a6080'>%d</td>"
                             "<td style='padding:3px 6px;text-align:right;"
                             "color:#888'>$%.2f</td>"
                             "<td style='padding:3px 6px;text-align:right;"
                             "color:#888'>$%.2f</td>"
                             "<td style='padding:3px 6px;text-align:right;"
                             "color:#4a6080'>$%.2f</td>"
                             "<td style='padding:3px 6px;text-align:right;"
                             "color:#c8d8f0;font-weight:700'>$%.2f</td>"
                             "<td style='padding:3px 6px;text-align:right;"
                             "color:%s'>%+.0f%%</td>"
                             "</tr>") % (sc["track"], sc["leg2_race"],
                                         sc["w1"], sc["w2"], sc["modeled"],
                                         sc["measured"], dc, diff)
                html += "</tbody></table>"

            html += ("<div style='font-size:9px;color:#4a6080;margin-top:8px'>"
                     "$1 DD on rank-1 pick &middot; "
                     "MEASURED = real payout data &middot; "
                     "MOD = theoretical estimate &middot; "
                     "Tracks with 0 hits shown for data-building transparency"
                     "</div>")
            html += "</div></details>"
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("DD section render failed: %s" % _e)

    Path(DASHBOARD_OUTPUT).write_text(html)


if __name__ == "__main__":
    build_dashboard()
    print(f"Dashboard saved → {DASHBOARD_OUTPUT}")
    # Open via http server if running, otherwise file://
    import socket
    try:
        s = socket.create_connection(("localhost", 8081), timeout=1)
        s.close()
        webbrowser.open("http://localhost:8081/racing.html")
    except Exception:
        webbrowser.open("file://" + os.path.abspath(DASHBOARD_OUTPUT))


def _build_pick34_panels():
    """Build Pick 3 and Pick 4 strategy panels for the dashboard."""
    try:
        from db.database import get_conn
        with get_conn() as conn:
            # Per-bet-type stats from agent_pick_sequences
            stats = {}
            for bet_type in ("PICK3", "PICK4"):
                row = conn.execute("""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN recommended=1 THEN 1 ELSE 0 END) AS recommended,
                        SUM(CASE WHEN hit=1 THEN 1 ELSE 0 END) AS hits,
                        SUM(CASE WHEN recommended=1 THEN cost ELSE 0 END) AS wagered,
                        SUM(CASE WHEN hit=1 THEN actual_payout ELSE 0 END) AS returned
                    FROM agent_pick_sequences
                    WHERE bet_type=?
                """, (bet_type,)).fetchone()
                stats[bet_type] = dict(row) if row else {}

            # Today's recommended sequences
            from datetime import date as _date
            today = _date.today().isoformat()
            today_rows = conn.execute("""
                SELECT aps.bet_type, aps.track_code,
                       COALESCE(
                           (SELECT DISTINCT r.track_name FROM races r
                            WHERE r.track_code=aps.track_code LIMIT 1),
                           aps.track_code
                       ) AS track_name,
                       aps.start_race_num,
                       aps.sequence_prob, aps.est_payout,
                       aps.expected_value, aps.cost
                FROM agent_pick_sequences aps
                WHERE aps.race_date=? AND aps.recommended=1
                ORDER BY aps.expected_value DESC
                LIMIT 20
            """, (today,)).fetchall()
            today_recs = [dict(r) for r in today_rows]

        return stats, today_recs
    except Exception as _e:
        return {}, []


def _render_pick34_panel(bet_type: str, stats: dict, today_recs: list,
                         threshold: int):
    """Render one strategy panel (Pick 3 or Pick 4)."""
    label = "PICK 3" if bet_type == "PICK3" else "PICK 4"
    cost = 4.00 if bet_type == "PICK3" else 8.00
    s = stats.get(bet_type, {})
    total = s.get("total", 0) or 0
    rec = s.get("recommended", 0) or 0
    hits = s.get("hits", 0) or 0
    wagered = s.get("wagered", 0) or 0
    returned = s.get("returned", 0) or 0
    net = returned - wagered
    roi = (100.0 * net / wagered) if wagered else 0

    # Baseline progress
    progress_pct = min(100.0, 100.0 * rec / threshold) if threshold else 0
    baseline_html = ""
    if rec < threshold:
        baseline_html = (
            f'<div style="background:#1a1003;border:1px solid #ff8c00;'
            f'border-radius:4px;padding:6px 10px;margin-bottom:10px;'
            f'font-size:10px;color:#ffb86b">'
            f'⚠ {label} BASELINE: {rec} / {threshold} sequences '
            f'recommended ({progress_pct:.1f}%). Not yet publishing-ready.'
            f'</div>'
        )

    today_html = ""
    if today_recs:
        seq_rows = ""
        for r in today_recs:
            if r["bet_type"] != bet_type:
                continue
            seq_rows += (
                f'<tr><td style="padding:4px 8px;color:#c8d8f0">{r["track_name"]}</td>'
                f'<td style="padding:4px 8px;text-align:center;color:#4a6080">R{r["start_race_num"]}-{r["start_race_num"] + (2 if bet_type == "PICK3" else 3)}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#4a6080">{(r["sequence_prob"] or 0)*100:.2f}%</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#4a6080">${r["est_payout"] or 0:.2f}</td>'
                f'<td style="padding:4px 8px;text-align:right;color:#00c896;font-weight:700">${r["expected_value"] or 0:+.2f}</td></tr>'
            )
        if seq_rows:
            today_html = (
                '<table style="width:100%;border-collapse:collapse;font-size:10px;margin-top:8px">'
                '<thead><tr style="background:#162038">'
                '<th style="padding:4px 8px;text-align:left;color:#4a6080">TRACK</th>'
                '<th style="padding:4px 8px;text-align:center;color:#4a6080">RACES</th>'
                '<th style="padding:4px 8px;text-align:right;color:#4a6080">SEQ PROB</th>'
                '<th style="padding:4px 8px;text-align:right;color:#4a6080">EST PAYOUT</th>'
                '<th style="padding:4px 8px;text-align:right;color:#4a6080">EV</th>'
                '</tr></thead><tbody>' + seq_rows + '</tbody></table>'
            )

    color = "#00c896" if net >= 0 else "#ff4d6d"
    return (
        f'<div style="margin:0 0 16px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:14px 18px">'
        f'<div style="font-size:11px;font-weight:700;color:#00c896;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:0.5px solid #00c89633">'
        f'{label} STRATEGY — ${cost:.2f}/sequence — TOP 2 PER LEG'
        f'</div>'
        f'{baseline_html}'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px">'
        f'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">SEQUENCES</div><div style="font-size:14px;font-weight:700;color:#fff">{rec}</div></div>'
        f'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">HITS</div><div style="font-size:14px;font-weight:700;color:#fff">{hits}</div></div>'
        f'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">NET P&L</div><div style="font-size:14px;font-weight:700;color:{color}">${net:+.2f}</div></div>'
        f'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">ROI</div><div style="font-size:14px;font-weight:700;color:{color}">{roi:+.1f}%</div></div>'
        f'</div>'
        f'{today_html}'
        f'</div>'
    )


def build_pick34_section():
    """Top-level: returns the combined Pick 3 + Pick 4 HTML for dashboard."""
    stats, today_recs = _build_pick34_panels()
    p3 = _render_pick34_panel("PICK3", stats, today_recs, threshold=300)
    p4 = _render_pick34_panel("PICK4", stats, today_recs, threshold=200)
    return p3 + p4

# PHASE3_PICK34_PANELS_APPLIED

