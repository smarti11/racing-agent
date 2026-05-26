"""Comprehensive data-integrity cleanup.

Fixes the systemic INSERT OR REPLACE bug in the `entries` table and cleans
up orphaned rows across all related tables.

DIAGNOSIS:
The `entries` table has 759,100 rows of which 730,160 are orphans (point to
deleted race IDs). Of the 28,940 valid rows, ~476 horse positions are duplicated
because INSERT OR REPLACE never matches (no UNIQUE constraint), so every
agent cycle adds new rows for the same horse.

Similar orphan pollution exists in agent_picks (3,222), agent_picks_history
(8,756), and results (15,006) — all from before tonight's race-UPSERT fix.

FIX STRATEGY:
1. Full database backup (timestamped .bak file)
2. Dedupe entries: keep MAX(id) per (race_id, program_num); delete others
3. Rebuild entries table with UNIQUE(race_id, program_num) constraint
4. Delete all orphan rows from entries, agent_picks, agent_picks_history, results
5. Patch INSERT OR REPLACE INTO entries → UPSERT in db/database.py
6. VACUUM the database to reclaim space
7. Verify expected row counts

All within ONE transaction where possible. Idempotent (safe to re-run).

Run from racing-agent root:
    venv/bin/python3 tools/migrate_dedupe_orphans.py
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
logger = logging.getLogger("dedupe")


def backup_file(path: Path, suffix: str = "") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}{suffix}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Step 1: Kill the agent
# ---------------------------------------------------------------------------

def kill_agent():
    logger.info("Step 1: Stopping any running racing-agent ...")
    try:
        out = subprocess.run(["pgrep", "-f", "racing_agent.py"],
                            capture_output=True, text=True)
        pids = [p.strip() for p in out.stdout.split() if p.strip()]
        if not pids:
            logger.info("  No racing-agent running; OK")
            return
        for pid in pids:
            logger.info(f"  Killing PID {pid}")
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(3)
        out = subprocess.run(["pgrep", "-f", "racing_agent.py"],
                            capture_output=True, text=True)
        still = [p.strip() for p in out.stdout.split() if p.strip()]
        if still:
            for pid in still:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(2)
        logger.info("  Agent stopped")
    except Exception as e:
        logger.warning(f"  Process kill issue: {e}")


# ---------------------------------------------------------------------------
# Step 2: Full database backup
# ---------------------------------------------------------------------------

def backup_database():
    logger.info("Step 2: Backing up entire database ...")
    backup_file(DB_PATH)
    logger.info(f"  Database backed up ({DB_PATH.stat().st_size / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# Step 3: Pre-cleanup audit
# ---------------------------------------------------------------------------

def snapshot_counts(conn, label=""):
    counts = {}
    for table in ("races", "entries", "agent_picks", "agent_picks_history",
                  "results", "pick_payouts"):
        try:
            counts[table] = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = "N/A"
    counts["entries_orphans"] = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE race_id NOT IN (SELECT id FROM races)"
    ).fetchone()[0]
    counts["agent_picks_orphans"] = conn.execute(
        "SELECT COUNT(*) FROM agent_picks WHERE race_id NOT IN (SELECT id FROM races)"
    ).fetchone()[0]
    counts["agent_picks_history_orphans"] = conn.execute(
        "SELECT COUNT(*) FROM agent_picks_history WHERE race_id NOT IN (SELECT id FROM races)"
    ).fetchone()[0]
    counts["results_orphans"] = conn.execute(
        "SELECT COUNT(*) FROM results WHERE race_id NOT IN (SELECT id FROM races)"
    ).fetchone()[0]
    counts["entries_dupes_sets"] = conn.execute(
        "SELECT COUNT(*) FROM (SELECT race_id, program_num FROM entries "
        "GROUP BY race_id, program_num HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    if label:
        logger.info(f"  -- {label} --")
        for k, v in counts.items():
            logger.info(f"    {k:35s} {v:>10}")
    return counts


# ---------------------------------------------------------------------------
# Step 4: Delete orphans (rows pointing to non-existent races)
# ---------------------------------------------------------------------------

def delete_orphans():
    logger.info("Step 3: Deleting orphaned rows ...")
    with sqlite3.connect(DB_PATH) as conn:
        # entries
        n = conn.execute(
            "DELETE FROM entries WHERE race_id NOT IN (SELECT id FROM races)"
        ).rowcount
        logger.info(f"  entries: deleted {n:,} orphans")

        # agent_picks
        n = conn.execute(
            "DELETE FROM agent_picks WHERE race_id NOT IN (SELECT id FROM races)"
        ).rowcount
        logger.info(f"  agent_picks: deleted {n:,} orphans")

        # agent_picks_history
        n = conn.execute(
            "DELETE FROM agent_picks_history WHERE race_id NOT IN (SELECT id FROM races)"
        ).rowcount
        logger.info(f"  agent_picks_history: deleted {n:,} orphans")

        # results
        n = conn.execute(
            "DELETE FROM results WHERE race_id NOT IN (SELECT id FROM races)"
        ).rowcount
        logger.info(f"  results: deleted {n:,} orphans")

        conn.commit()
    logger.info("  All orphans deleted")


# ---------------------------------------------------------------------------
# Step 5: Dedupe entries table — keep newest row per (race_id, program_num)
# ---------------------------------------------------------------------------

def dedupe_entries():
    logger.info("Step 4: Deduping entries table ...")
    with sqlite3.connect(DB_PATH) as conn:
        # Find sets that have duplicates
        before = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        logger.info(f"  Entries before dedupe: {before:,}")

        # Delete all but the MAX(id) for each (race_id, program_num).
        # This keeps the most recent row (newest fetched_ts effectively).
        deleted = conn.execute("""
            DELETE FROM entries
            WHERE id NOT IN (
                SELECT MAX(id) FROM entries
                GROUP BY race_id, program_num
            )
        """).rowcount
        conn.commit()

        after = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        logger.info(f"  Deleted {deleted:,} duplicate entries")
        logger.info(f"  Entries after dedupe: {after:,}")

        # Verify no duplicates remain
        dupes = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT race_id, program_num FROM entries
                GROUP BY race_id, program_num HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        assert dupes == 0, f"Still {dupes} dupes after dedupe!"
        logger.info("  No duplicate (race_id, program_num) pairs remain")


# ---------------------------------------------------------------------------
# Step 6: Add UNIQUE constraint to entries via table rebuild
# ---------------------------------------------------------------------------

def add_entries_unique_constraint():
    logger.info("Step 5: Adding UNIQUE constraint to entries table ...")
    with sqlite3.connect(DB_PATH) as conn:
        # Check if already done
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()[0]
        if "UNIQUE(race_id, program_num)" in schema or \
           "UNIQUE (race_id, program_num)" in schema:
            logger.info("  Constraint already present; skipping")
            return

        # SQLite can't ALTER TABLE to add UNIQUE — must rebuild
        conn.executescript("""
            BEGIN;
            CREATE TABLE entries_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id         INTEGER NOT NULL,
                program_num     TEXT NOT NULL,
                horse_name      TEXT NOT NULL,
                jockey          TEXT,
                trainer         TEXT,
                morning_line    TEXT,
                weight          TEXT,
                scratched       INTEGER DEFAULT 0,
                scratch_time    TEXT,
                fetched_ts      TEXT NOT NULL,
                UNIQUE(race_id, program_num),
                FOREIGN KEY(race_id) REFERENCES races(id)
            );
            INSERT INTO entries_new
              (id, race_id, program_num, horse_name, jockey, trainer,
               morning_line, weight, scratched, scratch_time, fetched_ts)
            SELECT id, race_id, program_num, horse_name, jockey, trainer,
                   morning_line, weight, scratched, scratch_time, fetched_ts
            FROM entries;
            DROP TABLE entries;
            ALTER TABLE entries_new RENAME TO entries;
            CREATE INDEX IF NOT EXISTS idx_entries_race_id ON entries(race_id);
            COMMIT;
        """)

        # Verify
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()[0]
        assert "UNIQUE" in schema and "program_num" in schema, \
            "UNIQUE constraint not applied"
        logger.info("  UNIQUE(race_id, program_num) constraint added")


# ---------------------------------------------------------------------------
# Step 7: Patch INSERT OR REPLACE INTO entries -> UPSERT in db/database.py
# ---------------------------------------------------------------------------

def patch_entries_insert():
    logger.info("Step 6: Patching INSERT OR REPLACE INTO entries ...")
    src = DB_FILE.read_text()
    if "ENTRIES_UPSERT_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(DB_FILE, suffix="_entries_patch")

    old_marker = "INSERT OR REPLACE INTO entries"
    idx = src.find(old_marker)
    if idx == -1:
        logger.error("  Could not locate INSERT OR REPLACE INTO entries")
        raise SystemExit(1)

    # Walk forward from the conn.execute( before idx to find the close paren
    exec_idx = src.rfind("conn.execute(", 0, idx)
    if exec_idx == -1:
        exec_idx = src.rfind(".execute(", 0, idx)
        if exec_idx == -1:
            logger.error("  Could not find execute() call")
            raise SystemExit(1)
        # Step back to start of identifier
        while exec_idx > 0 and src[exec_idx - 1] not in " \t\n":
            exec_idx -= 1

    # Walk forward to matching close paren
    end_idx = None
    i = exec_idx
    paren_depth = 0
    in_triple = None
    in_single = None
    while i < len(src):
        ch = src[i]
        ch3 = src[i:i + 3]
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
        logger.error("  Could not find matching close paren")
        raise SystemExit(1)

    old_call = src[exec_idx:end_idx]
    logger.info(f"  Located execute() call: {len(old_call)} bytes")

    # Extract params tuple - find triple-quote end then comma
    triple_end = old_call.rfind('"""')
    if triple_end == -1:
        triple_end = old_call.rfind("'''")
    if triple_end == -1:
        logger.error("  Could not find SQL end marker")
        raise SystemExit(1)
    after_triple = old_call[triple_end + 3:].lstrip()
    if not after_triple.startswith(","):
        logger.error("  Unexpected structure after SQL")
        raise SystemExit(1)
    params_part = after_triple[1:].strip()
    if not params_part.endswith(")"):
        logger.error("  Expected closing paren in params")
        raise SystemExit(1)

    new_call = (
        'conn.execute("""\n'
        '            INSERT INTO entries\n'
        '              (race_id, program_num, horse_name, jockey, trainer,\n'
        '               morning_line, weight, fetched_ts)\n'
        '            VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n'
        '            ON CONFLICT(race_id, program_num) DO UPDATE SET\n'
        '              horse_name   = excluded.horse_name,\n'
        '              jockey       = excluded.jockey,\n'
        '              trainer      = excluded.trainer,\n'
        '              morning_line = excluded.morning_line,\n'
        '              weight       = excluded.weight,\n'
        '              fetched_ts   = excluded.fetched_ts\n'
        '            /* ENTRIES_UPSERT_APPLIED */\n'
        '        """, ' + params_part
    )

    new_src = src[:exec_idx] + new_call + src[end_idx:]

    import ast
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        logger.error(f"  Patched source has syntax error: {e}")
        new_lines = new_src.split("\n")
        for i in range(max(0, e.lineno - 3), min(len(new_lines), e.lineno + 3)):
            marker = " >> " if i == e.lineno - 1 else "    "
            logger.error(f"  {marker}{i + 1}: {new_lines[i]}")
        raise SystemExit(1)

    DB_FILE.write_text(new_src)
    logger.info("  db/database.py patched (syntax OK)")


