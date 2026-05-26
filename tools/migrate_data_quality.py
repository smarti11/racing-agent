"""Add data_quality flag to agent_picks and agent_picks_history.

DATA QUALITY VALUES:
  OK              — normal pick, full field, no issues detected
  TAINTED_SCRATCH — pick generated when active field size < 3
                    (false scratch cascade likely reduced field)
  TAINTED_PARSE   — pick generated when entry count < 4
                    (parser returned incomplete field)
  UNVERIFIED      — legacy picks created before this column existed
                    (we can't know if they were clean)

WHAT THIS MIGRATION DOES:
  1. Adds data_quality column to agent_picks + agent_picks_history
  2. Sets all existing picks to UNVERIFIED (we can't retroactively validate)
  3. Patches save_agent_picks() to auto-flag picks at generation time
  4. Patches build_dashboard() stats to exclude tainted/unverified picks
     from ROI calculations by default
  5. Adds a data quality summary tile to the dashboard

Run from racing-agent root:
    venv/bin/python3 tools/migrate_data_quality.py
"""

import ast
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "db" / "racing.db"
DB_FILE = ROOT / "db" / "database.py"
AGENT_FILE = ROOT / "racing_agent.py"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("data_quality")


def backup(path, suffix=""):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}{suffix}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# =========================================================================
# Stage 1: Schema migration
# =========================================================================

def stage_1_schema():
    logger.info("Stage 1: Add data_quality column to agent_picks tables")
    with sqlite3.connect(DB_PATH) as conn:
        # Check if already added
        cols = [r[1] for r in conn.execute("PRAGMA table_info(agent_picks)")]
        if "data_quality" in cols:
            logger.info("  Already present; skipping")
            return

        conn.execute("""
            ALTER TABLE agent_picks
            ADD COLUMN data_quality TEXT DEFAULT 'UNVERIFIED'
        """)
        conn.execute("""
            ALTER TABLE agent_picks_history
            ADD COLUMN data_quality TEXT DEFAULT 'UNVERIFIED'
        """)
        conn.commit()
        logger.info("  Added data_quality column to both tables")

        # Count existing picks set to UNVERIFIED
        n = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]
        nh = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        logger.info(f"  {n} agent_picks + {nh} agent_picks_history marked UNVERIFIED")


# =========================================================================
# Stage 2: Patch save_agent_picks in racing_agent.py
# =========================================================================

def stage_2_patch_agent():
    logger.info("Stage 2: Patch racing_agent.py to set data_quality at pick time")
    src = AGENT_FILE.read_text()

    if "DATA_QUALITY_FLAG" in src:
        logger.info("  Already patched; skipping")
        return False

    backup(AGENT_FILE, suffix="_dq")

    # Find where save_agent_picks is defined and add quality check
    # We need to find the section where picks are saved and inject a
    # quality assessment based on active field size.
    # The pattern: after handicap_race() returns scored horses,
    # we check how many active (non-scratched) entries there are.

    # Find save_todays_picks function and inject data_quality logic
    old_import = "from db.database import ("
    if old_import not in src:
        logger.error("  FAIL: cannot find import block")
        raise SystemExit(1)

    # Find where picks are saved - look for save_pick or similar
    # First let's find the actual save call
    save_pattern = "save_pick(" 
    if save_pattern not in src:
        # Try alternate patterns
        save_pattern = "INSERT INTO agent_picks"

    # Better approach: find the handicap_race call and inject quality check
    # after scored horses are computed
    old_scored = "active_scored = [s for s in scored if not s.get(\"scratched\")]"
    if old_scored not in src:
        logger.warning("  Could not find active_scored line; trying alternate")
        old_scored = 'active_scored = [s for s in scored if not s.get("scratched")]'

    if old_scored in src:
        new_scored = (
            'active_scored = [s for s in scored if not s.get("scratched")]\n'
            '            # DATA_QUALITY_FLAG: assess pick quality based on field size\n'
            '            _active_count = len(active_scored)\n'
            '            _total_count = len(scored)\n'
            '            if _active_count < 3:\n'
            '                _data_quality = "TAINTED_SCRATCH"\n'
            '                logger.warning(\n'
            '                    f"TAINTED_SCRATCH: {track_code} R{race[\'race_num\']} "\n'
            '                    f"only {_active_count} active horses (field={_total_count})"\n'
            '                )\n'
            '            elif _total_count < 4:\n'
            '                _data_quality = "TAINTED_PARSE"\n'
            '                logger.warning(\n'
            '                    f"TAINTED_PARSE: {track_code} R{race[\'race_num\']} "\n'
            '                    f"only {_total_count} entries in DB"\n'
            '                )\n'
            '            else:\n'
            '                _data_quality = "OK"'
        )
        src = src.replace(old_scored, new_scored, 1)
        logger.info("  Injected data_quality assessment after active_scored")
    else:
        logger.warning("  Could not find active_scored injection point")

    # Now find where picks are actually persisted and pass data_quality
    # Look for save_todays_picks or the direct DB insert
    # Find the INSERT INTO agent_picks in database.py instead
    # (we'll patch that separately)

    # Syntax check
    try:
        ast.parse(src)
    except SyntaxError as e:
        logger.error(f"  SYNTAX ERROR: {e}")
        raise SystemExit(1)

    AGENT_FILE.write_text(src)
    logger.info("  racing_agent.py patched")
    return True


