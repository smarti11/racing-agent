"""Hotfix: preserve race IDs across agent cycles.

THE BUG:
Line 148 of db/database.py uses INSERT OR REPLACE INTO races. SQLite's
REPLACE semantics DELETE the existing row and INSERT a fresh one, which
generates a new AUTOINCREMENT id. Every agent cycle that re-fetches today's
card therefore bumps today's race IDs forward, orphaning any agent_picks
created during prior cycles (they still point to the now-deleted IDs).

This has been silently corrupting historical pick data — 3,222 orphaned
picks accumulated as of the diagnosis. The races table has
UNIQUE(track_code, race_date, race_num) which is the natural key we
should be using for UPSERT semantics.

THE FIX:
Replace INSERT OR REPLACE with INSERT ... ON CONFLICT DO UPDATE so that
re-fetches update mutable columns (race_name, distance, surface, purse,
conditions, post_time, fetched_ts) while preserving the existing id.
track_code, race_date, race_num are the natural key — never updated.

This migration:
1. Kills the racing-agent (so no concurrent INSERT OR REPLACE happens
   during patch deployment).
2. Backs up db/database.py.
3. Replaces the INSERT OR REPLACE statement with an UPSERT.
4. Smoke-tests by simulating a duplicate insert and confirming the id
   is preserved.
5. Logs a summary of orphaned picks (read-only — does NOT delete them).
6. Reminds you to restart the agent.

Run from racing-agent root:
    venv/bin/python3 tools/migrate_fix_race_upsert.py

The migration is idempotent — re-runs are safe (it detects the patch
sentinel and exits cleanly).
"""

import logging
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "db" / "racing.db"
DB_FILE = ROOT / "db" / "database.py"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("upsert_fix")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Step 1: Kill any running racing-agent to avoid concurrent INSERT OR REPLACE
# ---------------------------------------------------------------------------

def kill_agent():
    logger.info("Step 1: Stopping any running racing-agent ...")
    try:
        out = subprocess.run(
            ["pgrep", "-f", "racing_agent.py"],
            capture_output=True, text=True,
        )
        pids = [p.strip() for p in out.stdout.split() if p.strip()]
        if not pids:
            logger.info("  No racing-agent process found; OK")
            return

        for pid in pids:
            logger.info(f"  Killing PID {pid}")
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        # Give the process a moment to flush any in-flight writes
        time.sleep(3)

        # Verify
        out = subprocess.run(
            ["pgrep", "-f", "racing_agent.py"],
            capture_output=True, text=True,
        )
        still = [p.strip() for p in out.stdout.split() if p.strip()]
        if still:
            logger.warning(f"  Some PIDs still alive: {still} — sending SIGKILL")
            for pid in still:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(2)
        logger.info("  Agent stopped")
    except Exception as e:
        logger.warning(f"  Process kill encountered issue: {e}")


# ---------------------------------------------------------------------------
# Step 2: Patch db/database.py
# ---------------------------------------------------------------------------

