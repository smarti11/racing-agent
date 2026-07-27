"""WIN stake eligibility — single source of truth for bet placement."""

from __future__ import annotations

from typing import Optional, Tuple

from config.confidence import (
    MAX_ANTI_MARKET_REL_EDGE,
    MIN_PROB_FOR_HIGH,
    ML_SUPPORTED_RANK_MAX,
    relative_model_edge,
)
from config.meet_leaders import WEAK_SIGNAL_TRACKS

# Field sizes at or above this skip flat WIN stakes (Jul 24–26: >=11 → -59% ROI).
MAX_FIELD_SIZE_FOR_WIN = 10

# Pace roles blocked for WIN (Jul 24–26: S -59%, C variable).
WIN_BLOCKED_PACE_ROLES = frozenset({"C", "S"})


def win_stake_eligible(
    confidence: str,
    model_prob: Optional[float],
    market_prob: Optional[float],
    ml_rank: Optional[int],
    pace_role: Optional[str],
    field_size: int,
    track_code: str = "",
) -> Tuple[bool, str]:
    """Return (eligible, reason_code) for a flat $2 WIN on rank-1."""
    if (confidence or "").upper() != "HIGH":
        return False, "NOT_HIGH"

    if track_code in WEAK_SIGNAL_TRACKS:
        return False, "WEAK_TRACK"

    if model_prob is None or model_prob < MIN_PROB_FOR_HIGH:
        return False, "LOW_PROB"

    if ml_rank is None or ml_rank > ML_SUPPORTED_RANK_MAX:
        return False, "NOT_ML_TOP2"

    rel = relative_model_edge(model_prob, market_prob)
    if rel is not None and rel >= MAX_ANTI_MARKET_REL_EDGE:
        return False, "ANTI_MARKET"

    role = (pace_role or "").upper()
    if role in WIN_BLOCKED_PACE_ROLES:
        return False, f"PACE_{role}"

    if field_size > MAX_FIELD_SIZE_FOR_WIN:
        return False, "LARGE_FIELD"

    return True, "OK"


def win_bet_label(eligible: bool, confidence: str, short_chalk: bool = False) -> str:
    """Dashboard / pick bet_recommendation string."""
    if short_chalk:
        return "ITM ONLY"
    if eligible:
        return "$2.00 WIN"
    conf = (confidence or "").upper()
    if conf == "HIGH":
        return "ITM ONLY"
    if conf == "MEDIUM":
        return "tracked, not bet"
    return "$0.50 SHOW"