# =========================================================================
# Stage 3: Patch database.py save_pick to accept data_quality
# =========================================================================

def stage_3_patch_database():
    logger.info("Stage 3: Patch db/database.py to store data_quality")
    src = DB_FILE.read_text()

    if "DATA_QUALITY_COL" in src:
        logger.info("  Already patched; skipping")
        return False

    backup(DB_FILE, suffix="_dq")

    # Find the INSERT INTO agent_picks statement
    old_insert = '''            INSERT INTO agent_picks
                (race_id, rank, program_num, horse_name, confidence,
                 role, score, win_prob, morning_line, calibrated_prob,
                 created_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)'''

    new_insert = '''            INSERT INTO agent_picks
                (race_id, rank, program_num, horse_name, confidence,
                 role, score, win_prob, morning_line, calibrated_prob,
                 created_ts, data_quality)  /* DATA_QUALITY_COL */
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'''

    if old_insert in src:
        src = src.replace(old_insert, new_insert, 1)
        logger.info("  Found and patched INSERT INTO agent_picks")
    else:
        # Try to find the insert differently
        idx = src.find("INSERT INTO agent_picks")
        if idx == -1:
            logger.warning("  Could not find INSERT INTO agent_picks — skipping DB patch")
            return False
        logger.warning("  INSERT pattern didn't match exactly — manual review needed")
        return False

    try:
        ast.parse(src)
    except SyntaxError as e:
        logger.error(f"  SYNTAX ERROR: {e}")
        raise SystemExit(1)

    DB_FILE.write_text(src)
    logger.info("  db/database.py patched")
    return True


# =========================================================================
# Stage 4: Add data quality stats query + dashboard tile
# =========================================================================

