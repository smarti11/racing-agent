#!/usr/bin/env python3
"""Retrain isotonic calibrator from graded agent picks.

Trains on every active runner (agent_entry_scores), not just each race's
rank-1 favorite. The calibrator is applied via cal.transform() to every
active horse in the field (core/pick_manager.py), and the actionable/value
bet list is specifically drawn from non-favorite, longer-priced horses
(config/market.py ACTIONABLE_MIN_DECIMAL = 6.0, i.e. 5/1+). A calibrator
fit only on rank-1 outcomes is validated on a different population than
the one it's actually pricing bets for. Training on the full active-runner
population closes that gap and gives a far larger sample besides.
"""

import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.calibrator import IsotonicCalibrator
from db.database import get_conn, init_db

logger = logging.getLogger(__name__)
MODELS_DIR = ROOT / "models"


def load_training_data(min_samples: int = 50):
    """Return (raw_probs, outcomes) for every active runner with a graded result."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT es.win_prob,
                   CASE WHEN es.program_num = res.winner_num THEN 1 ELSE 0 END AS won
            FROM agent_entry_scores es
            JOIN agent_picks ap ON ap.race_id = es.race_id
                AND ap.program_num = es.program_num
            JOIN races r ON r.id = es.race_id
            JOIN results res ON res.race_id = es.race_id
            WHERE es.win_prob IS NOT NULL
              AND es.win_prob > 0
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


def _backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.json.bak.{stamp}")
    shutil.copy2(path, backup_path)
    print(f"Backed up {path.name} → {backup_path.name}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()

    raw, outcomes = load_training_data()
    if len(raw) < 10:
        print(f"Not enough graded runners ({len(raw)}) — need at least 10 with win_prob")
        sys.exit(1)

    cal = IsotonicCalibrator()
    cal.fit(raw, outcomes)

    MODELS_DIR.mkdir(exist_ok=True)
    pick1_path = MODELS_DIR / "calibrator_pick1.json"
    full_path = MODELS_DIR / "calibrator.json"
    _backup(pick1_path)
    _backup(full_path)
    cal.save(str(pick1_path))
    cal.save(str(full_path))

    wins = sum(outcomes)
    print(f"Trained on {len(raw)} active runners ({wins} wins, {100*wins/len(raw):.1f}% actual)")
    print(f"Breakpoints: {len(cal._x_breakpoints)}")
    print(f"Saved → {pick1_path}")
    print(f"Saved → {full_path}")


if __name__ == "__main__":
    main()