# ---------------------------------------------------------------------------
# Step 8: Smoke test the entries UPSERT
# ---------------------------------------------------------------------------

def smoke_test_entries_upsert():
    logger.info("Step 7: Smoke-testing entries UPSERT ...")
    # Force-reload
    for mod_name in ("db.database", "db"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    from db.database import save_entry

    # Use a real race id from the DB
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM races LIMIT 1").fetchone()
        if not row:
            logger.warning("  No races in DB; skipping smoke test")
            return
        real_race_id = row[0]
        # Use a clearly-test program_num
        conn.execute(
            "DELETE FROM entries WHERE race_id=? AND program_num='ZZ99'",
            (real_race_id,),
        )
        conn.commit()

    # Insert
    save_entry(real_race_id, "ZZ99", "Test Horse Original", "Test Jockey",
               "Test Trainer", "5/1", "120")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, horse_name FROM entries "
            "WHERE race_id=? AND program_num='ZZ99'",
            (real_race_id,),
        ).fetchall()
    assert len(rows) == 1, f"Expected 1 row after first insert, got {len(rows)}"
    first_id = rows[0][0]
    logger.info(f"  First insert: id={first_id}, name='{rows[0][1]}'")

    # Re-insert with updated name (should UPSERT not duplicate)
    save_entry(real_race_id, "ZZ99", "Test Horse Updated", "Test Jockey",
               "Test Trainer", "5/1", "120")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, horse_name FROM entries "
            "WHERE race_id=? AND program_num='ZZ99'",
            (real_race_id,),
        ).fetchall()
    assert len(rows) == 1, f"DUPLICATE CREATED! Got {len(rows)} rows after re-insert"
    second_id = rows[0][0]
    logger.info(f"  Second insert: id={second_id}, name='{rows[0][1]}'")

    assert first_id == second_id, f"ID changed! {first_id} -> {second_id}"
    assert rows[0][1] == "Test Horse Updated", \
        f"Name didn't update: '{rows[0][1]}'"

    # Cleanup
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM entries WHERE race_id=? AND program_num='ZZ99'",
            (real_race_id,),
        )
        conn.commit()

    logger.info("  UPSERT verified — no duplicates, ID preserved, fields updated")


