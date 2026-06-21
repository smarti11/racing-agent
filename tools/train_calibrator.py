#!/usr/bin/env python3
"""Retrain isotonic calibrator from graded agent picks."""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.calibrator import IsotonicCalibrator
from db.database import get_conn, init_db

logger = logging.getLogger(__name__)
MODELS_DIR = ROOT / "models"


def load_training_data(min_samples: int = 50):
    """Return (raw_probs, outcomes) from rank-1 picks with results."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ap.win_prob,
                   CASE WHEN ap.program_num = res.winner_num THEN 1 ELSE 0 END AS won
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            JOIN results res ON res.race_id = ap.race_id
            WHERE ap.rank = 1
              AND ap.win_prob IS NOT NULL
              AND ap.win_prob > 0
              AND ap.data_quality = 'OK'
            ORDER BY r.race_date
        """).fetchall()

    raw = [float(r["win_prob"]) for r in rows]
    outcomes = [int(r["won"]) for r in rows]
    if len(raw) < min_samples:
        logger.warning(
            f"Only {len(raw)} samples (need {min_samples}) — calibrator may be unstable"
        )
    return raw, outcomes


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()

    raw, outcomes = load_training_data()
    if len(raw) < 10:
        print(f"Not enough graded picks ({len(raw)}) — need at least 10 with win_prob")
        sys.exit(1)

    cal = IsotonicCalibrator()
    cal.fit(raw, outcomes)

    MODELS_DIR.mkdir(exist_ok=True)
    pick1_path = MODELS_DIR / "calibrator_pick1.json"
    full_path = MODELS_DIR / "calibrator.json"
    cal.save(str(pick1_path))
    cal.save(str(full_path))

    wins = sum(outcomes)
    print(f"Trained on {len(raw)} rank-1 picks ({wins} wins, {100*wins/len(raw):.1f}% actual)")
    print(f"Breakpoints: {len(cal._x_breakpoints)}")
    print(f"Saved → {pick1_path}")
    print(f"Saved → {full_path}")


if __name__ == "__main__":
    main()
