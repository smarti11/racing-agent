"""Clean baseline migration for racing-agent.

After the pick-freeze migration (v2), agent_picks is clean but agent_picks_history
still contains 233k tainted rows that feed the dashboard's performance panels.
This script:

1. Wipes agent_picks_history completely (per user decision: no legacy table)
2. Patches dashboard/builder.py to add a prominent baseline-progress banner
   immediately under the FURBO FOX RACING header
3. The banner shows "BASELINE IN PROGRESS - X / 1000 HIGH CONF races collected"
   and auto-hides once threshold is met

Run from racing-agent root:
    venv/bin/python3 tools/migrate_clean_baseline.py
"""

import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "db" / "racing.db"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"

BASELINE_THRESHOLD = 1000  # HIGH CONF races needed before publishing-ready

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate_baseline")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


def wipe_history():
    logger.info("Step 1: Wiping agent_picks_history ...")
    with sqlite3.connect(DB_PATH) as conn:
        before = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        conn.execute("DELETE FROM agent_picks_history")
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        ap_count = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]
        logger.info(f"  agent_picks_history: {before} -> {after}")
        logger.info(f"  agent_picks: {ap_count} (today's clean picks preserved)")


def patch_builder():
    logger.info("Step 2: Patching dashboard/builder.py ...")
    src = BUILDER_FILE.read_text()
    if "BASELINE_BANNER_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(BUILDER_FILE)

    # Locate the header div and inject the banner immediately after.
    # Line 1107 in the original: <div><div class="title">FURBO FOX RACING</div>...
    old_header = (
        '    <div><div class="title">FURBO FOX RACING</div>'
        '<div class="subtitle">US THOROUGHBRED · DAILY CARD · EXPERT HANDICAPPING</div></div>'
    )

    # The banner is built dynamically using {baseline_banner_html} which we'll
    # compute earlier in the render function.
    new_header = (
        '    <div><div class="title">FURBO FOX RACING</div>'
        '<div class="subtitle">US THOROUGHBRED · DAILY CARD · EXPERT HANDICAPPING</div></div>'
        '\n    {baseline_banner_html}  <!-- BASELINE_BANNER_APPLIED -->'
    )

    if old_header not in src:
        logger.error("  Could not find FURBO FOX RACING header line; aborting")
        raise SystemExit(1)

    src = src.replace(old_header, new_header)

    # Now we need to compute baseline_banner_html somewhere in the build function
    # before the f-string substitution. Find where total_races is computed (line 377)
    # and add our banner-computation logic right after.

    old_compute = (
        '    total_races     = len(races)\n'
    )

    new_compute = (
        '    total_races     = len(races)\n'
        '\n'
        '    # Baseline progress: count graded HIGH CONF races from agent_picks\n'
        '    # (clean post-freeze data only)\n'
        '    try:\n'
        '        from db.database import get_conn as _bp_conn\n'
        '        with _bp_conn() as _bp_c:\n'
        '            _bp_clean = _bp_c.execute(\n'
        '                "SELECT COUNT(DISTINCT race_id) FROM agent_picks "\n'
        '                "WHERE confidence=? AND result IS NOT NULL",\n'
        '                ("HIGH",),\n'
        '            ).fetchone()[0] or 0\n'
        '    except Exception:\n'
        '        _bp_clean = 0\n'
        '    _bp_target = ' + str(BASELINE_THRESHOLD) + '\n'
        '    _bp_pct = min(100.0, 100.0 * _bp_clean / _bp_target) if _bp_target else 0\n'
        '    if _bp_clean < _bp_target:\n'
        '        baseline_banner_html = (\n'
        '            f\'<div style="background:linear-gradient(90deg,#3d1f00,#5c2e00);\'\n'
        '            f\'border:1px solid #ff8c00;border-radius:6px;padding:12px 16px;\'\n'
        '            f\'margin:12px 0;display:flex;align-items:center;gap:14px">\'\n'
        '            f\'<span style="font-size:18px">⚠</span>\'\n'
        '            f\'<div style="flex:1">\'\n'
        '            f\'<div style="font-size:13px;font-weight:700;color:#ffb86b;\'\n'
        '            f\'letter-spacing:.05em">BASELINE IN PROGRESS — \'\n'
        '            f\'{_bp_clean:,} / {_bp_target:,} HIGH CONF races collected ({_bp_pct:.1f}%)</div>\'\n'
        '            f\'<div style="font-size:11px;color:#c8a070;margin-top:3px">\'\n'
        '            f\'Performance stats below are early indicators; not yet publishing-ready. \'\n'
        '            f\'Historical (pre-freeze) data has been cleared due to a data-integrity bug \'\n'
        '            f\'that allowed post-race picks to overwrite live picks.</div>\'\n'
        '            f\'<div style="background:#1a1003;border-radius:3px;height:6px;\'\n'
        '            f\'margin-top:6px;overflow:hidden">\'\n'
        '            f\'<div style="background:linear-gradient(90deg,#ff8c00,#ffb86b);\'\n'
        '            f\'height:100%;width:{_bp_pct:.1f}%"></div>\'\n'
        '            f\'</div></div></div>\'\n'
        '        )\n'
        '    else:\n'
        '        baseline_banner_html = ""\n'
    )

    if old_compute not in src:
        logger.error("  Could not locate total_races compute line; aborting")
        raise SystemExit(1)

    src = src.replace(old_compute, new_compute)

    BUILDER_FILE.write_text(src)
    logger.info("  Patched.")


def verify():
    logger.info("Step 3: Verifying ...")
    import ast
    try:
        ast.parse(BUILDER_FILE.read_text())
        logger.info("  builder.py: syntax OK")
    except SyntaxError as e:
        logger.error(f"  builder.py: SYNTAX ERROR: {e}")
        raise SystemExit(1)

    with sqlite3.connect(DB_PATH) as conn:
        h = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        ap = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]
        graded = conn.execute(
            "SELECT COUNT(*) FROM agent_picks WHERE result IS NOT NULL"
        ).fetchone()[0]
        logger.info(f"  agent_picks_history: {h} (should be 0)")
        logger.info(f"  agent_picks: {ap} rows ({graded} graded)")


def main():
    logger.info("=" * 60)
    logger.info("CLEAN BASELINE MIGRATION")
    logger.info("=" * 60)

    wipe_history()
    patch_builder()
    verify()

    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("The dashboard will now show a banner at the top until")
    logger.info(f"{BASELINE_THRESHOLD:,} HIGH CONF races are graded with clean (frozen) picks.")
    logger.info("")
    logger.info("Touch the regen flag to refresh the dashboard:")
    logger.info("    touch ~/Documents/racing-agent/.regen_now")
    logger.info("")


if __name__ == "__main__":
    main()
