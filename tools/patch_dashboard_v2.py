"""Dashboard V2 patch — collapsible sections + jockey leaderboard + ML accuracy.

Strategy:
- Collapsible sections: inject JS toggle (safer than patching f-strings directly)
- Jockey leaderboard: derived from entries + results tables (no jockey_stats)
- ML accuracy: agent win% vs ML favorite win%
- Pace scenario: SKIPPED (not stored in entries table)

Run from racing-agent root:
    venv/bin/python3 tools/patch_dashboard_v2.py
"""

import ast
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
BUILDER = ROOT / "dashboard" / "builder.py"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dash_v2")


def backup(path, suffix=""):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}{suffix}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")


# =========================================================================
# New query functions
# =========================================================================

QUERY_FUNCS = '''
# ── DASHBOARD V2 ANALYTICS ─────────────────────── DASHBOARD_V2_APPLIED ──

def get_jockey_leaderboard(days_back=30, min_starts=5, top_n=20):
    """Top jockeys derived from entries + results. No jockey_stats table needed."""
    try:
        from db.database import get_conn
        import datetime as _dt
        cutoff = (_dt.date.today() - _dt.timedelta(days=days_back)).isoformat()
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    e.jockey,
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
                r['win_pct']  = round(100.0 * r['wins']  / r['starts'], 1) if r['starts'] else 0
                r['itm_pct']  = round(100.0 * (r['wins'] + r['places'] + r['shows']) / r['starts'], 1) if r['starts'] else 0
                out.append(r)
            return out
    except Exception as _e:
        return []


def get_ml_accuracy():
    """Agent pick #1 win% vs ML favorite win%."""
    try:
        from db.database import get_conn
        with get_conn() as conn:
            # Agent accuracy
            ag = conn.execute("""
                SELECT COUNT(*) AS races,
                       SUM(CASE WHEN ap.finish_position=1 THEN 1 ELSE 0 END) AS wins
                FROM agent_picks ap
                WHERE ap.rank=1 AND ap.finish_position IS NOT NULL
                  AND ap.data_quality IN ('OK','UNVERIFIED')
            """).fetchone()
            # ML favorite: lowest odds entry per race
            ml = conn.execute("""
                WITH parsed AS (
                    SELECT e.race_id, e.program_num,
                        CASE
                            WHEN e.morning_line LIKE '%/%' THEN
                                CAST(SUBSTR(e.morning_line,1,INSTR(e.morning_line,'/')-1) AS REAL) /
                                NULLIF(CAST(SUBSTR(e.morning_line,INSTR(e.morning_line,'/')+1) AS REAL),0)
                            ELSE CAST(e.morning_line AS REAL)
                        END AS odds_dec,
                        ROW_NUMBER() OVER (PARTITION BY e.race_id ORDER BY
                            CASE
                                WHEN e.morning_line LIKE '%/%' THEN
                                    CAST(SUBSTR(e.morning_line,1,INSTR(e.morning_line,'/')-1) AS REAL) /
                                    NULLIF(CAST(SUBSTR(e.morning_line,INSTR(e.morning_line,'/')+1) AS REAL),0)
                                ELSE CAST(e.morning_line AS REAL)
                            END ASC
                        ) AS rn
                    FROM entries e
                    WHERE e.morning_line IS NOT NULL AND e.morning_line != ''
                      AND e.scratched = 0
                )
                SELECT COUNT(*) AS races,
                       SUM(CASE WHEN p.program_num = res.winner_num THEN 1 ELSE 0 END) AS wins
                FROM parsed p
                JOIN results res ON res.race_id = p.race_id
                WHERE p.rn = 1
            """).fetchone()
            ag_races  = ag[0] if ag else 0
            ag_wins   = ag[1] if ag else 0
            ml_races  = ml[0] if ml else 0
            ml_wins   = ml[1] if ml else 0
            return {
                'agent_races':   ag_races,
                'agent_wins':    ag_wins,
                'agent_win_pct': round(100.0 * ag_wins / ag_races, 1) if ag_races else 0,
                'ml_races':      ml_races,
                'ml_wins':       ml_wins,
                'ml_win_pct':    round(100.0 * ml_wins / ml_races, 1) if ml_races else 0,
            }
    except Exception as _e:
        return {}


def render_jockey_section():
    """Build jockey leaderboard + ML accuracy HTML block."""
    jockeys = get_jockey_leaderboard()
    ml      = get_ml_accuracy()

    # Jockey rows
    if jockeys:
        rows = ""
        for j in jockeys:
            clr = '#00c896' if j['win_pct'] >= 20 else '#c8d8f0'
            rows += (
                f'<tr style="border-bottom:0.5px solid #1e2d4a22">'
                f'<td style="padding:5px 8px;color:#c8d8f0">{j["jockey"]}</td>'
                f'<td style="padding:5px 8px;text-align:right;color:#4a6080">{j["starts"]}</td>'
                f'<td style="padding:5px 8px;text-align:right;color:{clr};font-weight:700">{j["win_pct"]:.1f}%</td>'
                f'<td style="padding:5px 8px;text-align:right;color:#ffd60a">{j["itm_pct"]:.1f}%</td>'
                f'<td style="padding:5px 8px;text-align:right;color:#4a6080">{j["wins"]}/{j["places"]}/{j["shows"]}</td>'
                f'</tr>'
            )
    else:
        rows = '<tr><td colspan="5" style="color:#4a6080;padding:10px">No jockey data yet — accumulates from results</td></tr>'

    # ML accuracy
    ag_pct   = ml.get('agent_win_pct', 0)
    ml_pct   = ml.get('ml_win_pct', 0)
    edge     = round(ag_pct - ml_pct, 1)
    edge_clr = '#00c896' if edge >= 0 else '#ff4d6d'

    return (
        '<div class="dash-section" id="section-jockey">'
        '<div class="section-header" onclick="toggleSection(\'section-jockey\')" style="cursor:pointer;'
        'background:#0f1829;border:0.5px solid #1e2d4a;border-radius:8px;padding:12px 16px;'
        'display:flex;justify-content:space-between;align-items:center;margin-bottom:0">'
        '<span style="font-size:12px;font-weight:700;color:#00c896;letter-spacing:.05em">'
        '🏇 JOCKEY LEADERBOARD — LAST 30 DAYS</span>'
        '<span class="chevron" style="color:#4a6080;font-size:10px">▾</span></div>'
        '<div class="section-body" style="background:#0a1020;border:0.5px solid #1e2d4a;'
        'border-top:none;border-radius:0 0 8px 8px;padding:14px;display:none">'

        # Jockey table
        '<table style="width:100%;border-collapse:collapse;font-size:11px;margin-bottom:20px">'
        '<thead><tr style="color:#4a6080;border-bottom:0.5px solid #1e2d4a">'
        '<th style="padding:5px 8px;text-align:left;font-weight:600">JOCKEY</th>'
        '<th style="padding:5px 8px;text-align:right;font-weight:600">STARTS</th>'
        '<th style="padding:5px 8px;text-align:right;font-weight:600">WIN%</th>'
        '<th style="padding:5px 8px;text-align:right;font-weight:600">ITM%</th>'
        '<th style="padding:5px 8px;text-align:right;font-weight:600">W/P/S</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'

        # ML accuracy tiles
        '<div style="font-size:10px;font-weight:700;color:#7eb6ff;letter-spacing:.05em;margin-bottom:8px">'
        '📊 MODEL vs MORNING LINE ACCURACY</div>'
        '<div style="display:flex;gap:10px;flex-wrap:wrap">'
        f'<div style="background:#162038;border-radius:6px;padding:10px 14px;min-width:120px">'
        f'<div style="font-size:9px;color:#4a6080;margin-bottom:4px">ML FAV WIN%</div>'
        f'<div style="font-size:20px;font-weight:700;color:#c8d8f0">{ml_pct:.1f}%</div>'
        f'<div style="font-size:9px;color:#4a6080">{ml.get("ml_races",0)} races</div></div>'
        f'<div style="background:#162038;border-radius:6px;padding:10px 14px;min-width:120px">'
        f'<div style="font-size:9px;color:#4a6080;margin-bottom:4px">AGENT PICK #1 WIN%</div>'
        f'<div style="font-size:20px;font-weight:700;color:#c8d8f0">{ag_pct:.1f}%</div>'
        f'<div style="font-size:9px;color:#4a6080">{ml.get("agent_races",0)} races</div></div>'
        f'<div style="background:#162038;border-radius:6px;padding:10px 14px;min-width:120px">'
        f'<div style="font-size:9px;color:#4a6080;margin-bottom:4px">AGENT EDGE vs ML</div>'
        f'<div style="font-size:20px;font-weight:700;color:{edge_clr}">{edge:+.1f}%</div>'
        f'<div style="font-size:9px;color:#4a6080">vs ML favorite</div></div>'
        '</div>'

        '</div></div>'  # section-body, section-jockey
    )

'''


