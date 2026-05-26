#!/usr/bin/env python3
"""
chart_parser.py — DRF Chart Parser for racing-agent

Fetches DRF chart PDFs, extracts structured data (results, fractions, trip notes,
payouts), and writes to racing.db. Designed for incremental use: re-running on
the same track/date upserts cleanly.

USAGE
-----
# Parse a single track-date and write to DB
python3 chart_parser.py --track LRL --date 20260516

# Parse from a local PDF (testing/backfill)
python3 chart_parser.py --pdf /path/to/chart.pdf --track LRL --date 20260516

# Dry-run (parse only, no DB write)
python3 chart_parser.py --track LRL --date 20260516 --dry-run

# Re-fetch even if today's chart was already parsed
python3 chart_parser.py --track LRL --date 20260516 --force

DEPENDENCIES
------------
- requests
- poppler-utils (provides pdftotext) — install via brew: `brew install poppler`
- sqlite3 (stdlib)

DATA FLOW
---------
1. fetch_chart_pdf(track, date) → downloads PDF to ~/Documents/racing-agent/data/charts/
2. extract_text(pdf_path) → runs pdftotext -layout → string
3. split_into_races(text) → list of per-race text blocks
4. parse_race(text_block) → dict with all extracted fields
5. tag_trips(race_dict) → adds running_style + trouble tags
6. write_to_db(race_dict) → upserts into chart_* tables
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================================
# CONFIG
# ============================================================================

AGENT_ROOT = Path.home() / "Documents" / "racing-agent"
DB_PATH = AGENT_ROOT / "db" / "racing.db"
CHART_CACHE = AGENT_ROOT / "data" / "charts"
SCHEMA_PATH = Path(__file__).parent / "chart_schema.sql"

DRF_URL_TEMPLATE = (
    "https://www1.drf.com/drfPDFChartRacesIndexAction.do"
    "?TRK={track}&CTY=USA&DATE={date}&RN=99"
)

# Word-number → integer for race numbers
RACE_NUM_WORDS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
    "ELEVENTH": 11, "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14,
    "FIFTEENTH": 15, "SIXTEENTH": 16,
}

# Trip-note keyword library — used for trouble scoring & running-style tags
TROUBLE_KEYWORDS = {
    "MAJOR": [
        r"\bstumbled\b", r"\bfell\b", r"\bunseated\b",
        # "eased" alone = pulled up. But "eased out/back/into/to" = routine
        # positional maneuver. Use negative lookahead.
        r"\beased(?!\s+(?:out|back|to|off|into|in|forward|up\s+to))\b",
        r"\bpulled up\b", r"\blugged in\b", r"\blugged out\b",
        r"\bvanned off\b", r"\bclipped heels\b", r"\bbroke down\b",
        r"\bsteadied sharply\b", r"\bchecked sharply\b",
    ],
    "MINOR": [
        r"\bbumped\b", r"\bsteadied\b", r"\bjostled\b", r"\brank\b",
        r"\bbore out\b", r"\bbore in\b", r"\bpinched\b", r"\bchecked\b",
        r"\baltered (?:in|out)\b", r"\bsqueezed\b", r"\bbobbled\b",
        r"\bbroke (?:in|out)ward\b", r"\bbroke a step slow\b",
        # "drifted" alone usually means horse got off course - mild trouble
        r"\bdrifted(?!\s+(?:back))\b",
        # "floated" usually means lane shift, often wide
        r"\bfloated\b",
        r"\bcame in\b",
    ],
}

WIDE_KEYWORDS = [
    (r"\bthree wide\b|\b3 wide\b", "3w"),
    (r"\bfour wide\b|\b4 wide\b", "4w"),
    (r"\bfive wide\b|\b5 wide\b", "5w"),
    (r"\bsix wide\b|\b6 wide\b", "6w"),
    (r"\bseven wide\b|\b7 wide\b", "7w"),
    (r"\bvery wide\b", "very_wide"),
    (r"\bwidest\b", "widest"),
]

RUNNING_STYLE_KEYWORDS = {
    "E": [r"\bset the (?:pace|early)\b", r"\bon the lead\b",
          r"\bsped to\b", r"\bassumed the early lead\b",
          r"\btook command\b", r"\bmade the early lead\b",
          r"\bbroke (?:sharply|on top)\b"],
    "P": [r"\bdueled\b", r"\bpressed\b", r"\bvied\b", r"\bdisputed the pace\b",
          r"\bprompted the pace\b", r"\bforwardly placed\b",
          r"\btracked the (?:pace|leader|leaders)\b"],
    "S": [r"\bstalked\b", r"\bmid pack\b", r"\bin range\b",
          r"\boff the (?:pace|leaders)\b", r"\bchased\b",
          r"\bwithin range\b", r"\brated (?:back|kindly|off)\b"],
    "C": [r"\bfar back\b", r"\blast\b", r"\btrailed\b", r"\blagged\b",
          r"\bdropped back\b", r"\bwell back\b", r"\bvoid of speed\b",
          r"\bbehind horses\b"],
}


# ============================================================================
# FETCHING
# ============================================================================

def fetch_chart_pdf(track: str, date: str, force: bool = False) -> Path:
    """Download chart PDF from DRF. Cache locally to avoid re-fetching.

    Args:
        track: 3-letter track code (e.g. "LRL", "GP", "CD")
        date: YYYYMMDD format
        force: if True, re-download even if cached

    Returns:
        Path to local PDF file.
    """
    CHART_CACHE.mkdir(parents=True, exist_ok=True)
    pdf_path = CHART_CACHE / f"{track}_{date}.pdf"

    if pdf_path.exists() and not force:
        print(f"[CACHE] Using cached chart: {pdf_path}")
        return pdf_path

    url = DRF_URL_TEMPLATE.format(track=track, date=date)
    print(f"[FETCH] Downloading {url}")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (racing-agent/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    if len(data) < 1000:
        raise RuntimeError(f"Chart fetch returned suspiciously small body ({len(data)} bytes)")

    pdf_path.write_bytes(data)
    print(f"[FETCH] Saved {len(data):,} bytes to {pdf_path}")
    return pdf_path


# ============================================================================
# TEXT EXTRACTION
# ============================================================================

def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext -layout (poppler-utils)."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "pdftotext not found. Install with: brew install poppler"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pdftotext failed: {e.stderr}")


# ============================================================================
# RACE SPLITTING
# ============================================================================

# Match "FIRST RACE", "SECOND RACE", etc. as section delimiters
RACE_HEADER_RE = re.compile(
    r"\b(" + "|".join(RACE_NUM_WORDS.keys()) + r")\s+RACE\b"
)


def split_into_races(text: str) -> list[tuple[int, str]]:
    """Split full chart text into per-race text blocks.

    DRF charts are one race per PDF page, so we split on form-feed (\\f) markers
    rather than on "NTH RACE" text labels. The label-based approach fails because
    pdftotext -layout linearizes columns top-to-bottom, and the race conditions
    block appears BEFORE the "NTH RACE" label in linear order.

    Returns:
        List of (race_num, race_text) tuples, sorted by race_num.
    """
    pages = text.split("\f")
    races: list[tuple[int, str]] = []
    for page in pages:
        m = RACE_HEADER_RE.search(page)
        if not m:
            continue
        race_num = RACE_NUM_WORDS[m.group(1)]
        races.append((race_num, page))
    return sorted(races, key=lambda x: x[0])


# ============================================================================
# RACE PARSING
# ============================================================================

# Race header: distance, surface, race type, conditions.
# Distance can include unicode fraction markers (ô=½, Â=1/16, ±=3/16, °=1/8, etc.)
# We allow any non-space non-period chars between the number and the unit word.
HEADER_DISTANCE_RE = re.compile(
    r"(\d+\s*[^\s.]*\s*(?:FURLONGS?|MILES?|YARDS))",
    re.IGNORECASE,
)
HEADER_SURFACE_RE = re.compile(r"\(\s*(Turf|Dirt|All Weather|AW)\s*\)", re.IGNORECASE)
HEADER_PURSE_RE = re.compile(r"Purse\s+\$([0-9,]+)")
HEADER_WEATHER_RE = re.compile(r"\(\s*(Clear|Cloudy|Overcast|Rain|Showers|Foggy|Sunny)\.\s*(\d+)\s*\.?\s*\)")
HEADER_RACE_TYPE_RE = re.compile(
    r"(MAIDEN SPECIAL WEIGHT|MAIDEN CLAIMING|ALLOWANCE OPTIONAL CLAIMING|"
    r"ALLOWANCE|CLAIMING|STARTER ALLOWANCE|STARTER OPTIONAL CLAIMING|"
    r"HANDICAP|STAKES?)",
    re.IGNORECASE,
)
HEADER_NAMED_STAKES_RE = re.compile(r"([A-Z][A-Z\s\.\-']+(?:S\.|STAKES))\s+(?:SPONSORED|Purse|Grade)")

# Track condition + start note
OFF_TIME_RE = re.compile(r"OFF AT\s+(\d{1,2}:\d{2})")
START_NOTE_RE = re.compile(r"(Won (?:driving|easily|ridden out|in hand|handily))\.\s*"
                            r"(?:Track|Course)\s+(\w+)\.")

# Fractional times — the parenthesized decimal form is the cleanest
FRACTIONS_RE = re.compile(r"TIME\s+[^()]*\(\s*([^)]+)\s*\)")
FRAC_NUM_RE = re.compile(r":?(\d+(?:\.\d+)?)")

# Result line — multi-stage parsing because columns vary
RESULT_LINE_RE = re.compile(
    r"^\s*"
    r"(?:(\S+\s+\S+)\s+)?"          # 1: Last raced (optional - first-time starters)
    r"([A-Za-z][A-Za-z0-9\s'.\-()]*?)\s+"   # 2: Horse name
    r"((?:L\s+)?[bfh\s]*)\s+"               # 3: M/Eqt (lasix + blinkers/etc)
    r"(\d+)\s+"                              # 4: Age
    r"(\d+)\s+"                              # 5: Weight
    r"(\d+)\s+"                              # 6: PP
    r"(\d+)\s+"                              # 7: Start
    r"(.*?)\s+"                              # 8: Position calls (greedy)
    r"([A-Z][a-zA-Z'\-\s.]+?\s+[A-Z](?:\s+[A-Z](?:r|rJr|r III)?)?)\s*"  # 9: Jockey
    r"(?:(\d{4,6})\s+)?"                     # 10: Claim price (optional)
    r"(\d+\.\d+)\s*$",                       # 11: Odds
)

# Simpler approach: split by whitespace and identify columns positionally
# Result line ends with: ... [jockey words] [optional claim price] [odds]

# Mutuel prices
WPS_RE = re.compile(
    r"(\d+)\s*-\s*([A-Z][A-Z\s'.\-()]+?)\s+"
    r"(\d+\.\d{2})?\s*(\d+\.\d{2})?\s*(\d+\.\d{2})?\s*$",
    re.MULTILINE,
)

# Exotic payouts
EXOTIC_RE = re.compile(
    r"\$(\d+(?:\.\d+)?)\s+(EXACTA|TRIFECTA|SUPERFECTA|SUPER HIGH FIVE)\s+"
    r"([\d\-/, ]+?)\s+PAID\s+\$([0-9,]+\.\d{2})",
    re.IGNORECASE,
)

# Multi-race exotics (Pick 3/4/5, Daily Double). Capture base amount in group 1.
PICK_RE = re.compile(
    r"(50\s*CENT|\$0?\.50|\$1|\$2)\s+"
    r"(Pick\s+(?:Three|Four|Five|Six)|Daily\s+Double)\s*"
    r"\(([\d\-/, ]+)\)\s+Paid\s+\$([0-9,]+\.\d{2})"
    r"(?:.*?Pool\s+\$([0-9,]+))?",
    re.IGNORECASE | re.DOTALL,
)

# Scratched horses
SCRATCHED_RE = re.compile(
    r"Scratched-\s+(.+?)(?=\n\s*\n|\n\s*\$|\n\s*50|\Z)",
    re.DOTALL,
)


def parse_race(race_num: int, text: str, track_code: str, race_date: str) -> dict[str, Any]:
    """Parse a single race text block into structured data."""
    race: dict[str, Any] = {
        "race_num": race_num,
        "track_code": track_code,
        "race_date": race_date,
        "horses": [],
        "fractions": {},
        "payouts": [],
        "trips": [],
        "scratches": [],
    }

    # --- Header parsing ---
    distance_match = HEADER_DISTANCE_RE.search(text)
    race["distance_raw"] = distance_match.group(1).strip() if distance_match else None

    surface_match = HEADER_SURFACE_RE.search(text)
    race["surface"] = surface_match.group(1).title() if surface_match else "Dirt"

    purse_match = HEADER_PURSE_RE.search(text)
    race["purse"] = int(purse_match.group(1).replace(",", "")) if purse_match else None

    weather_match = HEADER_WEATHER_RE.search(text)
    race["weather"] = f"{weather_match.group(1)}. {weather_match.group(2)}" if weather_match else None

    # Try named stakes first, then generic race type
    stakes_match = HEADER_NAMED_STAKES_RE.search(text)
    if stakes_match:
        race["race_type"] = stakes_match.group(1).strip()
    else:
        rt_match = HEADER_RACE_TYPE_RE.search(text)
        race["race_type"] = rt_match.group(1).upper() if rt_match else None

    # Conditions: first paragraph after distance until "Value of Race"
    val_idx = text.find("Value of Race")
    if val_idx > 0:
        header_block = text[:val_idx]
        # Strip race header words and track/date
        cleaned = re.sub(r"\b(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH)\s+RACE\b", "", header_block)
        cleaned = re.sub(r"MAY \d+\s*,\s*\d{4}", "", cleaned)  # date
        race["conditions_raw"] = " ".join(cleaned.split())

    # Off time + track condition + start note
    off_match = OFF_TIME_RE.search(text)
    race["off_time"] = off_match.group(1) if off_match else None

    sn_match = START_NOTE_RE.search(text)
    if sn_match:
        race["start_note"] = sn_match.group(1)
        race["track_condition"] = sn_match.group(2).lower()

    # --- Result table ---
    race["horses"] = parse_result_table(text, race["distance_raw"] or "")

    # Mark winner
    if race["horses"]:
        # Winner has finish_position = 1
        for h in race["horses"]:
            if h.get("finish_position") == 1:
                h["is_winner"] = 1

    # --- Fractions ---
    race["fractions"] = parse_fractions(text)

    # --- Win/Place/Show payouts (parse from $2 Mutuel Prices block) ---
    race["payouts"].extend(parse_wps_payouts(text))

    # --- Exotic payouts ---
    race["payouts"].extend(parse_exotic_payouts(text))

    # --- Multi-race exotics (Pick 3/4/5, DD) ---
    race["payouts"].extend(parse_pick_payouts(text))

    # --- Trip notes ---
    race["trips"] = parse_trips(text, [h["horse_name"] for h in race["horses"]])

    # --- Scratches ---
    race["scratches"] = parse_scratches(text)

    return race


def parse_result_table(text: str, distance_raw: str) -> list[dict[str, Any]]:
    """Parse the result table rows. Each horse is one line between header and OFF AT.

    Strategy: positional column parsing is unreliable due to variable spacing.
    Instead: tokenize each line and identify fields by structure:
      - First token(s) = last_raced ref (may be missing for first-timers)
      - Then horse name (letters, possibly multi-word, until M/Eqt)
      - M/Eqt = optional "L" + optional "b/bf/f" lookup
      - Then numeric fields: age, weight, PP, start, [position calls...]
      - Then jockey name (capitalized words)
      - Optional claim price (4-6 digit number)
      - Final field = odds (decimal)
    """
    # Find table boundaries
    header_match = re.search(r"^.*Last Raced\s+Horse.*?Odds.*?$", text, re.MULTILINE)
    if not header_match:
        return []
    table_start = header_match.end()
    off_match = re.search(r"OFF AT", text)
    table_end = off_match.start() if off_match else len(text)
    table_text = text[table_start:table_end]

    horses: list[dict[str, Any]] = []
    finish_pos = 0
    for line in table_text.split("\n"):
        line = line.rstrip()
        if not line.strip():
            continue
        if "Mutuel Pool" in line or "Pool $" in line:
            continue
        # Skip entries-only rows (race hasn't been run yet).
        # DRF shows these as "* * * * * >" or "0.00" odds with no real position calls.
        if re.search(r"\*\s*\*\s*\*", line):
            continue
        parsed = parse_result_row(line)
        if parsed:
            # Additional guard: real results have odds > 0 (0.00 = placeholder)
            if parsed.get("odds", 0) == 0.0:
                continue
            finish_pos += 1
            parsed["finish_position"] = finish_pos
            horses.append(parsed)
    return horses


# Token-level row parser
RESULT_ROW_TRAILING_RE = re.compile(
    r"^(.*?)\s+"                                   # everything before jockey
    r"([A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']*)*(?:\s+[A-Z](?:r|r Jr|rJr|r III|r II)?)?)\s+"  # jockey
    r"(?:(\d{4,6})\s+)?"                          # optional claim price
    r"(\d+\.\d+)\s*$"                              # odds
)


def parse_result_row(line: str) -> dict[str, Any] | None:
    """Parse one horse row from the result table.

    Robust strategy: work backwards from the end (odds, claim, jockey are
    last fields). Then parse forward from start (last_raced, horse name).
    """
    line = line.strip()
    if not line:
        return None

    # The line MUST end with odds (decimal). If not, it's not a result row.
    odds_match = re.search(r"(\d+\.\d{2})\s*$", line)
    if not odds_match:
        return None
    odds = float(odds_match.group(1))
    rest = line[: odds_match.start()].rstrip()

    # Optional claim price (4-6 digit integer at end)
    claim_match = re.search(r"\b(\d{4,6})\s*$", rest)
    claim_price = None
    if claim_match:
        # Verify it's plausibly a claim price (not a horse-name fragment)
        # Claim prices in racing are typically 4000–500000
        cp_val = int(claim_match.group(1))
        if 1000 <= cp_val <= 1_000_000:
            claim_price = cp_val
            rest = rest[: claim_match.start()].rstrip()

    # Jockey: trailing capitalized words/initials. Walk back from end.
    # Pattern: surname [first initial] [middle initial/suffix]
    # Examples: "Hazlewood Yª", "Ortiz J L", "Vargas J Eª", "Briceno J G",
    #           "Mena R E", "Boyce F", "Velazquez J R", "Ortiz I Jr"
    jockey_match = re.search(
        r"([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]*)*"
        r"(?:\s+(?:[A-Z](?:r)?|Jr|III|II|IV|JrJr))*"
        r"(?:\s+[A-Za-z0-9¦§¨©ª«¬­®¯]+)?)\s*$",
        rest,
    )
    if not jockey_match:
        return None
    jockey = jockey_match.group(1).strip()
    # Strip ONLY the trailing unicode apprentice/bug marks (ª, ¬, etc.),
    # preserving the preceding initial. "Vargas J Eª" → "Vargas J E"
    jockey = re.sub(r"[¦§¨©ª«¬­®¯ô°¬±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ]+\s*$", "", jockey).strip()
    rest_pre_jockey = rest[: jockey_match.start()].rstrip()

    # Now we have: [LastRaced?] Horse M/Eqt Age Wt PP St [calls]
    # Tokenize and walk forward.
    tokens = rest_pre_jockey.split()
    if len(tokens) < 5:
        return None

    # Find M/Eqt position: it's "L" + optional "b"/"bf"/"f"/"h" tokens,
    # followed immediately by Age (single digit usually 2-12) and Weight (3-digit 100-130).
    # OR no L (no lasix) — then just "b" / "bf" / "f" alone, OR nothing (then age/wt directly).
    meq_idx = None
    age = None
    weight = None
    pp = None
    start = None
    for i, tok in enumerate(tokens):
        # Look for age + weight: two consecutive numeric tokens where
        # second is 100-130 (lbs)
        if tok.isdigit() and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            a = int(tok)
            w = int(tokens[i + 1])
            if 2 <= a <= 14 and 100 <= w <= 140:
                meq_idx = i
                age = a
                weight = w
                # PP and Start are the next two integer tokens
                if i + 2 < len(tokens) and tokens[i + 2].isdigit():
                    pp = int(tokens[i + 2])
                if i + 3 < len(tokens) and tokens[i + 3].isdigit():
                    start = int(tokens[i + 3])
                break

    if meq_idx is None:
        return None

    # Equipment: tokens between horse name and age
    # last_raced: tokens before equipment IF the first token looks like a date ref
    # (contains digits + unicode chars + 3-letter track code) OR is empty
    eq_tokens: list[str] = []
    horse_tokens: list[str] = []
    last_raced_tokens: list[str] = []

    # last_raced refs look like "12ß26" + "¬Lrl§" — 2 tokens where:
    #   - token[0]: starts with digit (1-2 digit day), contains unicode mo/yr codes
    #   - token[1]: contains 2-4 letter track abbreviation (e.g. Lrl, GP, MVR, OP)
    #     wrapped in unicode prefix/suffix chars (race number markers)
    if len(tokens) >= 2 and tokens[0] and tokens[0][0].isdigit() and len(tokens[0]) <= 7:
        # tokens[1] must contain 2-4 consecutive uppercase letters (track code)
        if re.search(r"[A-Z][a-zA-Z]{1,3}", tokens[1]):
            last_raced_tokens = tokens[:2]
            start_idx = 2
        else:
            start_idx = 0
    else:
        start_idx = 0

    # Equipment tokens are right before age (meq_idx). They're "L" + b/bf/f flags
    # Walk back from meq_idx-1 until we hit a non-equipment token
    eq_start = meq_idx
    for i in range(meq_idx - 1, start_idx - 1, -1):
        t = tokens[i]
        if t in {"L", "b", "bf", "f", "h", "bh", "fh", "L*", "*L"}:
            eq_start = i
        else:
            break

    equipment = " ".join(tokens[eq_start:meq_idx])
    horse_tokens = tokens[start_idx:eq_start]
    horse_name = " ".join(horse_tokens).strip()

    if not horse_name:
        return None

    # Position calls: tokens after start (meq_idx+3) up to end of token list
    # (jockey already split off). For sprint races: 4 calls; routes: 5 calls.
    calls_start = meq_idx + 4 if start is not None else meq_idx + 3
    calls_tokens = tokens[calls_start:] if calls_start < len(tokens) else []
    calls_raw = " ".join(calls_tokens)

    # Finish margin: last call token
    finish_margin_raw = calls_tokens[-1] if calls_tokens else None

    return {
        "last_raced_raw": " ".join(last_raced_tokens) if last_raced_tokens else None,
        "horse_name": clean_horse_name(horse_name),
        "equipment": equipment,
        "age": age,
        "weight": weight,
        "post_position": pp,
        "start_position": start,
        "calls_raw": calls_raw,
        "finish_margin_raw": finish_margin_raw,
        "jockey": jockey.strip(),
        "claim_price": claim_price,
        "odds": odds,
        "program_num": str(pp) if pp is not None else None,
        # finish_position assigned by caller
    }


def clean_horse_name(name: str) -> str:
    """Strip trailing garbage and normalize spacing."""
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing "L" if it slipped through
    name = re.sub(r"\s+L\s*$", "", name)
    return name


def parse_fractions(text: str) -> dict[str, Any]:
    """Extract decimal fractions from the TIME line.

    Example: "TIME :22, :44¨, :56, 1:01© ( :22.12, :44.62, :56.00, 1:01.90 )"
    """
    m = FRACTIONS_RE.search(text)
    if not m:
        return {}
    raw = m.group(1).strip()
    # Find all decimal numbers (including those after a colon for minutes)
    nums: list[float] = []
    for piece in re.split(r"[,\s]+", raw):
        piece = piece.strip(": ")
        if not piece:
            continue
        # Handle "1:01.90" → 61.90
        if ":" in piece:
            mm, ss = piece.split(":")
            try:
                nums.append(int(mm) * 60 + float(ss))
            except ValueError:
                continue
        else:
            try:
                nums.append(float(piece))
            except ValueError:
                continue

    if not nums:
        return {"raw_text": raw}

    result: dict[str, Any] = {"raw_text": raw, "final_time": nums[-1]}
    for i, n in enumerate(nums, 1):
        if i <= 5:
            result[f"frac_{i}"] = n
    return result


def parse_wps_payouts(text: str) -> list[dict[str, Any]]:
    """Parse $2 Mutuel Prices block for Win/Place/Show.

    Note: due to PDF layout, the winner's price row may appear BEFORE the
    "$2 Mutuel Prices:" label in the linearized text. We capture from end of
    TIME line through to first exotic ($1 EXACTA / $2 EXACTA / $1 DAILY DOUBLE).
    """
    payouts: list[dict[str, Any]] = []
    # Find the WPS block: starts after TIME line, ends at first exotic
    time_match = re.search(r"TIME\s+[^\n]*\(\s*[^)]+\s*\)\s*\n", text)
    if not time_match:
        return payouts
    block_start = time_match.end()
    # End at first exotic header (EXACTA / TRIFECTA / SUPERFECTA / Pedigree)
    end_patterns = [
        r"\$\d+\s+EXACTA", r"\$\d+\s+TRIFECTA", r"\$\d+\s+SUPERFECTA",
        r"\$\d+\s+SUPER HIGH FIVE",
        r"^\s*(?:Ch|B|Dk|Gr|Ro|Bay)\.\s+",  # pedigree line
    ]
    end_pos = len(text)
    for pat in end_patterns:
        m = re.search(pat, text[block_start:], re.MULTILINE)
        if m and block_start + m.start() < end_pos:
            end_pos = block_start + m.start()
    block = text[block_start:end_pos]

    # Each price line: "  N -HORSE NAME    WIN  PLACE  SHOW"
    for line in block.split("\n"):
        line = line.strip()
        if not line or "Mutuel Prices" in line:
            # Strip the label out and keep parsing the rest of the line
            line = re.sub(r"\$\d+\s+Mutuel Prices:?", "", line).strip()
            if not line:
                continue
        m2 = re.match(
            r"(\d+)\s*-\s*([A-Z][A-Z0-9'.\-\s()]+?)\s{2,}"
            r"([\d.]+)?\s*([\d.]+)?\s*([\d.]+)?\s*$",
            line,
        )
        if not m2:
            continue
        pn = m2.group(1)
        prices = [p for p in [m2.group(3), m2.group(4), m2.group(5)] if p]
        if len(prices) == 3:
            labels = ["WIN", "PLACE", "SHOW"]
        elif len(prices) == 2:
            labels = ["PLACE", "SHOW"]
        elif len(prices) == 1:
            labels = ["SHOW"]
        else:
            continue
        for label, price in zip(labels, prices):
            try:
                payouts.append({
                    "bet_type": label,
                    "program_nums": pn,
                    "base_amount": 2.00,
                    "payout": float(price),
                    "pool_size": None,
                })
            except ValueError:
                pass
    return payouts


def parse_exotic_payouts(text: str) -> list[dict[str, Any]]:
    """Parse exacta/trifecta/superfecta payouts."""
    payouts: list[dict[str, Any]] = []
    for m in EXOTIC_RE.finditer(text):
        base = float(m.group(1))
        bet = m.group(2).upper().replace(" ", "_")
        combo = m.group(3).strip()
        amt = float(m.group(4).replace(",", ""))
        payouts.append({
            "bet_type": bet,
            "program_nums": combo,
            "base_amount": base,
            "payout": amt,
            "pool_size": None,
        })
    return payouts


def parse_pick_payouts(text: str) -> list[dict[str, Any]]:
    """Parse Pick 3/4/5/6 and Daily Double payouts."""
    payouts: list[dict[str, Any]] = []
    for m in PICK_RE.finditer(text):
        base_str = m.group(1).upper().replace(" ", "")
        if "50" in base_str:
            base = 0.50
        elif base_str.startswith("$1"):
            base = 1.00
        elif base_str.startswith("$2"):
            base = 2.00
        else:
            base = 1.00
        name = m.group(2).upper().strip()
        bet = (name.replace("PICK THREE", "PICK3")
                   .replace("PICK FOUR", "PICK4")
                   .replace("PICK FIVE", "PICK5")
                   .replace("PICK SIX", "PICK6")
                   .replace("DAILY DOUBLE", "DD"))
        combo = m.group(3).strip()
        amt = float(m.group(4).replace(",", ""))
        pool = float(m.group(5).replace(",", "")) if m.group(5) else None
        payouts.append({
            "bet_type": bet,
            "program_nums": combo,
            "base_amount": base,
            "payout": amt,
            "pool_size": pool,
        })
    return payouts


def parse_trips(text: str, horse_names: list[str]) -> list[dict[str, Any]]:
    """Extract per-horse trip notes from the narrative paragraph.

    The trip paragraph appears after the pedigree line and before "Owners-".
    Each horse's trip starts with their NAME IN ALL CAPS.
    """
    # Locate the trip block: between pedigree (ends with ".") and "Owners-"
    owners_idx = text.find("Owners-")
    if owners_idx < 0:
        return []

    # Find the pedigree line - it starts with a color/sex pattern.
    # DRF format: "Ch. f," "B. g," "Dk. b or br. m," "Gr/Ro. c,"
    # Note: comma (not period) follows the sex letter.
    pedigree_match = re.search(
        r"\b(?:Ch|B|Dk|Gr|Ro|Bay|Gr/Ro)\.\s*(?:b or br\.\s*)?(?:c|f|g|h|m)\s*,",
        text,
    )
    if not pedigree_match:
        return []

    # Trip block: pedigree ends at "(StateCode)." e.g. "(Md)." or "(Ky)."
    # We want trip block to start after that period.
    ped_block_end = re.search(
        r"\([A-Za-z]{2,4}\)\s*\.",
        text[pedigree_match.start():owners_idx],
    )
    if ped_block_end:
        trip_start = pedigree_match.start() + ped_block_end.end()
    else:
        # Fallback: first ". " after pedigree match
        ped_end_search = text.find(". ", pedigree_match.end())
        if ped_end_search < 0:
            return []
        trip_start = ped_end_search + 2

    trip_block = text[trip_start:owners_idx].strip()

    # Split by horse names. Each horse's trip starts with their name in caps.
    # PDF extraction sometimes mashes words together (e.g. "SECURE'SHOPE" instead
    # of "SECURE'S HOPE"). We build two patterns per horse: exact-with-spaces
    # and space-collapsed, and try both.
    positions: list[tuple[int, str]] = []
    seen: set[str] = set()

    for orig in horse_names:
        upper = orig.upper()
        if upper in seen:
            continue
        seen.add(upper)
        # Pattern 1: literal name where:
        #  - leading word boundary required
        #  - words separated by 0+ whitespace (catches mashed-together text)
        #  - trailing: NOT followed by another uppercase letter (so a longer
        #    horse name with same prefix doesn't match, but punctuation/lowercase OK)
        words = upper.split()
        joined = r"\s*".join(re.escape(w) for w in words)
        pattern = re.compile(r"\b" + joined + r"(?![A-Z])")
        m = pattern.search(trip_block)
        if m:
            positions.append((m.start(), orig))
            continue
        # Pattern 2: collapse all spaces (last resort, e.g. "ITSAMONSTAMASH")
        collapsed = upper.replace(" ", "")
        pattern2 = re.compile(r"\b" + re.escape(collapsed) + r"(?![A-Z])")
        m2 = pattern2.search(trip_block)
        if m2:
            positions.append((m2.start(), orig))

    if not positions:
        return []

    positions.sort()

    trips: list[dict[str, Any]] = []
    for i, (pos, horse) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(trip_block)
        narrative = trip_block[pos:end].strip()
        # Clean up: collapse whitespace
        narrative = re.sub(r"\s+", " ", narrative)
        tags = tag_trip(narrative)
        trips.append({
            "horse_name": horse,
            "trip_raw": narrative,
            **tags,
        })
    return trips


def tag_trip(narrative: str) -> dict[str, Any]:
    """Analyze trip narrative and return structured tags."""
    text_lc = narrative.lower()

    # Trouble score
    trouble_tags: list[str] = []
    score = "CLEAN"
    for kw in TROUBLE_KEYWORDS["MAJOR"]:
        if re.search(kw, text_lc):
            score = "MAJOR"
            trouble_tags.append(kw.strip(r"\b").strip("()"))
    if score != "MAJOR":
        for kw in TROUBLE_KEYWORDS["MINOR"]:
            if re.search(kw, text_lc):
                score = "MINOR"
                trouble_tags.append(kw.strip(r"\b").strip("()"))

    # Wide-trip tags
    for kw, label in WIDE_KEYWORDS:
        if re.search(kw, text_lc):
            trouble_tags.append(label)
            if label in ("5w", "6w", "7w", "widest", "very_wide") and score == "CLEAN":
                score = "MINOR"

    # Running style (first matching tier wins)
    style = None
    for s, patterns in RUNNING_STYLE_KEYWORDS.items():
        for p in patterns:
            if re.search(p, text_lc):
                style = s
                break
        if style:
            break

    # Pace role (more specific than running style)
    pace_role = None
    if re.search(r"\bset the (?:pace|early lead)\b", text_lc):
        pace_role = "lone_speed"
    elif re.search(r"\bdueled\b|\bvied\b|\bdisputed the pace\b|\bsparred\b", text_lc):
        pace_role = "duel"
    elif re.search(r"\bpressed\b|\bprompted the pace\b", text_lc):
        pace_role = "presser"
    elif re.search(r"\bstalked\b|\btracked\b", text_lc):
        pace_role = "stalker"
    elif re.search(r"\boff the pace\b|\bdrafted back\b", text_lc):
        pace_role = "off_pace"
    elif re.search(r"\bvoid of speed\b|\bwell back\b|\blagged\b|\btrailed\b", text_lc):
        pace_role = "deep_closer"

    # Short summary: first sentence trimmed
    first_sentence = re.split(r"\.\s+", narrative, maxsplit=1)[0]
    if len(first_sentence) > 140:
        first_sentence = first_sentence[:137] + "..."

    return {
        "running_style": style,
        "trouble_score": score,
        "trouble_tags": json.dumps(sorted(set(trouble_tags))),
        "pace_role": pace_role,
        "trip_notes_summary": first_sentence,
    }


def parse_scratches(text: str) -> list[dict[str, Any]]:
    """Extract scratched horses."""
    out: list[dict[str, Any]] = []
    m = SCRATCHED_RE.search(text)
    if not m:
        return out
    body = m.group(1).strip()
    # Each entry: "Horse Name ( date trk_ref )"
    for entry in re.split(r"\)\s*,\s*", body):
        entry = entry.strip().rstrip(")")
        if not entry:
            continue
        sub = re.match(r"(.+?)\s*\(\s*(.+?)\s*$", entry)
        if sub:
            out.append({
                "horse_name": sub.group(1).strip(),
                "last_raced_raw": sub.group(2).strip(),
            })
        else:
            out.append({"horse_name": entry.strip(), "last_raced_raw": None})
    return out


# ============================================================================
# DATABASE WRITES
# ============================================================================

def ensure_schema(db: sqlite3.Connection) -> None:
    """Create chart_* tables if they don't exist."""
    if not SCHEMA_PATH.exists():
        raise RuntimeError(f"Schema file not found: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    db.commit()


def link_to_races_table(db: sqlite3.Connection, track_code: str, race_date: str,
                       race_num: int) -> int | None:
    """Find matching races.id for a given track/date/race_num."""
    cur = db.execute(
        "SELECT id FROM races WHERE track_code=? AND race_date=? AND race_num=?",
        (track_code, race_date, race_num),
    )
    row = cur.fetchone()
    return row[0] if row else None


def write_race(db: sqlite3.Connection, race: dict[str, Any], fetched_ts: str) -> int:
    """Upsert one parsed race into chart_* tables. Returns chart_race_id."""
    race_id = link_to_races_table(db, race["track_code"], race["race_date"], race["race_num"])
    parsed_ts = datetime.utcnow().isoformat()

    # Upsert chart_races
    db.execute("""
        INSERT INTO chart_races (race_id, track_code, race_date, race_num,
            distance_raw, surface, race_type, purse, conditions_raw, weather,
            track_condition, off_time, start_note, fetched_ts, parsed_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(track_code, race_date, race_num) DO UPDATE SET
            race_id = excluded.race_id,
            distance_raw = excluded.distance_raw,
            surface = excluded.surface,
            race_type = excluded.race_type,
            purse = excluded.purse,
            conditions_raw = excluded.conditions_raw,
            weather = excluded.weather,
            track_condition = excluded.track_condition,
            off_time = excluded.off_time,
            start_note = excluded.start_note,
            parsed_ts = excluded.parsed_ts
    """, (
        race_id, race["track_code"], race["race_date"], race["race_num"],
        race.get("distance_raw"), race.get("surface"), race.get("race_type"),
        race.get("purse"), race.get("conditions_raw"), race.get("weather"),
        race.get("track_condition"), race.get("off_time"), race.get("start_note"),
        fetched_ts, parsed_ts,
    ))
    chart_race_id = db.execute(
        "SELECT id FROM chart_races WHERE track_code=? AND race_date=? AND race_num=?",
        (race["track_code"], race["race_date"], race["race_num"]),
    ).fetchone()[0]

    # Wipe + reinsert children for this race (idempotent)
    for table in ["chart_horses", "chart_fractions", "chart_payouts",
                  "chart_trips", "chart_scratches"]:
        if table == "chart_fractions":
            db.execute(f"DELETE FROM {table} WHERE chart_race_id=?", (chart_race_id,))
        else:
            db.execute(f"DELETE FROM {table} WHERE chart_race_id=?", (chart_race_id,))

    # Horses
    for h in race["horses"]:
        db.execute("""
            INSERT INTO chart_horses (chart_race_id, program_num, horse_name,
                last_raced_raw, equipment, age, weight, post_position,
                start_position, calls_raw, finish_position, finish_margin_raw,
                jockey, claim_price, odds, is_winner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chart_race_id, h.get("program_num"), h["horse_name"],
            h.get("last_raced_raw"), h.get("equipment"), h.get("age"),
            h.get("weight"), h.get("post_position"), h.get("start_position"),
            h.get("calls_raw"), h.get("finish_position"), h.get("finish_margin_raw"),
            h.get("jockey"), h.get("claim_price"), h.get("odds"),
            h.get("is_winner", 0),
        ))

    # Fractions
    f = race.get("fractions", {})
    if f:
        db.execute("""
            INSERT INTO chart_fractions (chart_race_id, frac_1, frac_2, frac_3,
                frac_4, frac_5, final_time, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chart_race_id, f.get("frac_1"), f.get("frac_2"), f.get("frac_3"),
            f.get("frac_4"), f.get("frac_5"), f.get("final_time"), f.get("raw_text"),
        ))

    # Payouts
    for p in race["payouts"]:
        db.execute("""
            INSERT INTO chart_payouts (chart_race_id, bet_type, program_nums,
                base_amount, payout, pool_size)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chart_race_id, p["bet_type"], p.get("program_nums"),
            p.get("base_amount"), p.get("payout"), p.get("pool_size"),
        ))

    # Trips
    for t in race["trips"]:
        prog_num = None
        for h in race["horses"]:
            if h["horse_name"].upper() == t["horse_name"].upper():
                prog_num = h.get("program_num")
                break
        db.execute("""
            INSERT INTO chart_trips (chart_race_id, horse_name, program_num,
                trip_raw, running_style, trouble_score, trouble_tags, pace_role,
                trip_notes_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chart_race_id, t["horse_name"], prog_num, t["trip_raw"],
            t.get("running_style"), t.get("trouble_score"), t.get("trouble_tags"),
            t.get("pace_role"), t.get("trip_notes_summary"),
        ))

    # Scratches
    for s in race["scratches"]:
        db.execute("""
            INSERT INTO chart_scratches (chart_race_id, horse_name, last_raced_raw)
            VALUES (?, ?, ?)
        """, (chart_race_id, s["horse_name"], s.get("last_raced_raw")))

    return chart_race_id


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def parse_chart_pdf(pdf_path: Path, track: str, date: str,
                    db_path: Path = DB_PATH, dry_run: bool = False) -> dict[str, Any]:
    """End-to-end: PDF → parsed dict → DB write."""
    print(f"[PARSE] Extracting text from {pdf_path}")
    text = extract_text(pdf_path)

    print(f"[PARSE] Splitting into races...")
    race_blocks = split_into_races(text)
    print(f"[PARSE] Found {len(race_blocks)} races")

    parsed_races: list[dict[str, Any]] = []
    for race_num, block in race_blocks:
        race = parse_race(race_num, block, track, date)
        parsed_races.append(race)
        is_completed = len(race["horses"]) > 0
        status = "COMPLETED" if is_completed else "ENTRIES_ONLY"
        print(f"  R{race_num}: {status} — {len(race['horses'])} horses, "
              f"{len(race['trips'])} trips, {len(race['payouts'])} payouts")

    if dry_run:
        print("[DRY-RUN] Skipping DB write")
        return {"races": parsed_races, "races_written": 0}

    fetched_ts = datetime.utcnow().isoformat()
    completed_races = [r for r in parsed_races if r["horses"]]

    db = sqlite3.connect(str(db_path))
    try:
        ensure_schema(db)
        written = 0
        for race in completed_races:
            write_race(db, race, fetched_ts)
            written += 1
        db.commit()
        print(f"[DB] Wrote {written} completed races to {db_path}")
    finally:
        db.close()

    return {"races": parsed_races, "races_written": len(completed_races)}


def main() -> int:
    p = argparse.ArgumentParser(description="DRF chart parser")
    p.add_argument("--track", required=True, help="3-letter track code (e.g. LRL)")
    p.add_argument("--date", required=True, help="YYYYMMDD")
    p.add_argument("--pdf", help="Local PDF path (skip fetch)")
    p.add_argument("--db", default=str(DB_PATH), help=f"DB path (default: {DB_PATH})")
    p.add_argument("--dry-run", action="store_true", help="Parse only, no DB write")
    p.add_argument("--force", action="store_true", help="Re-fetch even if cached")
    args = p.parse_args()

    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
            return 1
    else:
        pdf_path = fetch_chart_pdf(args.track, args.date, force=args.force)

    result = parse_chart_pdf(pdf_path, args.track, args.date,
                              db_path=Path(args.db), dry_run=args.dry_run)
    print(f"\n[DONE] Parsed {len(result['races'])} races, wrote {result['races_written']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