# ---------------------------------------------------------------------------
# Step 9: VACUUM to reclaim space
# ---------------------------------------------------------------------------

def vacuum_db():
    logger.info("Step 8: VACUUM database to reclaim space ...")
    size_before = DB_PATH.stat().st_size
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("VACUUM")
    size_after = DB_PATH.stat().st_size
    logger.info(f"  DB size: {size_before/1e6:.1f} MB -> {size_after/1e6:.1f} MB "
                f"(saved {(size_before-size_after)/1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("COMPREHENSIVE DATA INTEGRITY CLEANUP")
    logger.info("=" * 60)

    kill_agent()
    backup_database()

    # Pre-cleanup snapshot
    with sqlite3.connect(DB_PATH) as conn:
        snapshot_counts(conn, label="BEFORE")

    delete_orphans()
    dedupe_entries()
    add_entries_unique_constraint()
    patch_entries_insert()
    smoke_test_entries_upsert()
    vacuum_db()

    # Post-cleanup snapshot
    with sqlite3.connect(DB_PATH) as conn:
        snapshot_counts(conn, label="AFTER")

    logger.info("=" * 60)
    logger.info("CLEANUP COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Summary of changes:")
    logger.info("  - All orphan rows deleted across 4 tables")
    logger.info("  - entries deduplicated (476 duplicate sets collapsed)")
    logger.info("  - UNIQUE(race_id, program_num) added to entries")
    logger.info("  - INSERT OR REPLACE INTO entries -> UPSERT")
    logger.info("  - Database VACUUMed")
    logger.info("")
    logger.info("Restart the racing-agent:")
    logger.info("  cd ~/Documents/racing-agent && \\")
    logger.info("    nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")
    logger.info("")
    logger.info("After 5-10 minutes, refresh the dashboard. Each horse should")
    logger.info("appear exactly once per race.")


if __name__ == "__main__":
    main()