# =========================================================================
# JS toggle script to inject into HTML template
# =========================================================================

JS_TOGGLE = '''
<script>
function toggleSection(id) {
    const sec = document.getElementById(id);
    if (!sec) return;
    const body = sec.querySelector('.section-body');
    const chev = sec.querySelector('.chevron');
    if (!body) return;
    const open = body.style.display !== 'none';
    body.style.display = open ? 'none' : 'block';
    if (chev) chev.textContent = open ? '▾' : '▴';
}

// Wrap existing sections with toggle behavior
document.addEventListener('DOMContentLoaded', function() {
    const sectionTitles = [
        "TODAY\\'S BET SLATE",
        "PICK 3 STRATEGY",
        "PICK 4 STRATEGY",
        "HIGH-CONFIDENCE PICKS",
        "OPTIMIZED STRATEGY",
        "PERFORMANCE BY TRACK",
        "TRACK ROI BY CONFIDENCE",
        "EXACTA-WORTHY TRACKS",
        "DAILY DOUBLE PERFORMANCE",
        "RECENT MODELED"
    ];
    // Find all section wrapper divs and make headers clickable
    document.querySelectorAll('[data-section]').forEach(function(sec) {
        const header = sec.querySelector('[data-section-header]');
        const body   = sec.querySelector('[data-section-body]');
        if (header && body) {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                const open = body.style.display !== 'none';
                body.style.display = open ? 'none' : '';
            });
        }
    });
});
</script>
'''