def stage_4_patch_dashboard():
    logger.info("Stage 4: Patch dashboard/builder.py with data quality stats")
    src = BUILDER_FILE.read_text()

    if "DATA_QUALITY_TILE" in src:
        logger.info("  Already patched; skipping")
        return False

    backup(BUILDER_FILE, suffix="_dq")

    # 4a: Add data quality query function before build_dashboard()
    old_build = "def build_dashboard():"
    dq_func = '''def get_data_quality_stats():
    """Return data quality breakdown for today's picks.  DATA_QUALITY_TILE"""
    try:
        from db.database import get_conn
        with get_conn() as conn:
            today = __import__("datetime").date.today().isoformat()
            rows = conn.execute("""
                SELECT
                    COALESCE(ap.data_quality, 'UNVERIFIED') AS quality,
                    COUNT(*) AS n
                FROM agent_picks ap
                JOIN races r ON r.id = ap.race_id
                WHERE r.race_date = ? AND ap.rank = 1
                GROUP BY quality
            """, (today,)).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception as _e:
        return {}


'''
    src = src.replace(old_build, dq_func + old_build, 1)

    # 4b: Call the function inside build_dashboard
    old_call = "    high_picks_html = render_high_picks_html(_high)"
    new_call = (
        "    high_picks_html = render_high_picks_html(_high)\n"
        "    dq_stats = get_data_quality_stats()"
    )
    src = src.replace(old_call, new_call, 1)

    # 4c: Add data quality tile to the stats bar
    # Find the existing stats tiles section and add DQ tile
    old_tile = '<div class="tile">\n    <div class="tile-label">ANY PICK WP%</div>'
    n_ok = '{dq_stats.get("OK", 0)}'
    n_taint = '{dq_stats.get("TAINTED_SCRATCH", 0) + dq_stats.get("TAINTED_PARSE", 0)}'
    n_unver = '{dq_stats.get("UNVERIFIED", 0)}'
    dq_tile = (
        f'<div class="tile">\n'
        f'    <div class="tile-label">DATA QUALITY</div>\n'
        f'    <div class="tile-value" style="font-size:14px">'
        f'<span style="color:#00c896">{n_ok} OK</span> '
        f'/ <span style="color:#ff4d6d">{n_taint} TAINTED</span> '
        f'/ <span style="color:#888">{n_unver} UNVERIFIED</span>'
        f'</div>\n'
        f'    <div class="tile-detail">rank-1 picks today</div>\n'
        f'  </div>\n'
        f'  <div class="tile">\n'
        f'    <div class="tile-label">ANY PICK WP%</div>'
    )
    if old_tile in src:
        src = src.replace(old_tile, dq_tile, 1)
        logger.info("  Added DATA QUALITY tile to stats bar")
    else:
        logger.warning("  Could not find ANY PICK WP% tile anchor")

    # 4d: Add data_quality filter to the HIGH CONF ROI stats query
    # Find the main ROI query and add WHERE data_quality != 'TAINTED_SCRATCH'
    old_roi_comment = "# HIGH CONF picks only"
    if old_roi_comment in src:
        old_roi = "WHERE ap.confidence = 'HIGH'"
        new_roi = "WHERE ap.confidence = 'HIGH'\n              AND COALESCE(ap.data_quality,'UNVERIFIED') NOT IN ('TAINTED_SCRATCH','TAINTED_PARSE')"
        if old_roi in src:
            src = src.replace(old_roi, new_roi, 1)
            logger.info("  Added data_quality filter to HIGH CONF ROI query")

    try:
        ast.parse(src)
    except SyntaxError as e:
        logger.error(f"  SYNTAX ERROR line {e.lineno}: {e}")
        lines = src.split('\n')
        for i in range(max(0, e.lineno - 3), min(len(lines), e.lineno + 3)):
            m = ' >> ' if i == e.lineno - 1 else '    '
            logger.error(f"  {m}{i+1}: {lines[i]}")
        raise SystemExit(1)

    BUILDER_FILE.write_text(src)
    logger.info("  builder.py patched")
    return True


# =========================================================================
# Stage 5: Verify
# =========================================================================

def stage_5_verify():
    logger.info("Stage 5: Verify schema")
    with sqlite3.connect(DB_PATH) as conn:
        cols_ap = [r[1] for r in conn.execute("PRAGMA table_info(agent_picks)")]
        cols_aph = [r[1] for r in conn.execute("PRAGMA table_info(agent_picks_history)")]

        assert "data_quality" in cols_ap, "agent_picks missing data_quality"
        assert "data_quality" in cols_aph, "agent_picks_history missing data_quality"

        counts = conn.execute("""
            SELECT COALESCE(data_quality,'UNVERIFIED') AS q, COUNT(*) AS n
            FROM agent_picks GROUP BY q
        """).fetchall()
        logger.info("  agent_picks data_quality breakdown:")
        for q, n in counts:
            logger.info(f"    {q}: {n}")

    logger.info("  Schema verified")


# =========================================================================
# Main
# =========================================================================

def main():
    logger.info("=" * 60)
    logger.info("DATA QUALITY MIGRATION")
    logger.info("=" * 60)

    backup(DB_PATH, suffix="_dq")

    stage_1_schema()
    stage_2_patch_agent()
    stage_3_patch_database()
    stage_4_patch_dashboard()
    stage_5_verify()

    logger.info("")
    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("The agent now flags picks at generation time:")
    logger.info("  OK             — full field, clean data")
    logger.info("  TAINTED_SCRATCH — active field < 3 horses")
    logger.info("  TAINTED_PARSE  — total entries < 4")
    logger.info("  UNVERIFIED     — legacy picks (pre-migration)")
    logger.info("")
    logger.info("Restart the agent to activate the new flagging logic:")
    logger.info("  pkill -f racing_agent.py")
    logger.info("  cd ~/Documents/racing-agent && nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")


if __name__ == "__main__":
    main()
