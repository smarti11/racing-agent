"""Backfill score and win_prob for historical agent_picks rows.

Usage:
    python3 tools/backfill_probabilities.py --limit 10    # test run
    python3 tools/backfill_probabilities.py               # full backfill
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import get_conn
from core.handicapper import handicap_race
from core.probabilities import scores_to_probabilities


def get_races_to_backfill(limit=None):
    with get_conn() as conn:
        sql = """
            SELECT DISTINCT r.id, r.race_date, r.track_name, r.race_num,
                   r.track_code, r.conditions, r.distance
            FROM races r
            JOIN agent_picks ap ON ap.race_id = r.id
            WHERE ap.score IS NULL
              AND r.race_date BETWEEN '2026-04-12' AND '2026-05-04'
            ORDER BY r.race_date, r.track_name, r.race_num
        """
        if limit:
            sql += f" LIMIT {limit}"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_entries(race_id):
    with get_conn() as conn:
        return [dict(e) for e in conn.execute(
            "SELECT * FROM entries WHERE race_id=? AND scratched=0",
            (race_id,)
        ).fetchall()]


def update_picks(race_id, prob_map, score_map, ml_map):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, program_num FROM agent_picks WHERE race_id=?",
            (race_id,)
        ).fetchall()
        for row in rows:
            pgm = row["program_num"]
            conn.execute("""
                UPDATE agent_picks
                SET score = ?, win_prob = ?, morning_line = ?
                WHERE id = ?
            """, (
                score_map.get(pgm),
                prob_map.get(pgm),
                ml_map.get(pgm),
                row["id"]
            ))


def backfill(limit=None, verbose=False):
    races = get_races_to_backfill(limit=limit)
    total = len(races)
    print(f"Found {total} races to backfill")
    if total == 0:
        return

    start = time.time()
    success = 0
    failed = 0
    skipped = 0

    for i, race in enumerate(races, 1):
        try:
            entries = get_entries(race["id"])
            if not entries:
                skipped += 1
                continue

            scored = handicap_race(
                entries,
                race["conditions"] or "",
                race["track_code"] or "",
                race["distance"] or ""
            )
            if not scored:
                skipped += 1
                continue

            scores_to_probabilities(scored, temperature=8.0)

            score_map = {s["program_num"]: s.get("score") for s in scored}
            prob_map = {s["program_num"]: s.get("win_prob") for s in scored}
            ml_map = {e.get("program_num"): e.get("morning_line") for e in entries}

            update_picks(race["id"], prob_map, score_map, ml_map)
            success += 1

        except Exception as e:
            failed += 1
            if verbose:
                print(f"  ERROR on race {race['id']} ({race['track_name']} R{race['race_num']}): {e}")

        if i % 25 == 0 or i == total or limit:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  [{i}/{total}] success={success} fail={failed} skip={skipped} "
                  f"elapsed={elapsed:.1f}s rate={rate:.1f}/s eta={eta:.0f}s")

    elapsed = time.time() - start
    print(f"\nDone. {success} succeeded, {failed} failed, {skipped} skipped in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Process only N races (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Print errors")
    args = parser.parse_args()
    backfill(limit=args.limit, verbose=args.verbose)
