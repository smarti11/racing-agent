"""
Fit the morning-line-anchored conditional logit (core/anchored_model.py).

Trains on graded races before --split, reports out-of-sample performance on
races from --split onward against the current production picks and the ML
favorite, then (with --write) refits on all data and saves
models/anchored_weights.json. Pure Python so it runs on the agent's own
interpreter.

    python tools/fit_anchored_model.py                       # evaluate only
    python tools/fit_anchored_model.py --write               # evaluate + save
    python tools/fit_anchored_model.py --split 2026-10-01 --write

Re-run monthly as results accumulate. Data before 2026-05-26 is excluded
(stub-field handicapping bug — see CLAUDE.md).
"""

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.anchored_model import (  # noqa: E402
    FEATURES, WEIGHTS_PATH, featurize, ml_probabilities, race_probabilities,
)

DB_PATH = ROOT / "db" / "racing.db"
CLEAN_DATA_START = "2026-05-26"
L2 = 1e-3  # ridge penalty on non-ML weights (per race-averaged objective)


def load_races(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT s.race_id, s.program_num, s.speed_fig, s.j_win_pct, s.t_win_pct,
               s.form, s.class_change, s.trainer_hot, s.pace_role,
               e.morning_line, r.race_date, res.winner_num, res.winner_win_payout,
               (SELECT rank FROM agent_picks p
                 WHERE p.race_id = s.race_id AND p.program_num = s.program_num) AS pick_rank
        FROM agent_entry_scores s
        JOIN races r     ON r.id = s.race_id
        JOIN results res ON res.race_id = s.race_id
        LEFT JOIN entries e ON e.race_id = s.race_id AND e.program_num = s.program_num
        WHERE r.race_date >= ? AND COALESCE(e.scratched, 0) = 0
        ORDER BY s.race_id, s.program_num
    """, (CLEAN_DATA_START,)).fetchall()
    conn.close()

    by_race = defaultdict(list)
    for r in rows:
        by_race[r["race_id"]].append(dict(r))

    races = []
    for rid, horses in by_race.items():
        winners = [i for i, h in enumerate(horses) if h["program_num"] == h["winner_num"]]
        if len(horses) < 2 or len(winners) != 1:
            continue  # winner not among scored runners (late scratch/entry mismatch)
        ml = ml_probabilities([h["morning_line"] for h in horses])
        if ml is None:
            continue
        races.append({
            "race_id": rid,
            "date": horses[0]["race_date"],
            "horses": horses,
            "ml": ml,
            "x": featurize(horses, ml),
            "winner": winners[0],
            "payout": horses[0]["winner_win_payout"] or 0.0,
            "pick1": next((i for i, h in enumerate(horses) if h["pick_rank"] == 1), None),
        })
    return races


def _solve(a, b):
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def fit(races, iters=25):
    """Newton-Raphson on the conditional-logit log-likelihood."""
    k = len(FEATURES)
    w = [0.0] * k
    w[FEATURES.index("log_ml")] = 1.0
    n = len(races)
    for it in range(iters):
        grad = [0.0] * k
        hess = [[0.0] * k for _ in range(k)]
        ll = 0.0
        wd = dict(zip(FEATURES, w))
        for race in races:
            xs = [[f[name] for name in FEATURES] for f in race["x"]]
            p = race_probabilities(race["x"], wd)
            ll += math.log(max(p[race["winner"]], 1e-12))
            mean = [sum(p[i] * xs[i][j] for i in range(len(xs))) for j in range(k)]
            xw = xs[race["winner"]]
            for j in range(k):
                grad[j] += xw[j] - mean[j]
            for i, xi in enumerate(xs):
                pi = p[i]
                if pi < 1e-9:
                    continue
                d = [xi[j] - mean[j] for j in range(k)]
                for a in range(k):
                    pa = pi * d[a]
                    row = hess[a]
                    for b in range(a, k):
                        row[b] += pa * d[b]
        for a in range(k):
            for b in range(a):
                hess[a][b] = hess[b][a]
        # ridge on everything except the ML anchor
        for j, name in enumerate(FEATURES):
            if name != "log_ml":
                grad[j] -= L2 * n * w[j]
                hess[j][j] += L2 * n
        step = _solve(hess, grad)
        w = [wi + si for wi, si in zip(w, step)]
        if max(abs(s) for s in step) < 1e-6:
            break
    return dict(zip(FEATURES, w)), -ll / n


def evaluate(races, weights):
    """Out-of-sample comparison: new model vs current pick #1 vs ML favorite."""
    out = {"races": len(races)}
    ll_model = ll_ml = 0.0
    tallies = {"model": [0, 0, 0.0], "current": [0, 0, 0.0], "ml_fav": [0, 0, 0.0]}  # n, wins, return

    def tally(key, idx, race):
        t = tallies[key]
        t[0] += 1
        if idx == race["winner"]:
            t[1] += 1
            t[2] += race["payout"]

    top_probs = []
    for race in races:
        p = race_probabilities(race["x"], weights)
        ll_model -= math.log(max(p[race["winner"]], 1e-12))
        ll_ml -= math.log(max(race["ml"][race["winner"]], 1e-12))
        best = max(range(len(p)), key=p.__getitem__)
        top_probs.append(p[best])
        tally("model", best, race)
        tally("ml_fav", max(range(len(p)), key=race["ml"].__getitem__), race)
        if race["pick1"] is not None:
            tally("current", race["pick1"], race)
    out["logloss_model"] = ll_model / len(races)
    out["logloss_ml"] = ll_ml / len(races)
    for key, (n, wins, ret) in tallies.items():
        out[key] = {"n": n, "win_pct": 100.0 * wins / n if n else 0.0,
                    "roi_pct": 100.0 * (ret / (2.0 * n) - 1) if n else 0.0}
    return out, top_probs


def confidence_thresholds(top_probs, high_share=0.30, medium_share=0.32):
    """Prob cutoffs reproducing roughly today's HIGH/MEDIUM/LOW mix."""
    s = sorted(top_probs, reverse=True)
    return {"HIGH": round(s[int(len(s) * high_share)], 4),
            "MEDIUM": round(s[int(len(s) * (high_share + medium_share))], 4)}


def print_eval(label, ev):
    print(f"\n{label}: {ev['races']} races")
    print(f"  log loss (winner)  model {ev['logloss_model']:.4f}   morning line {ev['logloss_ml']:.4f}")
    for key, name in (("model", "anchored model #1"), ("current", "current pick #1"), ("ml_fav", "ML favorite")):
        t = ev[key]
        print(f"  {name:18} n={t['n']:5}  win {t['win_pct']:5.1f}%  $2 win ROI {t['roi_pct']:+6.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--split", default=None, help="test-set start date (default: last ~25%% of dates)")
    ap.add_argument("--write", action="store_true", help=f"refit on all data and write {WEIGHTS_PATH.name}")
    args = ap.parse_args()

    races = load_races(args.db)
    dates = sorted({r["date"] for r in races})
    split = args.split or dates[int(len(dates) * 0.75)]
    train = [r for r in races if r["date"] < split]
    test = [r for r in races if r["date"] >= split]
    print(f"{len(races)} graded races {dates[0]}..{dates[-1]}; train {len(train)} (<{split}), test {len(test)}")

    w_train, _ = fit(train)
    print("weights (train):", {k: round(v, 3) for k, v in w_train.items()})
    ev, _ = evaluate(test, w_train)
    print_eval("OUT-OF-SAMPLE", ev)

    if args.write:
        w_all, ll = fit(races)
        _, top_probs = evaluate(races, w_all)
        model = {
            "version": 1,
            "fitted_at": datetime.now().isoformat(timespec="seconds"),
            "data": {"start": dates[0], "end": dates[-1], "races": len(races)},
            "features": FEATURES,
            "weights": w_all,
            "confidence_thresholds": confidence_thresholds(top_probs),
            "holdout": {"split": split, **ev},
        }
        WEIGHTS_PATH.write_text(json.dumps(model, indent=2))
        print(f"\nWrote {WEIGHTS_PATH} (all-data fit, train log loss {ll:.4f}); "
              f"confidence thresholds {model['confidence_thresholds']}")


if __name__ == "__main__":
    main()
