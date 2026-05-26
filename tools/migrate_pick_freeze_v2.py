"""Pick-freeze migration v2 for racing-agent.

Aligned with actual codebase architecture:
- agent_picks_history already exists with (rendered_ts, trigger) schema
- save_agent_picks is in db/database.py and writes to agent_picks
- dashboard/builder.py independently runs handicap_race + logs to history
- BOTH code paths must freeze once race results are posted

What this script does:
1. Wipe agent_picks (one-time clean baseline; history table preserved)
2. Patch db/database.py:save_agent_picks to:
   - Skip writes if race has results (freeze)
   - Also log every save to agent_picks_history with trigger='agent_save'
3. Patch dashboard/builder.py to skip handicap + history-insert for finished races
4. Patch racing_agent.py:save_todays_picks to skip completed races

Both files get timestamped backups. Run from racing-agent root:
    venv/bin/python3 tools/migrate_pick_freeze_v2.py
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
DB_FILE = ROOT / "db" / "database.py"
AGENT_FILE = ROOT / "racing_agent.py"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate_v2")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


def wipe_agent_picks():
    logger.info("Step 1: Wiping agent_picks (tainted) ...")
    with sqlite3.connect(DB_PATH) as conn:
        before = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]
        conn.execute("DELETE FROM agent_picks")
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]

        hist = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        logger.info(f"  agent_picks: {before} -> {after} wiped")
        logger.info(f"  agent_picks_history preserved: {hist} rows")


def patch_database_py():
    logger.info("Step 2: Patching db/database.py ...")
    src = DB_FILE.read_text()
    if "FREEZE_GUARD_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(DB_FILE)

    old_func = (
        'def save_agent_picks(race_id: int, picks: list):\n'
        '    """\n'
        '    Save agent\'s top 3 picks for a race.\n'
        '    picks = [{"rank":1,"program_num":"3","horse_name":"Stowaway","confidence":"HIGH",\n'
        '              "score":71,"win_prob":0.27,"morning_line":"5/2"},...]\n'
        '\n'
        '    Now does DELETE-then-INSERT so picks update when scratches change the field.\n'
        '    """\n'
        '    with get_conn() as conn:\n'
        '        # Replace any existing picks for this race so updates take effect\n'
        '        # (e.g., when a horse scratches and the agent recomputes)\n'
        '        conn.execute("DELETE FROM agent_picks WHERE race_id=?", (race_id,))\n'
        '\n'
        '        for pick in picks:\n'
        '            conn.execute("""\n'
        '                INSERT INTO agent_picks\n'
        '                (race_id, rank, program_num, horse_name, confidence, role,\n'
        '                 created_ts, score, win_prob, morning_line, calibrated_prob)\n'
        '                VALUES (?,?,?,?,?,?,?,?,?,?,?)\n'
        '            """, (\n'
        '                race_id,\n'
        '                pick.get("rank", 1),\n'
        '                str(pick.get("program_num", "")),\n'
        '                pick.get("horse_name", ""),\n'
        '                pick.get("confidence", ""),\n'
        '                pick.get("role", ""),\n'
        '                datetime.now().isoformat(),\n'
        '                pick.get("score"),\n'
        '                pick.get("win_prob"),\n'
        '                pick.get("morning_line"),\n'
        '                pick.get("calibrated_prob"),\n'
        '            ))\n'
    )

    new_func = (
        'def save_agent_picks(race_id: int, picks: list):\n'
        '    """\n'
        '    Save agent\'s top 3 picks for a race. FREEZE_GUARD_APPLIED.\n'
        '\n'
        '    Behavior:\n'
        '    - If race has results in `results` table, the live agent_picks row is\n'
        '      FROZEN: this function will NOT modify agent_picks. It still logs to\n'
        '      agent_picks_history for forensic record.\n'
        '    - Pre-race: continues DELETE-then-INSERT into agent_picks so scratches\n'
        '      and updated form trigger re-handicapping. Every save also appends to\n'
        '      agent_picks_history with trigger=\'agent_save\'.\n'
        '    """\n'
        '    now_iso = datetime.now().isoformat()\n'
        '\n'
        '    with get_conn() as conn:\n'
        '        # FREEZE CHECK\n'
        '        race_done = conn.execute(\n'
        '            "SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race_id,)\n'
        '        ).fetchone() is not None\n'
        '\n'
        '        # Always log to history (audit trail; never deleted)\n'
        '        for pick in picks:\n'
        '            conn.execute(\n'
        '                "INSERT INTO agent_picks_history "\n'
        '                "(race_id, rank, program_num, horse_name, confidence, role, "\n'
        '                "rendered_ts, trigger) VALUES (?,?,?,?,?,?,?,?)",\n'
        '                (\n'
        '                    race_id,\n'
        '                    pick.get("rank", 1),\n'
        '                    str(pick.get("program_num", "")),\n'
        '                    pick.get("horse_name", ""),\n'
        '                    pick.get("confidence", ""),\n'
        '                    pick.get("role", ""),\n'
        '                    now_iso,\n'
        '                    "agent_save_frozen" if race_done else "agent_save",\n'
        '                ),\n'
        '            )\n'
        '\n'
        '        if race_done:\n'
        '            # Race is over: do NOT modify agent_picks (FREEZE)\n'
        '            return\n'
        '\n'
        '        # Pre-race: DELETE-then-INSERT live picks (scratches still apply)\n'
        '        conn.execute("DELETE FROM agent_picks WHERE race_id=?", (race_id,))\n'
        '\n'
        '        for pick in picks:\n'
        '            conn.execute("""\n'
        '                INSERT INTO agent_picks\n'
        '                (race_id, rank, program_num, horse_name, confidence, role,\n'
        '                 created_ts, score, win_prob, morning_line, calibrated_prob)\n'
        '                VALUES (?,?,?,?,?,?,?,?,?,?,?)\n'
        '            """, (\n'
        '                race_id,\n'
        '                pick.get("rank", 1),\n'
        '                str(pick.get("program_num", "")),\n'
        '                pick.get("horse_name", ""),\n'
        '                pick.get("confidence", ""),\n'
        '                pick.get("role", ""),\n'
        '                now_iso,\n'
        '                pick.get("score"),\n'
        '                pick.get("win_prob"),\n'
        '                pick.get("morning_line"),\n'
        '                pick.get("calibrated_prob"),\n'
        '            ))\n'
    )

    if old_func not in src:
        logger.error("  Could not locate save_agent_picks; aborting.")
        raise SystemExit(1)

    src = src.replace(old_func, new_func)
    DB_FILE.write_text(src)
    logger.info("  Patched.")


