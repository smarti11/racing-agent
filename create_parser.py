#!/usr/bin/env python3
"""Run this script from ~/Documents/racing-agent to create data/chart_parser.py"""

code = r'''import re, logging, sys
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger("racing_agent")

def parse_time_to_seconds(time_str):
    if not time_str:
        return None
    t = time_str.strip()
    try:
        if ":" in t:
            parts = t.split(":")
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(t)
    except (ValueError, IndexError):
        return None

def parse_distance_to_yards(text):
    if not text:
        return None
    t = text.lower().strip()
    total = 0.0
    num_words = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
                 "seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12}
    t = t.replace("one half",".5").replace("and one half",".5").replace("one-half",".5")
    t = t.replace("and one quarter",".25").replace("one quarter",".25")
    t = t.replace("three quarters",".75").replace("three-quarters",".75")
    t = t.replace("and a half",".5")
    for nw, nv in num_words.items():
        for unit, uy in [("furlongs",220),("furlong",220),("miles",1760),("mile",1760),("yards",1),("yard",1)]:
            m = re.search(rf"\b{nw}\s*(\.\d+)?\s*{unit}\b", t)
            if m:
                frac = float(m.group(1)) if m.group(1) else 0
                total += (nv + frac) * uy
                t = t.replace(m.group(), "", 1)
                break
    for m2 in re.finditer(r"(\d+)\s+(\d+)/(\d+)\s+(furlongs?|miles?|yards?)", t):
        uv = {"furlong":220,"furlongs":220,"mile":1760,"miles":1760,"yard":1,"yards":1}
        total += (int(m2.group(1)) + int(m2.group(2))/int(m2.group(3))) * uv.get(m2.group(4),1)
    for m3 in re.finditer(r"(\d+(?:\.\d+)?)\s+(furlongs?|miles?|yards?)", t):
        uv = {"furlong":220,"furlongs":220,"mile":1760,"miles":1760,"yard":1,"yards":1}
        total += float(m3.group(1)) * uv.get(m3.group(2),1)
    return int(round(total)) if total > 0 else None

RE_RACE_HEADER = re.compile(r"([A-Z][A-Z\s]+?)\s*-\s*(\w+\s+\d+,\s+\d{4})\s*-\s*Race\s+(\d+)", re.IGNORECASE)
RE_DISTANCE = re.compile(r"Distance:\s*(.+?)(?:Current\s+Track\s+Record|\n|$)", re.IGNORECASE | re.DOTALL)
RE_SURFACE = re.compile(r"On\s+The\s+(Dirt|Turf|Grass|Synthetic|All\s*Weather|Inner\s+Turf)", re.IGNORECASE)
RE_CONDITION = re.compile(r"Track:\s*(\w+(?:\s+\w+)?)", re.IGNORECASE)
RE_WEATHER = re.compile(r"Weather:\s*(\w+(?:\s+\w+)?),?\s*(\d+)", re.IGNORECASE)
RE_FINAL_TIME = re.compile(r"Final\s+Time:\s*(\d+:\d+\.\d+|\d+\.\d+)", re.IGNORECASE)
RE_FRACTIONAL = re.compile(r"Fractional\s+Times?:\s*([\d\s:.]+?)(?:Split|Run-Up|Final|\n\s*\n|$)", re.IGNORECASE | re.DOTALL)
RE_PURSE = re.compile(r"Purse:\s*\$?([\d,]+)", re.IGNORECASE)
RE_CLAIMING = re.compile(r"Claiming\s+Price:\s*\$?([\d,]+)", re.IGNORECASE)
RE_RUN_UP = re.compile(r"Run-Up:\s*(\d+)\s*feet", re.IGNORECASE)
RE_CLASS = re.compile(r"^(MAIDEN|CLAIMING|ALLOWANCE|STAKES|HANDICAP|STARTER|OPTIONAL|MATCH)", re.IGNORECASE | re.MULTILINE)

def split_into_races(full_text):
    positions = [(m.start(), m.group(0)) for m in RE_RACE_HEADER.finditer(full_text)]
    if not positions:
        return []
    chunks = []
    for i, (start, header) in enumerate(positions):
        end = positions[i+1][0] if i+1 < len(positions) else len(full_text)
        chunks.append(full_text[start:end])
    return chunks

def parse_race_chunk(text, track_code, date_str):
    m = RE_RACE_HEADER.search(text)
    if not m:
        return None
    race = {
        "track_code": track_code, "race_date": date_str, "race_num": int(m.group(3)),
        "distance_text": None, "distance_yards": None, "surface": None,
        "track_condition": None, "weather": None, "temp_f": None,
        "final_time_sec": None, "fractional_times_sec": [],
        "purse": None, "claiming_price": None, "run_up_feet": None, "class_type": None,
    }
    dm = RE_DISTANCE.search(text)
    if dm:
        dt = dm.group(1).strip()
        race["distance_text"] = re.sub(r"\s+On\s+The.*$", "", dt, flags=re.IGNORECASE).strip()
        race["distance_yards"] = parse_distance_to_yards(race["distance_text"])
        sm = RE_SURFACE.search(dt)
        if sm:
            s = sm.group(1).lower()
            if "turf" in s or "grass" in s:
                race["surface"] = "Turf"
            elif "synthetic" in s or "weather" in s:
                race["surface"] = "Synthetic"
            else:
                race["surface"] = "Dirt"
    tm = RE_CONDITION.search(text)
    if tm:
        race["track_condition"] = tm.group(1).strip()
    wm = RE_WEATHER.search(text)
    if wm:
        race["weather"] = wm.group(1).strip()
        try:
            race["temp_f"] = int(wm.group(2))
        except ValueError:
            pass
    ftm = RE_FINAL_TIME.search(text)
    if ftm:
        race["final_time_sec"] = parse_time_to_seconds(ftm.group(1))
    fm = RE_FRACTIONAL.search(text)
    if fm:
        for tok in fm.group(1).strip().split():
            sec = parse_time_to_seconds(tok)
            if sec is not None:
                race["fractional_times_sec"].append(sec)
    pm = RE_PURSE.search(text)
    if pm:
        try:
            race["purse"] = int(pm.group(1).replace(",",""))
        except ValueError:
            pass
    cm = RE_CLAIMING.search(text)
    if cm:
        try:
            race["claiming_price"] = int(cm.group(1).replace(",",""))
        except ValueError:
            pass
    rm = RE_RUN_UP.search(text)
    if rm:
        try:
            race["run_up_feet"] = int(rm.group(1))
        except ValueError:
            pass
    cl = RE_CLASS.search(text[:1000])
    if cl:
        race["class_type"] = cl.group(1).upper()
    return race

def parse_chart_text(full_text, track_code, date_str):
    chunks = split_into_races(full_text)
    races = []
    for chunk in chunks:
        parsed = parse_race_chunk(chunk, track_code, date_str)
        if parsed and parsed.get("final_time_sec"):
            races.append(parsed)
    return races

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).parent))
    from chart_fetcher import get_chart_text
    text = get_chart_text("PRX", "20260414")
    if not text:
        print("No chart text")
        sys.exit(1)
    print("Text length: %d" % len(text))
    races = parse_chart_text(text, "PRX", "20260414")
    print("Parsed %d races\n" % len(races))
    for r in races:
        dist = r["distance_text"] or "?"
        yards = r["distance_yards"] or 0
        surf = r["surface"] or "?"
        cond = r["track_condition"] or "?"
        ts = r["final_time_sec"] or 0
        fracs = r["fractional_times_sec"]
        print("  R%2d: %-35s (%4dy) %-6s %-6s Time: %7.2fs Fracs: %s" % (r["race_num"], dist, yards, surf, cond, ts, fracs))
'''

with open("data/chart_parser.py", "w") as f:
    f.write(code)
print("data/chart_parser.py created successfully")
