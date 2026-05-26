"""
Pace Scenario Analyzer
========================
Detects pace scenarios for a race based on post positions
and running style estimates. This is one of the most
powerful free handicapping tools available.

Key scenarios:
  LONE SPEED   — one horse likely to lead uncontested → BIG advantage
  CONTESTED    — 2-3 speed horses will fight for lead → likely to tire
  CLOSERS RACE — no early speed → closers have a big chance
  NORMAL       — balanced pace, no clear advantage

Also detects:
  - Rail advantage (inside posts on certain tracks)
  - Post position bias for route vs sprint
  - Likely pace shape (fast/slow/honest)
"""

import logging

logger = logging.getLogger("racing_agent")

# Tracks known for specific post position biases
RAIL_BIAS_TRACKS = {
    "KEE": {"sprint": "outside", "route": "inside"},   # Keeneland
    "SA":  {"sprint": "outside", "route": "outside"},  # Santa Anita
    "CD":  {"sprint": "inside",  "route": "inside"},   # Churchill Downs
    "GP":  {"sprint": "outside", "route": "outside"},  # Gulfstream
    "AQU": {"sprint": "inside",  "route": "inside"},   # Aqueduct
    "BEL": {"sprint": "outside", "route": "outside"},  # Belmont
    "SAR": {"sprint": "outside", "route": "outside"},  # Saratoga
    "DMR": {"sprint": "outside", "route": "outside"},  # Del Mar
    "OP":  {"sprint": "inside",  "route": "inside"},   # Oaklawn
    "TAM": {"sprint": "outside", "route": "outside"},  # Tampa Bay
}

# Distance classification
def is_route(distance_str: str) -> bool:
    """Returns True if race is a route (1 mile or more)."""
    if not distance_str:
        return False
    d = distance_str.lower()
    if "mile" in d:
        try:
            # "1 1/16 Miles" → route
            return True
        except Exception:
            return True
    if "furlong" in d:
        try:
            import re
            nums = re.findall(r'\d+\.?\d*', d)
            if nums and float(nums[0]) >= 8.0:
                return True
        except Exception:
            pass
    return False


def estimate_pace_style(post: int, field_size: int, morning_line: str = None) -> str:
    """
    Estimate a horse's pace style from post position and odds.
    Returns: E (early), EP (early-presser), P (presser), S (stalker), C (closer)
    
    Inside posts tend toward early speed.
    Favorites tend to be placed where trainers know they run best.
    Short-priced horses often have tactical speed.
    """
    if field_size <= 0:
        return "P"
    
    pct = post / field_size
    
    # Base style from post position
    if pct <= 0.15:
        style = "E"
    elif pct <= 0.30:
        style = "EP"
    elif pct <= 0.55:
        style = "P"
    elif pct <= 0.75:
        style = "S"
    else:
        style = "C"
    
    # Adjust for odds — favorites tend to have tactical ability
    if morning_line:
        try:
            from core.speed_figures import parse_odds
            ml = parse_odds(morning_line)
            if ml is not None and ml <= 2.0 and style in ["S", "C"]:
                style = "P"  # Favorites rarely win from way off pace
        except Exception:
            pass
    
    return style