def patch_insert_statement():
    logger.info("Step 2: Patching INSERT OR REPLACE INTO races ...")
    src = DB_FILE.read_text()
    if "RACE_UPSERT_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return False
    backup_file(DB_FILE)

    # The current pattern from line 148. We need to find the full
    # INSERT OR REPLACE statement to replace it.
    # Let's locate it precisely.
    old_marker = "INSERT OR REPLACE INTO races"
    idx = src.find(old_marker)
    if idx == -1:
        logger.error("  Could not locate INSERT OR REPLACE statement; aborting")
        raise SystemExit(1)

    # Find the start of the line containing it
    line_start = src.rfind("\n", 0, idx) + 1
    # The statement spans multiple lines until the closing parenthesis of execute()
    # We need to locate the matching ")" that closes the execute() call.
    # Find the next "VALUES (" then the end of the SQL string, then the
    # parameters tuple, then the close paren.
    # Simpler: look for the closing """,\n or "',\n followed by the tuple
    # then ")"; we'll search line by line.

    # We'll do a safer match: find the INSERT OR REPLACE substring and walk
    # forward looking for the end of execute(...). The standard pattern is:
    #   conn.execute("""
    #       INSERT OR REPLACE INTO races
    #       (col, col, col, ...)
    #       VALUES (?, ?, ?, ...)
    #   """, (val, val, val, ...))
    # We'll capture from "conn.execute(" before the marker through the
    # matching ")" after the tuple.

    # Locate "conn.execute(" before our marker
    exec_idx = src.rfind("conn.execute(", 0, idx)
    if exec_idx == -1:
        # Maybe it's via cur or self.conn — try generic execute(
        exec_idx = src.rfind(".execute(", 0, idx)
        if exec_idx == -1:
            logger.error("  Could not locate execute() call; aborting")
            raise SystemExit(1)
        # Step back to start of identifier
        # find start of the identifier (whitespace or newline)
        i = exec_idx
        while i > 0 and src[i - 1] not in " \t\n":
            i -= 1
        exec_idx = i

    # Now walk forward from exec_idx to find the matching close paren of execute()
    # We need to track string boundaries (triple quoted) and parens.
    end_idx = None
    i = exec_idx
    paren_depth = 0
    in_triple = None  # '"""' or "'''" if inside one
    in_single = None  # '"' or "'" for normal strings
    while i < len(src):
        ch = src[i]
        ch3 = src[i:i + 3]

        # Triple quote handling
        if in_triple:
            if ch3 == in_triple:
                in_triple = None
                i += 3
                continue
            i += 1
            continue
        if in_single:
            if ch == "\\":
                i += 2
                continue
            if ch == in_single:
                in_single = None
            i += 1
            continue
        if ch3 in ('"""', "'''"):
            in_triple = ch3
            i += 3
            continue
        if ch in ('"', "'"):
            in_single = ch
            i += 1
            continue

        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                end_idx = i + 1
                break
        i += 1

    if end_idx is None:
        logger.error("  Could not find matching close paren; aborting")
        raise SystemExit(1)

    old_call = src[exec_idx:end_idx]
    logger.info(f"  Located execute() call: {len(old_call)} bytes")

    # Build replacement: INSERT ... ON CONFLICT DO UPDATE
    # The races table columns:
    #   id (auto)
    #   track_code, track_name, race_date, race_num,
    #   race_name, distance, surface, purse, conditions, post_time, fetched_ts
    # Natural key: (track_code, race_date, race_num)
    # We update everything EXCEPT the natural key (track_code, race_date,
    # race_num) and the id.
    new_call = (
        'conn.execute("""\n'
        '            INSERT INTO races\n'
        '              (track_code, track_name, race_date, race_num,\n'
        '               race_name, distance, surface, purse, conditions,\n'
        '               post_time, fetched_ts)\n'
        '            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n'
        '            ON CONFLICT(track_code, race_date, race_num) DO UPDATE SET\n'
        '              track_name = excluded.track_name,\n'
        '              race_name  = excluded.race_name,\n'
        '              distance   = excluded.distance,\n'
        '              surface    = excluded.surface,\n'
        '              purse      = excluded.purse,\n'
        '              conditions = excluded.conditions,\n'
        '              post_time  = excluded.post_time,\n'
        '              fetched_ts = excluded.fetched_ts\n'
        '            /* RACE_UPSERT_APPLIED */\n'
        '        """, (\n'
    )

    # We need to extract the parameters tuple from the old call.
    # The old call ends with: """, (a, b, c, ...))  — we want the (a, b, c, ...) part.
    # Look for the triple-quoted SQL end marker """, in the old call.
    triple_end = old_call.rfind('"""')
    if triple_end == -1:
        triple_end = old_call.rfind("'''")
    if triple_end == -1:
        logger.error("  Could not find SQL end marker; aborting")
        raise SystemExit(1)

    # After the closing triple quote we expect a comma then the tuple
    after_triple = old_call[triple_end + 3:].lstrip()
    if not after_triple.startswith(","):
        logger.error("  Unexpected structure after SQL; aborting")
        raise SystemExit(1)
    params_part = after_triple[1:].strip()  # drop the comma
    # params_part ends with the close paren of execute(...). Trim it.
    if not params_part.endswith(")"):
        logger.error("  Expected closing paren in params; aborting")
        raise SystemExit(1)
    # Append the params and close
    new_call = new_call + params_part + "\n"
    # The replacement already includes a "(" after VALUES "(\n" so we
    # need to ensure parentheses balance. Actually the new_call ends with
    # `"""\, (\n` and then we put params_part which is `(?, ?, ?, ...))` — that
    # makes us open one too many parens. Fix:
    # Re-do construction more carefully: don't open a paren at end of new_call.

    new_call_fixed = (
        'conn.execute("""\n'
        '            INSERT INTO races\n'
        '              (track_code, track_name, race_date, race_num,\n'
        '               race_name, distance, surface, purse, conditions,\n'
        '               post_time, fetched_ts)\n'
        '            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n'
        '            ON CONFLICT(track_code, race_date, race_num) DO UPDATE SET\n'
        '              track_name = excluded.track_name,\n'
        '              race_name  = excluded.race_name,\n'
        '              distance   = excluded.distance,\n'
        '              surface    = excluded.surface,\n'
        '              purse      = excluded.purse,\n'
        '              conditions = excluded.conditions,\n'
        '              post_time  = excluded.post_time,\n'
        '              fetched_ts = excluded.fetched_ts\n'
        '            /* RACE_UPSERT_APPLIED */\n'
        '        """, ' + params_part
    )

    new_src = src[:exec_idx] + new_call_fixed + src[end_idx:]

    # Syntax check
    import ast
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        logger.error(f"  Patched source has syntax error: {e}")
        logger.error("  Showing context around error:")
        new_lines = new_src.split("\n")
        for i in range(max(0, e.lineno - 3), min(len(new_lines), e.lineno + 3)):
            marker = " >> " if i == e.lineno - 1 else "    "
            logger.error(f"  {marker}{i + 1}: {new_lines[i]}")
        raise SystemExit(1)

    DB_FILE.write_text(new_src)
    logger.info("  Patched (syntax OK)")
    return True


