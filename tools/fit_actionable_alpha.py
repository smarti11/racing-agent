#!/usr/bin/env python3
"""Sweep ACTIONABLE_BLEND_ALPHA against graded actionable-bet history.

select_actionable_bets() keeps the single largest edge per race per day —
a winner's-curse selection over model/market disagreement. This script
checks what blend weight the *actionable* population actually supports,
independent of MARKET_BLEND_ALPHA (which is fit for the general/favorite
population instead). Re-run periodically as actionable-bet history grows,
and update config/market.py ACTIONABLE_BLEND_ALPHA if the fit has moved.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db.database import get_conn


def _logit(p: float, eps: float = 1e-6) -> float:
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def load_graded_actionable_bets():
    """Return (model_prob, market_prob, won) for every graded actionable bet."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT vb.model_prob, vb.market_prob,
                   CASE WHEN ab.program_num = res.winner_num THEN 1 ELSE 0 END AS won
            FROM agent_actionable_bets ab
            JOIN agent_value_bets vb ON vb.race_id = ab.race_id
                AND vb.program_num = ab.program_num
            JOIN results res ON res.race_id = ab.race_id
            WHERE vb.model_prob IS NOT NULL AND vb.market_prob IS NOT NULL
              AND vb.market_prob > 0
        """).fetchall()
    return rows


def sweep(rows, step: float = 0.05):
    n = len(rows)
    wins = sum(r["won"] for r in rows)
    print(f"n={n}  actual_wins={wins}  actual_rate={100*wins/n:.1f}%\n")
    print(f"{'alpha':<8}{'expected_wins':<15}{'expected_rate':<15}{'brier':<10}")

    best = None
    alpha = 0.0
    while alpha <= 1.0 + 1e-9:
        exp_wins = 0.0
        brier = 0.0
        for r in rows:
            blended = alpha * _logit(r["model_prob"]) + (1 - alpha) * _logit(r["market_prob"])
            p = _sigmoid(blended)
            exp_wins += p
            brier += (p - r["won"]) ** 2
        brier /= n
        print(f"{alpha:<8.2f}{exp_wins:<15.2f}{100*exp_wins/n:<15.1f}{brier:<10.4f}")
        if best is None or brier < best[1]:
            best = (alpha, brier)
        alpha = round(alpha + step, 10)

    return best


def main():
    rows = load_graded_actionable_bets()
    if len(rows) < 30:
        print(f"Only {len(rows)} graded actionable bets — fit will be unstable")
    best_alpha, best_brier = sweep(rows)
    print(f"\nBest (min Brier) alpha ~= {best_alpha:.2f} (brier={best_brier:.4f})")
    print("Compare against config/market.py ACTIONABLE_BLEND_ALPHA")


if __name__ == "__main__":
    main()
