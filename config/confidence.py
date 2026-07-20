"""Confidence calibration — score gap + market alignment + pace + track baseline.

Gates tuned from Jul 13–19 2026 graded performance:
  - Anti-market relative edges (>=50%) hit ~15% win / -43% ROI
  - Closers (pace C) hit ~3–8% for WIN
  - Prob < 20% near-useless for WIN stakes
  - MEDIUM previously underperformed LOW when miscalibrated
"""

from typing import Optional

from config.meet_leaders import WEAK_SIGNAL_TRACKS

# Historical HIGH-conf win rate by track (min ~20 graded picks in baseline window).
# Unknown tracks default to DEFAULT_TRACK_HIGH_WIN_RATE.
TRACK_HIGH_WIN_RATE = {
    "DEL": 0.444,
    "EMD": 0.360,
    "EVD": 0.353,
    "WO": 0.333,
    "TDN": 0.333,
    "BAQ": 0.280,
    "BTP": 0.280,
    "HAW": 0.260,
    "FMT": 0.250,
    "PEN": 0.240,
    "CD": 0.220,
    "LRL": 0.192,
    "CT": 0.172,
    "IND": 0.167,
    "CBY": 0.158,
    "PID": 0.152,
}

DEFAULT_TRACK_HIGH_WIN_RATE = 0.250

# Score-gap thresholds (top horse minus second horse)
GAP_HIGH_DEFAULT = 8
GAP_MEDIUM = 4
GAP_HIGH_LONGSHOT = 12   # 5/1+ (decimal >= 5.0)
GAP_HIGH_MIDPRICE = 10   # just above 4/1 (decimal > 4.0)

# Tracks below this HIGH-conf win rate never receive HIGH confidence
TRACK_HIGH_FLOOR = 0.20

# --- Performance gates (Jul 2026) ---
# Relative edge = (model_prob - market_prob) / market_prob
MAX_ANTI_MARKET_REL_EDGE = 0.50
# Top-2 on morning line counts as market-supported
ML_SUPPORTED_RANK_MAX = 2
# Soft-cap WIN / elevated confidence by model probability
MIN_PROB_FOR_HIGH = 0.25
MIN_PROB_FOR_MEDIUM = 0.20
# Pace roles that may receive elevated confidence when scenario favors them
CLOSER_FAVORABLE_SCENARIOS = frozenset({"CONTESTED", "CLOSERS_RACE"})


def _min_gap_for_high(ml_decimal: Optional[float], track_code: str) -> float:
    """Minimum score gap required to label a pick HIGH."""
    if ml_decimal is not None:
        if ml_decimal >= 5.0:
            gap = GAP_HIGH_LONGSHOT
        elif ml_decimal > 4.0:
            gap = GAP_HIGH_MIDPRICE
        else:
            gap = GAP_HIGH_DEFAULT
    else:
        gap = GAP_HIGH_DEFAULT

    track_wr = TRACK_HIGH_WIN_RATE.get(track_code, DEFAULT_TRACK_HIGH_WIN_RATE)
    if track_code in WEAK_SIGNAL_TRACKS or track_wr < TRACK_HIGH_FLOOR:
        return 999.0  # cap at MEDIUM — weak tracks / chronic underperformers
    if track_wr < 0.25:
        gap = max(gap, GAP_HIGH_MIDPRICE)
    return gap


def _conf_rank(conf: str) -> int:
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(conf, 1)


def _cap_confidence(conf: str, ceiling: str) -> str:
    """Return the lower of conf and ceiling."""
    if _conf_rank(conf) <= _conf_rank(ceiling):
        return conf
    return ceiling


def relative_model_edge(
    model_prob: Optional[float],
    market_prob: Optional[float],
) -> Optional[float]:
    """(model - market) / market. None if market missing."""
    if model_prob is None or market_prob is None or market_prob <= 0:
        return None
    return (model_prob - market_prob) / market_prob


def calibrate_confidence(
    score_gap: float,
    ml_decimal: Optional[float],
    track_code: str = "",
    *,
    win_prob: Optional[float] = None,
    market_prob: Optional[float] = None,
    pace_role: Optional[str] = None,
    ml_rank: Optional[int] = None,
    pace_scenario_name: Optional[str] = None,
) -> str:
    """Return HIGH / MEDIUM / LOW using gap, price, track, market, pace, and prob.

    Extra keyword gates (all optional for backward compatibility):
      win_prob / market_prob — anti-market edge + min-prob soft-caps
      pace_role — closer (C) WIN veto
      ml_rank — 1 = ML favorite; <=2 counts as market-supported
      pace_scenario_name — allows limited closer exception when contested
    """
    min_high = _min_gap_for_high(ml_decimal, track_code or "")

    if score_gap >= min_high:
        conf = "HIGH"
    elif score_gap >= GAP_MEDIUM:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    market_supported = (
        ml_rank is not None and ml_rank <= ML_SUPPORTED_RANK_MAX
    )

    # Gate 1 — hard-cap anti-market edges without ML support
    rel_edge = relative_model_edge(win_prob, market_prob)
    if (
        rel_edge is not None
        and rel_edge >= MAX_ANTI_MARKET_REL_EDGE
        and not market_supported
    ):
        return "LOW"

    # Gate 2 — closer (C) WIN veto (limited exception when pace favors closers)
    role = (pace_role or "").upper()
    if role == "C":
        scenario = (pace_scenario_name or "").upper()
        if (
            scenario in CLOSER_FAVORABLE_SCENARIOS
            and market_supported
            and win_prob is not None
            and win_prob >= MIN_PROB_FOR_HIGH
        ):
            conf = _cap_confidence(conf, "MEDIUM")
        else:
            return "LOW"

    # Gate 3 — probability soft-caps for elevated confidence / WIN stakes
    if win_prob is not None:
        if conf == "HIGH" and win_prob < MIN_PROB_FOR_HIGH:
            conf = "MEDIUM" if win_prob >= MIN_PROB_FOR_MEDIUM else "LOW"
        elif conf == "MEDIUM" and win_prob < MIN_PROB_FOR_MEDIUM:
            conf = "LOW"

    # Gate 3b — HIGH also requires market support (ML top-2)
    if conf == "HIGH" and ml_rank is not None and not market_supported:
        conf = "MEDIUM"

    return conf