def patch_builder():
    src = BUILDER.read_text()

    if "DASHBOARD_V2_APPLIED" in src:
        logger.info("Already patched; skipping")
        return

    backup(BUILDER, suffix="_v2")

    # ── Step 1: Inject query functions before build_dashboard() ──────────
    anchor = "def build_dashboard():"
    if anchor not in src:
        logger.error("FAIL: build_dashboard() anchor not found")
        raise SystemExit(1)
    src = src.replace(anchor, QUERY_FUNCS + anchor, 1)
    logger.info("  Step 1: Query functions injected")

    # ── Step 2: Call render_jockey_section() inside build_dashboard ──────
    # Find the opt_stats / roi_stats call area and add jockey_html computation
    old_roi = "    opt_stats    = get_optimized_roi_stats()"
    new_roi = (
        "    opt_stats    = get_optimized_roi_stats()\n"
        "    jockey_html  = render_jockey_section()"
    )
    if old_roi in src:
        src = src.replace(old_roi, new_roi, 1)
        logger.info("  Step 2: jockey_html computation added")
    else:
        # Fallback anchor
        old_roi2 = "    picks_today  = get_todays_agent_picks()"
        new_roi2 = "    picks_today  = get_todays_agent_picks()\n    jockey_html  = render_jockey_section()"
        if old_roi2 in src:
            src = src.replace(old_roi2, new_roi2, 1)
            logger.info("  Step 2 (fallback): jockey_html computation added")
        else:
            logger.warning("  Step 2: anchor not found — jockey_html won't render")
            # Set a safe default so template doesn't crash
            old_html_start = '    html = f"""'
            if old_html_start in src:
                src = src.replace(old_html_start,
                                  "    jockey_html = ''\n    html = f\"\"\"", 1)

    # ── Step 3: Inject {jockey_html} + JS into HTML template ─────────────
    old_closing = "</body>\\n</html>"
    new_closing  = "{jockey_html}\\n" + JS_TOGGLE.replace('{', '{{').replace('}', '}}').replace('{{jockey_html}}', '{jockey_html}') + "\\n</body>\\n</html>"

    # Safer: find the literal string in the f-string template
    # The builder uses triple-quoted f-string for HTML
    old_body_tag = "    </body>\\n</html>"
    if old_body_tag in src:
        src = src.replace(old_body_tag,
                          "    {jockey_html}\\n" +
                          JS_TOGGLE.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'") +
                          "\\n    </body>\\n</html>", 1)
        logger.info("  Step 3: jockey_html + JS injected into template")
    else:
        # Try without indentation
        if "</body>\\n</html>" in src:
            src = src.replace("</body>\\n</html>",
                              "{jockey_html}\\n</body>\\n</html>", 1)
            logger.info("  Step 3 (fallback): jockey_html injected (no JS)")
        else:
            logger.warning("  Step 3: </body> anchor not found — manual insertion needed")

    # ── Step 4: Syntax check ──────────────────────────────────────────────
    try:
        ast.parse(src)
        logger.info("  Syntax check: OK")
    except SyntaxError as e:
        logger.error(f"  SYNTAX ERROR line {e.lineno}: {e}")
        lines = src.split("\n")
        for i in range(max(0, e.lineno - 4), min(len(lines), e.lineno + 4)):
            mark = " >> " if i == e.lineno - 1 else "    "
            logger.error(f"  {mark}{i+1}: {lines[i]}")
        raise SystemExit(1)

    BUILDER.write_text(src)
    logger.info("  builder.py written")


def smoke_test():
    logger.info("Smoke test...")
    # Remove cached modules
    for k in list(sys.modules.keys()):
        if "dashboard" in k or k == "db.database":
            del sys.modules[k]
    try:
        from dashboard.builder import build_dashboard
        build_dashboard()
        logger.info("  build_dashboard() OK")
    except Exception as e:
        logger.error(f"  FAILED: {e}")
        import traceback; traceback.print_exc()
        raise SystemExit(1)


def main():
    logger.info("=" * 60)
    logger.info("DASHBOARD V2 PATCH")
    logger.info("=" * 60)
    patch_builder()
    smoke_test()
    logger.info("")
    logger.info("DONE — hard refresh the dashboard")
    logger.info("Jockey leaderboard + ML accuracy now shown at bottom")
    logger.info("Collapsible section JS injected (toggle on header click)")


if __name__ == "__main__":
    main()