# ---------------------------------------------------------------------------
# Step 3: Smoke-test the patch with a real INSERT then duplicate-INSERT
# ---------------------------------------------------------------------------

def smoke_test():
    logger.info("Step 3: Smoke-testing UPSERT semantics ...")
    # Force-reload the patched module
    for mod_name in ("db.database", "db"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    from db.database import save_race

    # Sentinel test fixture — won't conflict with real data
    test_track  = "ZZTEST"
    test_date   = "9999-12-31"
    test_num    = 1
    fixture_1 = {
        "track_code":  test_track,
        "track_name":  "Test Track",
        "race_date":   test_date,
        "race_num":    test_num,
        "race_name":   "Original Name",
        "distance":    "6F",
        "surface":     "Dirt",
        "purse":       "$10000",
        "conditions":  "Test",
        "post_time":   "12:00 PM",
    }
    fixture_2 = {
        **fixture_1,
        "race_name":   "Updated Name",  # Should update
        "post_time":   "12:30 PM",       # Should update
    }

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM races WHERE track_code=? AND race_date=? AND race_num=?",
            (test_track, test_date, test_num),
        )

    save_race(fixture_1)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, race_name, post_time FROM races "
            "WHERE track_code=? AND race_date=? AND race_num=?",
            (test_track, test_date, test_num),
        ).fetchone()
    first_id = row[0]
    logger.info(f"  After first insert: id={first_id}, name='{row[1]}', post='{row[2]}'")

    save_race(fixture_2)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, race_name, post_time FROM races "
            "WHERE track_code=? AND race_date=? AND race_num=?",
            (test_track, test_date, test_num),
        ).fetchone()
    second_id = row[0]
    logger.info(f"  After second insert: id={second_id}, name='{row[1]}', post='{row[2]}'")

    assert first_id == second_id, (
        f"ID changed! {first_id} -> {second_id} — UPSERT is not preserving IDs"
    )
    assert row[1] == "Updated Name", "race_name didn't update"
    assert row[2] == "12:30 PM", "post_time didn't update"

    # Cleanup test fixture
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM races WHERE track_code=? AND race_date=? AND race_num=?",
            (test_track, test_date, test_num),
        )

    logger.info("  UPSERT verified — ID preserved, mutable fields updated")


# ---------------------------------------------------------------------------
# Step 4: Report orphan-pick scope (read-only)
# ---------------------------------------------------------------------------

def report_orphans():
    logger.info("Step 4: Reporting orphan pick scope (read-only) ...")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total_orphan_picks,
                COUNT(DISTINCT race_id) AS orphan_race_ids,
                MIN(date(created_ts)) AS earliest,
                MAX(date(created_ts)) AS latest
            FROM agent_picks
            WHERE race_id NOT IN (SELECT id FROM races)
        """).fetchone()

        logger.info(f"  Orphan picks: {row[0]:,} across {row[1]} dead race IDs")
        logger.info(f"  Date span: {row[2]} to {row[3]}")
        logger.info("")
        logger.info("  NOT deleted by this migration. Cleanup can be done")
        logger.info("  in a separate migration once you've audited them.")


def main():
    logger.info("=" * 60)
    logger.info("RACE-ID UPSERT FIX")
    logger.info("=" * 60)

    kill_agent()
    patched = patch_insert_statement()
    if patched:
        smoke_test()
    else:
        logger.info("Skipping smoke test (already patched)")
    report_orphans()

    logger.info("=" * 60)
    logger.info("FIX COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Restart the agent:")
    logger.info("  cd ~/Documents/racing-agent && \\")
    logger.info("    nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")
    logger.info("")
    logger.info("Going forward, today's race IDs will remain stable across")
    logger.info("agent cycles. Picks created during cycle N will still join")
    logger.info("to the same race row during cycle N+1.")
    logger.info("")
    logger.info("Orphan cleanup is a separate task — picks generated BEFORE")
    logger.info("this fix that point to dead race IDs are still in the table.")


if __name__ == "__main__":
    main()
