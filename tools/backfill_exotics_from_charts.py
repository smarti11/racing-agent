"""Fill missing exacta/trifecta/superfecta payouts from Equibase chart PDFs.

Before 2026-10-19 the results parser only recognized "Exacta"/"Trifecta",
so Fort Erie races (Canadian "Exactor"/"Triactor") were saved with NULL
exotic payouts, which the ROI code reads as "no pool offered". This re-reads
the full-card chart PDF for each affected date and fills only NULL columns.
Payoffs are stored as printed, i.e. at the track's base wager, matching what
the mobile results page reports.

Usage:
    python3 tools/backfill_exotics_from_charts.py --track FE            # dry run
    python3 tools/backfill_exotics_from_charts.py --track FE --write
"""

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.chart_fetcher import fetch_chart_pdf, pdf_to_text
from db.database import get_conn

RACE_HEADER = re.compile(r"-\s+Race\s+(\d+)\s*$")
# "$1.00 Exactor   5-1   9.65   13,279"
WAGER = re.compile(
    r"\$\d+\.\d+\s+(Exacta|Exactor|Trifecta|Triactor|Superfecta)\s+"
    r"([0-9A-Z]+(?:-[0-9A-Z/]+)+)\s+([\d,]+\.\d+)"
)
COLUMN = {"Exacta": "exacta_payout", "Exactor": "exacta_payout",
          "Trifecta": "trifecta_payout", "Triactor": "trifecta_payout",
          "Superfecta": "superfecta_payout"}


def parse_card(text):
    """Returns {race_num: {column: (combo, payoff)}} from chart PDF text."""
    races, current = {}, None
    for line in text.splitlines():
        m = RACE_HEADER.search(line)
        if m:
            current = int(m.group(1))
            races.setdefault(current, {})
            continue
        if current is None:
            continue
        for kind, combo, payoff in WAGER.findall(line):
            races[current].setdefault(COLUMN[kind], (combo, float(payoff.replace(",", ""))))
    return races


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT x.race_id, r.race_date, r.race_num, x.winner_num, x.second_num,
                   x.third_num, x.exacta_payout, x.trifecta_payout, x.superfecta_payout
            FROM results x JOIN races r ON r.id = x.race_id
            WHERE r.track_code = ? AND (x.exacta_payout IS NULL OR x.trifecta_payout IS NULL)
            ORDER BY r.race_date, r.race_num
        """, (args.track,)).fetchall()

    by_date = {}
    for row in rows:
        by_date.setdefault(row["race_date"], []).append(row)

    updates, skipped = [], 0
    for race_date, races in by_date.items():
        pdf = fetch_chart_pdf(args.track, race_date.replace("-", ""), force=True)
        card = parse_card(pdf_to_text(pdf)) if pdf else {}
        time.sleep(1)
        for row in races:
            found = card.get(row["race_num"], {})
            ex = found.get("exacta_payout")
            # Sanity check: the chart's exacta must match our recorded 1-2.
            if ex and ex[0].split("-")[:2] != [row["winner_num"], row["second_num"]]:
                print(f"  MISMATCH {race_date} R{row['race_num']}: chart {ex[0]} vs "
                      f"result {row['winner_num']}-{row['second_num']}; skipped")
                skipped += 1
                continue
            vals = {col: v[1] for col, v in found.items() if row[col] is None}
            if vals:
                updates.append((row["race_id"], vals))
            else:
                skipped += 1
        print(f"{race_date}: {len(races)} races, chart had {len(card)}")

    print(f"\n{len(updates)} races to update, {skipped} skipped")
    if not args.write:
        print("dry run; pass --write to save")
        return
    with get_conn() as conn:
        for race_id, vals in updates:
            sets = ", ".join(f"{c} = ?" for c in vals)
            conn.execute(f"UPDATE results SET {sets} WHERE race_id = ?", (*vals.values(), race_id))
        conn.commit()
    print("saved")


if __name__ == "__main__":
    main()
