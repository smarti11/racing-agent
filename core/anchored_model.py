"""
Morning-line-anchored win probabilities (conditional logit).

The handicapper's raw score ranks horses on fundamentals alone and ignores the
market, which made the rank-1 pick win less often than the ML favorite
(24% vs 33%, 2026-05..10). Here the ML-implied probability is the prior and the
handicapper's features adjust it:

    p_i ∝ exp(w_ml * log(ml_p_i) + Σ_k w_k * x_ik)

Weights are fit by tools/fit_anchored_model.py and stored in
models/anchored_weights.json. featurize() is shared by the fitter and the live
path so training and serving features can't drift apart.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

from core.market import parse_odds_to_decimal

logger = logging.getLogger(__name__)

WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "models" / "anchored_weights.json"

# Continuous handicapper outputs, z-scored within the race.
Z_FIELDS = {"speed_fig_z": "speed_fig", "j_win_pct_z": "j_win_pct", "t_win_pct_z": "t_win_pct"}

FEATURES = [
    "log_ml",
    "speed_fig_z", "j_win_pct_z", "t_win_pct_z",
    "last_win", "last_2_3", "no_form",
    "cls_drop", "cls_rise",
    "tr_hot", "tr_cold",
    "pace_E", "pace_EP", "pace_P",
]

_weights_cache: Optional[dict] = None


def load_weights(path: Path = WEIGHTS_PATH) -> Optional[dict]:
    global _weights_cache
    if _weights_cache is None:
        try:
            _weights_cache = json.loads(Path(path).read_text())
        except (OSError, ValueError) as e:
            logger.warning(f"Anchored model weights unavailable ({e}) — falling back to raw score ranking")
            return None
    return _weights_cache


def ml_probabilities(ml_odds: List[Optional[str]]) -> Optional[List[float]]:
    """Normalized ML-implied probabilities. Missing/unparseable lines get the
    field's median implied prob; returns None if no line parses at all."""
    raw = []
    for s in ml_odds:
        s = (s or "").strip()
        # parse_odds_to_decimal doesn't know even money, and it's always a
        # heavy favorite — imputing the field median would bury it.
        dec = 2.0 if s.upper() in ("EVN", "EVEN") else (parse_odds_to_decimal(s) if s else None)
        raw.append(1.0 / dec if dec and dec > 1.0 else None)
    known = sorted(r for r in raw if r is not None)
    if not known:
        return None
    median = known[len(known) // 2]
    raw = [r if r is not None else median for r in raw]
    total = sum(raw)
    return [r / total for r in raw]


def _zscores(values: List[Optional[float]]) -> List[float]:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return [0.0] * len(values)
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd == 0:
        return [0.0] * len(values)
    return [max(-3.0, min(3.0, (v - mean) / sd)) if v is not None else 0.0 for v in values]


def featurize(horses: List[dict], ml_probs: List[float]) -> List[Dict[str, float]]:
    """Feature dicts for one race. Each horse dict needs the keys persisted in
    agent_entry_scores: speed_fig, j_win_pct, t_win_pct, form, class_change,
    trainer_hot, pace_role."""
    rows = [{"log_ml": math.log(max(p, 1e-6))} for p in ml_probs]
    for zname, field in Z_FIELDS.items():
        for row, z in zip(rows, _zscores([h.get(field) for h in horses])):
            row[zname] = z
    for row, h in zip(rows, horses):
        form = h.get("form") or "---"
        last = form.split("-")[0]
        row["last_win"] = float(last == "1")
        row["last_2_3"] = float(last in ("2", "3"))
        row["no_form"] = float(form == "---")
        row["cls_drop"] = float(h.get("class_change") == "DROP")
        row["cls_rise"] = float(h.get("class_change") == "RISE")
        row["tr_hot"] = float(h.get("trainer_hot") == "HOT")
        row["tr_cold"] = float(h.get("trainer_hot") == "COLD")
        for role in ("E", "EP", "P"):
            row[f"pace_{role}"] = float(h.get("pace_role") == role)
    return rows


def race_probabilities(features: List[Dict[str, float]], weights: Dict[str, float]) -> List[float]:
    utils = [sum(weights.get(k, 0.0) * f.get(k, 0.0) for k in FEATURES) for f in features]
    m = max(utils)
    exps = [math.exp(u - m) for u in utils]
    s = sum(exps)
    return [e / s for e in exps]


def confidence_for(prob: float, thresholds: Dict[str, float]) -> str:
    if prob >= thresholds["HIGH"]:
        return "HIGH"
    if prob >= thresholds["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def apply_anchored_probs(horses: List[dict], ml_map: Dict[str, Optional[str]]) -> bool:
    """Set h["anchored_prob"] on each active horse. Returns False (leaving the
    horses untouched) when weights or morning lines are unavailable."""
    model = load_weights()
    if not model or not horses:
        return False
    # Live handicapper dicts carry jockey/trainer win% as *_db (that's what
    # save_agent_entry_scores persists as j_win_pct / t_win_pct).
    view = [{**h,
             "j_win_pct": h.get("j_win_pct_db", h.get("j_win_pct")),
             "t_win_pct": h.get("t_win_pct_db", h.get("t_win_pct"))} for h in horses]
    ml = ml_probabilities([ml_map.get(str(h.get("program_num"))) for h in horses])
    if ml is None:
        return False
    probs = race_probabilities(featurize(view, ml), model["weights"])
    for h, p in zip(horses, probs):
        h["anchored_prob"] = p
    return True