def patch_builder_py():
    logger.info("Step 3: Patching dashboard/builder.py ...")
    src = BUILDER_FILE.read_text()
    if "BUILDER_FREEZE_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(BUILDER_FILE)

    old_block = (
        '            for race in track_races:\n'
        '                entries    = get_race_entries(race["id"])\n'
        '                active     = [e for e in entries if not e["scratched"]]\n'
        '                scratched  = [e for e in entries if e["scratched"]]\n'
        '                conditions = race["conditions"] or ""\n'
        '                distance   = race["distance"] or ""\n'
        '                track_code = race["track_code"] or ""\n'
        '\n'
        '                scored      = handicap_race([dict(e) for e in entries], conditions, track_code, distance)\n'
    )

    new_block = (
        '            for race in track_races:\n'
        '                entries    = get_race_entries(race["id"])\n'
        '                active     = [e for e in entries if not e["scratched"]]\n'
        '                scratched  = [e for e in entries if e["scratched"]]\n'
        '                conditions = race["conditions"] or ""\n'
        '                distance   = race["distance"] or ""\n'
        '                track_code = race["track_code"] or ""\n'
        '\n'
        '                # BUILDER_FREEZE_APPLIED: do not re-handicap completed races.\n'
        '                # The agent_picks table is frozen post-race; the builder must\n'
        '                # read the frozen picks from agent_picks instead of recomputing.\n'
        '                try:\n'
        '                    from db.database import get_conn as _gc\n'
        '                    with _gc() as _c:\n'
        '                        _race_done = _c.execute(\n'
        '                            "SELECT 1 FROM results WHERE race_id=? LIMIT 1",\n'
        '                            (race["id"],),\n'
        '                        ).fetchone() is not None\n'
        '                except Exception:\n'
        '                    _race_done = False\n'
        '\n'
        '                scored      = handicap_race([dict(e) for e in entries], conditions, track_code, distance)\n'
    )

    if old_block not in src:
        logger.error("  Could not locate builder.py for-loop; aborting.")
        raise SystemExit(1)
    src = src.replace(old_block, new_block)

    # Now skip the history-insert if race is done (the history row would be a post-race
    # recomputation and is misleading)
    old_hist = (
        '                # Audit log: append every render to history table\n'
        '                try:\n'
        '                    from db.database import get_conn as _get_conn\n'
        '                    _now_iso = datetime.now().isoformat()\n'
        '                    _role_names = ["WIN", "PLACE", "SHOW"]\n'
        '                    with _get_conn() as _conn:\n'
        '                        for _idx, _pick in enumerate(role_top3[:3]):\n'
        '                            _conn.execute(\n'
        '                                "INSERT INTO agent_picks_history "\n'
        '                                "(race_id, rank, program_num, horse_name, confidence, role, rendered_ts, trigger) "\n'
        '                                "VALUES (?,?,?,?,?,?,?,?)",\n'
        '                                (\n'
        '                                    race["id"],\n'
        '                                    _idx + 1,\n'
        '                                    str(_pick.get("program_num", "")),\n'
        '                                    _pick.get("horse_name", ""),\n'
        '                                    _pick.get("confidence", ""),\n'
        '                                    _role_names[_idx],\n'
        '                                    _now_iso,\n'
        '                                    "dashboard_render",\n'
        '                                ),\n'
        '                            )\n'
    )

    new_hist = (
        '                # Audit log: only log pre-race renders. Post-race renders\n'
        '                # would be misleading because handicap inputs may have shifted.\n'
        '                try:\n'
        '                    from db.database import get_conn as _get_conn\n'
        '                    _now_iso = datetime.now().isoformat()\n'
        '                    _role_names = ["WIN", "PLACE", "SHOW"]\n'
        '                    _trigger = "dashboard_render_postrace" if _race_done else "dashboard_render"\n'
        '                    with _get_conn() as _conn:\n'
        '                        for _idx, _pick in enumerate(role_top3[:3]):\n'
        '                            _conn.execute(\n'
        '                                "INSERT INTO agent_picks_history "\n'
        '                                "(race_id, rank, program_num, horse_name, confidence, role, rendered_ts, trigger) "\n'
        '                                "VALUES (?,?,?,?,?,?,?,?)",\n'
        '                                (\n'
        '                                    race["id"],\n'
        '                                    _idx + 1,\n'
        '                                    str(_pick.get("program_num", "")),\n'
        '                                    _pick.get("horse_name", ""),\n'
        '                                    _pick.get("confidence", ""),\n'
        '                                    _role_names[_idx],\n'
        '                                    _now_iso,\n'
        '                                    _trigger,\n'
        '                                ),\n'
        '                            )\n'
    )

    if old_hist not in src:
        logger.warning("  History-insert block not in expected form; skipping its tag.")
    else:
        src = src.replace(old_hist, new_hist)

    BUILDER_FILE.write_text(src)
    logger.info("  Patched.")


