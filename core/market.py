"""Market probability normalization and Benter-style model blend.

Stage 1: fundamental softmax probabilities (core/probabilities.py)
Stage 2: logit blend with normalized market probabilities (this module)
Stage 3: edge scan across full field (scan_value_bets)
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional

from config.market import MARKET_BLEND_ALPHA, MIN_EDGE, TAKEOUT, VALUE_BET_MIN_DECIMAL
from core.kelly import compute_edge, kelly_fraction, parse_odds_to_decimal


def _logit(p: float, eps: float = 1e-6) -> float:
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def normalize_market_probs(
    odds_by_program: Dict[str, str],
    takeout: float = TAKEOUT,
) -> Dict[str, float]:
    """Convert odds strings to fair win probabilities that sum to 1.0."""
    raw: Dict[str, float] = {}
    for pgm, odds_str in odds_by_program.items():
        if not odds_str:
            continue
        dec = parse_odds_to_decimal(str(odds_str))
        if dec and dec > 1.0:
            raw[str(pgm)] = 1.0 / dec

    if not raw:
        return {}

    total = sum(raw.values())
    if total <= 0:
        return {}

    # Remove overround, then re-normalize to a proper distribution.
    fair = {k: (v / total) * (1.0 - takeout) for k, v in raw.items()}
    s = sum(fair.values())
    if s <= 0:
        return {}
    return {k: v / s for k, v in fair.items()}


def blend_race_probabilities(
    horses: List[dict],
    alpha: float = MARKET_BLEND_ALPHA,
) -> None:
    """Apply logit-space blend; sets final_prob on each horse in-place."""
    if not horses:
        return

    logits: List[float] = []
    for h in horses:
        model_p = h.get("calibrated_prob") or h.get("win_prob") or 0.0
        market_p = h.get("market_prob") or 0.0
        if market_p > 0 and model_p > 0:
            blended = alpha * _logit(model_p) + (1.0 - alpha) * _logit(market_p)
        elif model_p > 0:
            blended = _logit(model_p)
        elif market_p > 0:
            blended = _logit(market_p)
        else:
            blended = _logit(1.0 / len(horses))
        logits.append(blended)

    probs = [_sigmoid(x) for x in logits]
    total = sum(probs)
    if total <= 0:
        uniform = 1.0 / len(horses)
        for h in horses:
            h["final_prob"] = uniform
        return

    for h, p in zip(horses, probs):
        h["final_prob"] = p / total


def _best_odds_for_horse(
    program_num: str,
    live_odds: Optional[Dict[str, str]],
    ml_map: Optional[Dict[str, str]],
) -> tuple[Optional[str], str]:
    """Return (odds_str, source) preferring live over morning line."""
    pgm = str(program_num)
    live = (live_odds or {}).get(pgm)
    if live:
        return live, "live"
    ml = (ml_map or {}).get(pgm)
    if ml:
        return ml, "ml"
    return None, ""


def enrich_race_with_market(
    horses: List[dict],
    live_odds: Optional[Dict[str, str]] = None,
    ml_map: Optional[Dict[str, str]] = None,
    alpha: float = MARKET_BLEND_ALPHA,
    takeout: float = TAKEOUT,
) -> None:
    """Attach market_prob, final_prob, edge, kelly_f, and corrected value."""
    if not horses:
        return

    odds_input: Dict[str, str] = {}
    for h in horses:
        pgm = str(h.get("program_num", ""))
        odds_str, source = _best_odds_for_horse(pgm, live_odds, ml_map)
        h["odds_str"] = odds_str
        h["odds_source"] = source
        if odds_str:
            odds_input[pgm] = odds_str

    market_probs = normalize_market_probs(odds_input, takeout=takeout)
    for h in horses:
        pgm = str(h.get("program_num", ""))
        h["market_prob"] = market_probs.get(pgm, 0.0)
        if h.get("calibrated_prob") is None:
            h["calibrated_prob"] = h.get("win_prob")

    blend_race_probabilities(horses, alpha=alpha)

    for h in horses:
        final_p = h.get("final_prob") or 0.0
        mkt_p = h.get("market_prob") or 0.0
        odds_str = h.get("odds_str")
        h["edge"] = compute_edge(final_p, odds_str, takeout) if odds_str else None
        h["kelly_f"] = kelly_fraction(final_p, odds_str, takeout) if odds_str else 0.0
        if mkt_p > 0 and final_p > 0:
            h["value"] = round((final_p - mkt_p) / mkt_p * 100, 1)
        else:
            h["value"] = 0.0


def scan_value_bets(
    horses: List[dict],
    min_edge: float = MIN_EDGE,
    min_decimal: float = VALUE_BET_MIN_DECIMAL,
) -> List[dict]:
    """Return all runners with positive edge, sorted by edge descending."""
    bets: List[dict] = []
    for h in horses:
        edge = h.get("edge")
        if edge is None or edge < min_edge:
            continue
        dec = parse_odds_to_decimal(h.get("odds_str") or "")
        if dec and dec < min_decimal:
            continue
        bets.append(h)
    bets.sort(key=lambda x: x.get("edge") or 0.0, reverse=True)
    return bets


def clean_odds_text(text: str) -> Optional[str]:
    """Extract a single odds fraction from Equibase desktop cell text."""
    if not text:
        return None
    s = re.sub(r"\s+", " ", text.strip())
    if not s or s.upper() in ("SCR", "-", "N/A"):
        return None
    # Cell may show "5/2" or "5-2" or "12" (meaning 12/1)
    for pat in (
        r"(\d+\.?\d*\s*[/\-]\s*\d+\.?\d*)",
        r"^(\d+\.?\d*)$",
    ):
        m = re.search(pat, s)
        if m:
            token = m.group(1).replace("-", "/")
            if parse_odds_to_decimal(token):
                return token
    return None
