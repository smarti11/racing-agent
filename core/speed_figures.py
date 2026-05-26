"""
Speed Figure Calculator
========================
Estimates speed figures from past performance times.

Without a paid Beyer/Equibase subscription we can't get
actual past performance times, so we use morning line odds
as a proxy for speed figure estimation.

A horse at 2/1 morning line is expected to be faster than
a horse at 20/1. We convert odds to an estimated speed figure
on the standard 0-120 Beyer scale.

Phase 3 will add actual past performance scraping.
"""

import logging

logger = logging.getLogger("racing_agent")

# Beyer speed figure ranges by class level
CLASS_BASE_FIGURES = {
    "grade 1":        105,
    "grade 2":         98,
    "grade 3":         92,
    "stakes":          88,
    "allowance":       82,
    "optional":        78,
    "maiden special":  72,
    "maiden claiming": 65,
    "claiming":        68,
    "starter":         70,
    "unknown":         75,
}


def odds_to_speed_figure(morning_line: str, class_level: str = "unknown") -> float:
    """
    Convert morning line odds to estimated speed figure.
    
    Uses odds as a proxy for expected performance:
    - Favorite (even money to 2/1): top of class range
    - Mid-range (3/1 to 8/1): middle of class range  
    - Longshot (10/1+): bottom of class range
    
    Returns estimated Beyer-equivalent speed figure.
    """
    base = get_class_base(class_level)
    
    try:
        ml = parse_odds(morning_line)
        if ml is None:
            return float(base)
        
        # Convert odds to probability
        prob = 1 / (ml + 1)
        
        # Scale within ±15 points of base based on probability
        # Favorite (prob ~0.5) gets +12, longshot (prob ~0.05) gets -8
        adjustment = (prob - 0.15) * 50  # roughly -7 to +18
        adjustment = max(-10, min(15, adjustment))
        
        figure = base + adjustment
        return round(figure, 1)
        
    except Exception:
        return float(base)


def parse_odds(odds_str: str):
    """Parse odds string like '5/2', '7/5', '6/1', 'EVN' to decimal."""
    if not odds_str or odds_str in ["—", "-", "", "N/A"]:
        return None
    
    odds_str = str(odds_str).strip().upper()
    
    if odds_str in ["EVN", "EVEN", "1/1"]:
        return 1.0
    
    try:
        if "/" in odds_str:
            num, den = odds_str.split("/")
            return float(num) / float(den)
        return float(odds_str)
    except Exception:
        return None


def get_class_base(conditions: str) -> int:
    """Get base speed figure for race conditions/class."""
    if not conditions:
        return CLASS_BASE_FIGURES["unknown"]
    
    cond_lower = conditions.lower()
    
    for key, value in CLASS_BASE_FIGURES.items():
        if key in cond_lower:
            return value
    
    return CLASS_BASE_FIGURES["unknown"]


def estimate_figures_for_race(entries: list, conditions: str) -> dict:
    """
    Estimate speed figures for all horses in a race.
    Returns dict of {program_num: speed_figure}
    """
    figures = {}
    for entry in entries:
        if entry.get("scratched"):
            continue
        prog = entry.get("program_num", "")
        ml = entry.get("morning_line", "")
        fig = odds_to_speed_figure(ml, conditions or "")
        figures[prog] = fig
    return figures
