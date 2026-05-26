"""
Equibase PDF Chart Parser
===========================
Parses the text extracted from Equibase PDF result charts.

Input:  Full text of a day's chart PDF (multiple races concatenated)
Output: List of race dicts with:
        - track_code, race_num, race_date
        - distance_text, distance_yards
        - surface (Dirt/Turf/Synthetic)
        - track_condition (Fast/Good/Sloppy/etc.)
        - final_time_sec (winner's time in seconds)
        - fractional_times (list of floats in seconds)
        - weather, temp_f
        - purse, class_text, claiming_price
        - winner_num, winner_name

Phase 1 scope: race-level metadata + winner's time only.
Per-finisher times and margins come in Phase 3.
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("racing_agent")


# ── Distance conversion ─────────────────────────────────────────────
# Thoroughbreds: 1 furlong = 220 yards; 1 mile = 1760 yards
_DISTANCE_WORDS = {
    "furlong":  220, "furlongs":  220,
    "mile":    1760, "miles":    1760,
    "yard":       1, "yards":       1,
}

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "sixteenth": 0.0625,
    "half": 0.5, "quarter": 0.25, "three-quarters": 0.75,
    "third": 0.333,
}

def parse_distance_to_yards(text: str) -> Optional[int]:
    """
    Parse distance phrases like "Six Furlongs", "One Mile And Seventy Yards",
    "Five And One Half Furlongs" into total yards.
    Returns None if unparseable.
    """
    if not text:
        return None
    t = text.lower().strip()

    # Normalize fractions
    t = t.replace("one half", ".5").replace("and one half", ".5")
    t = t.replace("and one quarter", ".25").replace("and three quarters", ".75")
    t = t.replace("one-half", ".5").replace("three-quarters", ".75")

    total_yards = 0.0
    # Find number + unit pairs
    # Handle number words: "six furlongs", "one mile"
    for num_word, num_val in _NUM_WORDS.items():
        # match "six furlongs" — consume the match
        for unit_word, unit_yd in _DISTANCE_WORDS.items():
            pattern = rf"\b{num_word}\s*\.?\d*\s*{unit_word}\b"
            m = re.search(pattern, t)
            if m:
                # Extract optional fraction after number word
                frac_m = re.search(rf"{num_word}\s*(\.\d+)?\s*{unit_word}", t)
                frac = float(frac_m.group(1)) if frac_m and frac_m.group(1) else 0
                total_yards += (num_val + frac) * unit_yd
                t = t.replace(m.group(), "", 1)
                break

    # Handle digit-prefix patterns: "5 furlongs", "1 1/16 miles"
    digit_patterns = [
        # Mixed fraction: "1 1/16 miles"
        (r"(\d+)\s+(\d+)/(\d+)\s+(furlongs?|miles?|yards?)",
         lambda m: (int(m.group(1)) + int(m.group(2))/int(m.group(3))) * _DISTANCE_WORDS[m.group(4).rstrip("s") + ("s" if not m.group(4).endswith("s") else "")]),
        # Decimal or whole: "5.5 furlongs", "6 furlongs", "70 yards"
        (r"(\d+(?:\.\d+)?)\s+(furlongs?|miles?|yards?)",
         lambda m: float(m.group(1)) * _DISTANCE_WORDS[m.group(2) if m.group(2) in _DISTANCE_WORDS else m.group(2) + "s"]),
    ]
    for pat, fn in digit_patterns:
        for match in re.finditer(pat, t):
            try:
                total_yards += fn(match)
            except (KeyError, ValueError):
                pass

    return int(round(total_yards)) if total_yards > 0 else None


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """
    Parse time strings like "1:45.59", "48.02", "1:14.00" into seconds.
    Returns None if unparseable.
    """
    if not time_str:
        return None
    t = time_str.strip()
    try:
        if ":" in t:
            parts = t.split(":")
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            return float(t)
    except (ValueError, IndexError):
        return None


# ── Race chart parser ────────────────────────────────────────────────

# Regex patterns for race fields
RE_RACE_HEADER = re.compile(
    r"([A-Z][A-Z\s]+?)\s*-\s*(\w+\s+\d+,\s+\d{4})\s*-\s*Race\s+(\d+)",
    re.IGNORECASE
)
RE_DISTANCE = re.compile(
    r"Distance:\s*(.+?)(?:Current\s+Track\s+Record|\n|$)",
    re.IGNORECASE | re.DOTALL
)
RE_SURFACE_FROM_DIST = re.compile(
    r"On\s+The\s+(Dirt|Turf|Grass|Synthetic|All\s*Weather|Inner\s+Turf|Outer\s+Turf)",
    re.IGNORECASE
)
RE_TRACK_CONDITION = re.compile(
    r"Track:\s*(\w+(?:\s+\w+)?)",
    re.IGNORECASE
)
RE_WEATHER = re.compile(
    r"Weather:\s*(\w+(?:\s+\w+)?),?\s*(\d+)°?",
    re.IGNORECASE
)
RE_FINAL_TIME = re.compile(
    r"Final\s+Time:\s*(\d+:\d+\.\d+|\d+\.\d+)",
    re.IGNORECASE
)
RE_FRACTIONAL = re.compile(
    r"Fractional\s+Times?:\s*([\d\s:.]+?)(?:Split|Run-Up|Final|\n\s*\n|$)",
    re.IGNORECASE | re.DOTALL
)
RE_PURSE = re.compile(r"Purse:\s*\$?([\d,]+)", re.IGNORECASE)
RE_CLAIMING_PRICE = re.compile(r"Claiming\s+Price:\s*\$?([\d,]+)", re.IGNORECASE)
RE_RUN_UP = re.compile(r"Run-Up:\s*(\d+)\s*feet", re.IGNORECASE)
RE_CLASS = re.compile(
    r"^(MAIDEN|CLAIMING|ALLOWANCE|STAKES|HANDICAP|STARTER|OPTIONAL|MATCH)"
    r"([^\n]*)",
    re.IGNORECASE | re.MULTILINE
)


def split_into_races(full_text: str) -> List[str]:
    """
    Split a day's chart text into individual race chunks.
    Races are separated by headers like "PARX RACING - April 14, 2026 - Race 1".
    """
    # Find all race header positions
    positions = []
    for m in RE_RACE_HEADER.finditer(full_text):
        positions.append((m.start(), m.group(0)))

    if not positions:
        return []

    # Split into chunks between consecutive headers
    chunks = []
    for i, (start, header) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(full_text)
        chunks.append(full_text[start:end])

    return chunks


def parse_race_chunk(text: str, track_code: str, date_str: str) -> Optional[Dict]:
    """
    Parse a single race's chart text into a structured dict.
    Returns None if the chunk isn't parseable.
    """
    # Race number from header
    m = RE_RACE_HEADER.search(text)
    if not m:
        return None
    race_num = int(m.group(3))

    race = {
        "track_code": track_code,
        "race_date": date_str,
        "race_num": race_num,
        "distance_text": None,
        "distance_yards": None,
        "surface": None,
        "track_condition": None,
        "weather": None,
        "temp_f": None,
        "final_time_sec": None,
        "fractional_times_sec": [],
        "purse": None,
        "claiming_price": None,
        "run_up_feet": None,
        "class_type": None,
    }

    # Distance
    dm = RE_DISTANCE.search(text)
    if dm:
        dist_text = dm.group(1).strip().rstrip(".").rstrip()
        # Chop off anything after "On The X" for cleaner display
        race["distance_text"] = re.sub(r"\s+On\s+The.*$", "", dist_text, flags=re.IGNORECASE).strip()
        race["distance_yards"] = parse_distance_to_yards(race["distance_text"])
        sm = RE_SURFACE_FROM_DIST.search(dist_text)
        if sm:
            surf = sm.group(1).title().replace("  ", " ")
            # Normalize
            if "turf" in surf.lower() or "grass" in surf.lower():
                race["surface"] = "Turf"
            elif "synthetic" in surf.lower() or "all weather" in surf.lower():
                race["surface"] = "Synthetic"
            else:
                race["surface"] = "Dirt"

    # Track condition
    tm = RE_TRACK_CONDITION.search(text)
    if tm:
        race["track_condition"] = tm.group(1).strip()

    # Weather + temp
    wm = RE_WEATHER.search(text)
    if wm:
        race["weather"] = wm.group(1).strip()
        try:
            race["temp_f"] = int(wm.group(2))
        except ValueError:
            pass

    # Final time
    ftm = RE_FINAL_TIME.search(text)
    if ftm:
        race["final_time_sec"] = parse_time_to_seconds(ftm.group(1))

    # Fractional times
    fm = RE_FRACTIONAL.search(text)
    if fm:
        raw = fm.group(1).strip()
        # Times are space-separated: "23.94 48.02 1:14.00 1:41.26"
        for tok in raw.split():
            sec = parse_time_to_seconds(tok)
            if sec is not None:
                race["fractional_times_sec"].append(sec)

    # Purse
    pm = RE_PURSE.search(text)
    if pm:
        try:
            race["purse"] = int(pm.group(1).replace(",", ""))
        except ValueError:
            pass

    # Claiming price
    cm = RE_CLAIMING_PRICE.search(text)
    if cm:
        try:
            race["claiming_price"] = int(cm.group(1).replace(",", ""))
        except ValueError:
            pass

    # Run-up
    rm = RE_RUN_UP.search(text)
    if rm:
        try:
            race["run_up_feet"] = int(rm.group(1))
        except ValueError:
            pass

    # Class type (MAIDEN/CLAIMING/etc.) — look near top of chunk
    class_match = RE_CLASS.search(text[:1000])
    if class_match:
        race["class_type"] = class_match.group(1).upper()

    return race


def parse_chart_text(full_text: str, track_code: str, date_str: str) -> List[Dict]:
    """
    Parse a full day's chart text into a list of race dicts.
    """
    chunks = split_into_races(full_text)
    races = []
    for chunk in chunks:
        parsed = parse_race_chunk(chunk, track_code, date_str)
        if parsed and parsed.get("final_time_sec"):
            races.append(parsed)
        elif parsed:
            logger.debug(f"Race {parsed.get('race_num')} parsed but missing time")
    return races


if __name__ == "__main__":
    # Test with the cached PRX chart
    import sys
    from pathlib import Path
    try:
        from chart_fetcher import get_chart_text
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from chart_fetcher import get_chart_text

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    text = get_chart_text("PRX", "20260414")
    if not text:
        print("No chart text")
        sys.exit(1)
    print(f"Text length: {len(text)}")
    races = parse_chart_text(text, "PRX", "20260414")
    print(f"Parsed {len(races)} races\n")
    for r in races:
        print(f"Race {r['race_num']:>2}: "
              f"{r['distance_text']:<35} "
              f"({r['distance_yards']:>4}y) "
              f"{str(r['surface'] or '?'):<6} "
              f"{str(r['track_condition'] or '?'):<6} "
              f"Time: {r['final_time_sec']:>6.2f}s "
              f"Fracs: {r['fractional_times_sec']}")
