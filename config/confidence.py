"""Confidence calibration — score gap + morning line + track baseline.

Derived from 1,085 HIGH-conf rank-1 picks (2026-05-24 through 2026-06-20).
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


def calibrate_confidence(
    score_gap: float,
    ml_decimal: Optional[float],
    track_code: str = "",
) -> str:
    """Return HIGH / MEDIUM / LOW using gap, price, and track baseline."""
    min_high = _min_gap_for_high(ml_decimal, track_code or "")

    if score_gap >= min_high:
        return "HIGH"
    if score_gap >= GAP_MEDIUM:
        return "MEDIUM"
    return "LOW"