def analyze_pace_scenario(entries: list, distance_str: str = "", track_code: str = "") -> dict:
    """
    Analyze the pace scenario for a race.
    
    Returns dict with:
      scenario: LONE_SPEED / CONTESTED / HONEST / CLOSERS_RACE
      pace_shape: FAST / HONEST / SLOW
      speed_horses: list of program numbers with early pace
      lone_speed: program number if lone speed exists
      advantage: which running style benefits
      notes: human-readable explanation
      post_bias: track post position bias if known
    """
    active = [e for e in entries if not e.get("scratched")]
    field_size = len(active)
    
    if field_size == 0:
        return {"scenario": "UNKNOWN", "notes": "No active entries"}
    
    # Estimate pace style for each horse
    pace_styles = {}
    for entry in active:
        post_raw = str(entry.get("post_position") or entry.get("program_num") or "1"); post = int("".join(c for c in post_raw if c.isdigit()) or "1")
        ml   = entry.get("morning_line", "")
        style = estimate_pace_style(post, field_size, ml)
        pace_styles[entry.get("program_num", "")] = style
    
    # Count speed horses (E and EP)
    speed_horses = [prog for prog, style in pace_styles.items() 
                    if style in ["E", "EP"]]
    closers      = [prog for prog, style in pace_styles.items() 
                    if style in ["S", "C"]]
    pressers     = [prog for prog, style in pace_styles.items()
                    if style in ["P", "EP"]]
    
    n_speed   = len(speed_horses)
    n_closers = len(closers)
    
    # Determine scenario
    if n_speed == 0:
        scenario  = "CLOSERS_RACE"
        pace_shape = "SLOW"
        advantage  = "CLOSER"
        notes = "No clear early speed — pace likely slow. Closers and pressers have big advantage."
    elif n_speed == 1:
        scenario  = "LONE_SPEED"
        pace_shape = "SLOW"
        advantage  = "EARLY"
        lone = speed_horses[0]
        # Find horse name
        for e in active:
            if e.get("program_num") == lone:
                notes = f"#{lone} {e.get('horse_name','')} has lone speed — uncontested lead is HUGE advantage. Lone speed wins ~35% of races."
                break
        else:
            notes = f"#{lone} has lone speed — uncontested lead is HUGE advantage."
    elif n_speed == 2:
        scenario  = "HONEST"
        pace_shape = "HONEST"
        advantage  = "PRESSER"
        notes = f"Two speed horses (#{', #'.join(speed_horses)}) — honest pace. Pressers and stalkers benefit."
    else:
        scenario  = "CONTESTED"
        pace_shape = "FAST"
        advantage  = "CLOSER"
        notes = f"{n_speed} speed horses ({', '.join('#'+p for p in speed_horses)}) — contested/fast pace. Closers big beneficiaries. Speed likely to tire."
    
    # Post position bias
    post_bias = ""
    if track_code and track_code.upper() in RAIL_BIAS_TRACKS:
        race_type = "route" if is_route(distance_str) else "sprint"
        bias = RAIL_BIAS_TRACKS[track_code.upper()].get(race_type, "")
        if bias:
            post_bias = f"{track_code} {race_type} bias: {bias.upper()} posts"
    
    return {
        "scenario":     scenario,
        "pace_shape":   pace_shape,
        "advantage":    advantage,
        "speed_horses": speed_horses,
        "closers":      closers,
        "pressers":     pressers,
        "pace_styles":  pace_styles,
        "lone_speed":   speed_horses[0] if scenario == "LONE_SPEED" else None,
        "notes":        notes,
        "post_bias":    post_bias,
        "field_size":   field_size,
    }


def pace_scenario_score_adjustment(program_num: str, scenario: dict) -> float:
    """
    Returns score adjustment (-10 to +15) based on pace scenario.
    Applied on top of base handicapping score.
    """
    if not scenario or scenario.get("scenario") == "UNKNOWN":
        return 0.0
    
    style = scenario.get("pace_styles", {}).get(program_num, "P")
    adv   = scenario.get("advantage", "")
    
    adjustments = {
        "LONE_SPEED": {"E": +15, "EP": +5, "P": -2, "S": -3, "C": -5},
        "CONTESTED":  {"E": -8,  "EP": -5, "P": +3, "S": +5, "C": +8},
        "HONEST":     {"E": +2,  "EP": +3, "P": +5, "S": +2, "C": -2},
        "CLOSERS_RACE":{"E":-3,  "EP": 0,  "P": +5, "S": +8, "C": +5},
    }
    
    scenario_name = scenario.get("scenario", "HONEST")
    adj_map = adjustments.get(scenario_name, {})
    return adj_map.get(style, 0.0)