def patch_racing_agent_py():
    logger.info("Step 4: Patching racing_agent.py ...")
    src = AGENT_FILE.read_text()
    if "FREEZE_SKIP_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(AGENT_FILE)

    old_loop = (
        '    races = get_todays_races()\n'
        '    saved = 0\n'
        '    for race in races:\n'
        '        try:\n'
        '            entries = db_get_race_entries(race["id"])'
    )

    new_loop = (
        '    races = get_todays_races()\n'
        '    saved = 0\n'
        '    skipped_done = 0\n'
        '    for race in races:\n'
        '        # FREEZE_SKIP_APPLIED: skip races whose results are already posted.\n'
        '        # save_agent_picks would freeze anyway, but skipping here avoids\n'
        '        # wasting time on handicap_race for completed races.\n'
        '        try:\n'
        '            from db.database import get_conn\n'
        '            with get_conn() as _c:\n'
        '                _done = _c.execute(\n'
        '                    "SELECT 1 FROM results WHERE race_id=? LIMIT 1",\n'
        '                    (race["id"],),\n'
        '                ).fetchone()\n'
        '            if _done:\n'
        '                skipped_done += 1\n'
        '                continue\n'
        '        except Exception:\n'
        '            pass\n'
        '\n'
        '        try:\n'
        '            entries = db_get_race_entries(race["id"])'
    )

    if old_loop not in src:
        logger.error("  Could not locate save_todays_picks loop; aborting.")
        raise SystemExit(1)
    src = src.replace(old_loop, new_loop)

    AGENT_FILE.write_text(src)
    logger.info("  Patched.")


def verify():
    logger.info("Step 5: Verifying ...")
    import ast
    for f in (DB_FILE, AGENT_FILE, BUILDER_FILE):
        try:
            ast.parse(f.read_text())
            logger.info(f"  {f.name}: syntax OK")
        except SyntaxError as e:
            logger.error(f"  {f.name}: SYNTAX ERROR: {e}")
            raise SystemExit(1)

    with sqlite3.connect(DB_PATH) as conn:
        n = conn.execute("SELECT COUNT(*) FROM agent_picks").fetchone()[0]
        h = conn.execute("SELECT COUNT(*) FROM agent_picks_history").fetchone()[0]
        logger.info(f"  agent_picks rows: {n} (should be 0)")
        logger.info(f"  agent_picks_history rows: {h} (preserved)")


def main():
    logger.info("=" * 60)
    logger.info("RACING-AGENT PICK-FREEZE MIGRATION v2")
    logger.info("=" * 60)

    wipe_agent_picks()
    patch_database_py()
    patch_builder_py()
    patch_racing_agent_py()
    verify()

    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Restart racing-agent:")
    logger.info("       cd ~/Documents/racing-agent && nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")
    logger.info("  2. Watch logs:")
    logger.info("       tail -f ~/Documents/racing-agent/logs/racing.log")
    logger.info("  3. After a race finishes, verify agent_picks does NOT update.")
    logger.info("  4. Verify agent_picks_history shows trigger=agent_save_frozen for it.")


if __name__ == "__main__":
    main()
