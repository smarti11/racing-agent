"""
Equibase Mobile Scraper
========================
Fetches race entries from Equibase's mobile site which uses
simple, stable HTML with no JavaScript requirements.

URL pattern:
  Track list:    mobile.equibase.com/html/entries.html
  Day card:      mobile.equibase.com/html/entries{CODE}{YYYYMMDD}.html
  Race entries:  mobile.equibase.com/html/entries{CODE}{YYYYMMDD}{RR}.html

Data available: horse name, jockey, trainer, program number, morning line odds
"""

import requests
import logging
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from config.settings import REQUEST_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger("racing_agent")

BASE = "https://mobile.equibase.com/html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
}

# Track code mapping — Equibase mobile codes
TRACK_CODES = {
    "Aqueduct":                  "AQU",
    "Camarero":                  "CMR",
    "Charles Town":              "CT",
    "Evangeline":                "EVD",
    "Fonner Park":               "FON",
    "Gulfstream Park":           "GP",
    "Horseshoe Indianapolis":    "IND",
    "Keeneland":                 "KEE",
    "Laurel Park":               "LRL",
    "Los Alamitos Quarter Horse":"LA",
    "Louisiana Downs":           "EVD",
    "Mahoning Valley Race Course":"MVR",
    "Oaklawn Park":              "OP",
    "Parx Racing":               "PRX",
    "Penn National":             "PEN",
    "Remington Park":            "RP",
    "Sam Houston":               "HOU",
    "Santa Anita":               "SA",
    "Sunland Park":              "SUN",
    "Tampa Bay":                 "TAM",
    "Turf Paradise":             "TUP",
    "Will Rogers":               "WRD",
    "Churchill Downs":           "CD",
    "Belmont Park":              "BEL",
    "Saratoga":                  "SAR",
    "Pimlico":                   "PIM",
    "Del Mar":                   "DMR",
    "Golden Gate Fields":        "GG",
    "Prairie Meadows":           "PRM",
    "Canterbury Park":           "CBY",
    "Fair Grounds":              "FG",
    "Delta Downs":               "DED",
    "Monmouth Park":             "MTH",
    "Mountaineer Park":          "MNR",
}


def get_todays_tracks():
    """
    Fetch list of tracks with entries today from Equibase mobile.
    Returns list of {name, code} dicts.
    """
    try:
        url = f"{BASE}/entries.html"
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        tracks = []
        seen = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Match pattern: entries{CODE}.html (full or relative URLs)
            # Strip full URL prefix if present
            href_short = href.split("/")[-1]
            m = re.match(r"entries([A-Z0-9]+)\.html", href_short)
            if m:
                code = m.group(1)
                name = link.text.strip()
                # Filter out pick pools and non-US tracks
                skip_keywords = ["Pick", "Brazil", "Panama", "Chile", "Hipico",
                                  "Coast", "Cross", "Tropical", "Sunset", "Turf Pick",
                                  "Houston Turf", "Sa All", "Kentucky Derby Future"]
                if any(kw.lower() in name.lower() for kw in skip_keywords):
                    continue
                if name and name not in seen and len(name) > 2:
                    seen.add(name)
                    tracks.append({"name": name, "code": code})

        # Apply excluded tracks blocklist from settings
        try:
            from config.settings import EXCLUDED_TRACKS
            tracks = [t for t in tracks if t["name"] not in EXCLUDED_TRACKS]
        except Exception:
            pass

        logger.info(f"Found {len(tracks)} tracks with entries today")
        return tracks

    except Exception as e:
        logger.error(f"Error fetching today's tracks: {e}")
        return []


def get_day_card(track_code: str, track_name: str, date_str: str = None):
    """
    Fetch list of races for a track on a given date.
    date_str: YYYYMMDD format. Defaults to today.
    Returns list of {race_num, post_time, url} dicts.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    try:
        url = f"{BASE}/entries{track_code}{date_str}.html"
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        races = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Strip to filename only
            href_short = href.split("/")[-1]
            # Match race entry links: entriesKEE202604030{N}.html
            m = re.match(rf"entries{track_code}(\d{{8}})(\d{{2}})\.html", href_short)
            if m:
                race_num = int(m.group(2))
                text = link.text.strip()
                # Extract post time from link text if present
                post_time = ""
                pt_m = re.search(r"(\d+:\d+)", text)
                if pt_m:
                    post_time = pt_m.group(1)
                # Build full URL
                full_url = href if href.startswith("http") else f"{BASE}/{href_short}"
                races.append({
                    "race_num": race_num,
                    "post_time": post_time,
                    "url": full_url
                })

        logger.info(f"{track_name}: Found {len(races)} races on {date_str}")
        return races

    except Exception as e:
        logger.warning(f"{track_name}: Day card error — {e}")
        return []

def get_race_entries(race_url: str, track_code: str, track_name: str, race_num: int, post_time: str):
    """
    Fetch entries for a single race from its Equibase mobile URL.
    Returns dict with race details and entries list.
    """
    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(race_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        html = resp.text
        text = BeautifulSoup(html, "html.parser").get_text()

        # Parse race conditions
        race_details = {
            "track_code": track_code,
            "track_name": track_name,
            "race_num": race_num,
            "post_time": post_time,
            "conditions": "",
            "distance": "",
            "surface": "",
        }

        for line in text.split("\n"):
            line = line.strip()
            if any(w in line for w in ["Furlongs", "Mile", "Yards"]):
                race_details["distance"] = line
            if any(w in line for w in ["Dirt", "Turf", "Synthetic", "Polytrack"]):
                race_details["surface"] = line
            if any(w in line for w in ["Maiden", "Claiming", "Allowance", "Stakes",
                                        "Handicap", "Optional", "Starter"]):
                if len(line) > 5:
                    race_details["conditions"] = line

        # Parse entries from raw HTML to preserve <br> boundaries
        # Pattern: Program: N Post: N Odds: X/Y ... <b>Horse Name</b> ... Jockey: ... Trainer: ...
        entries = []

        # Split HTML on the green separator image to get one chunk per entry
        chunks = re.split(r'<img[^>]*green\.gif[^>]*>', html)
        _n_chunks    = len(chunks)
        _n_matched   = 0
        _n_extracted = 0

        for _ci, chunk in enumerate(chunks):
            prog_m = re.search(r'Program:\s*(\w+)\s+Post:\s*(\w+)(?:\s+Odds:\s*([^\s<]+))?', chunk)
            if not prog_m:
                if chunk.strip():
                    logger.warning(
                        f"Equibase parse drop [{track_name} R{race_num}]: "
                        f"chunk {_ci} has no Program: line — "
                        f"{chunk.strip()[:200]!r}"
                    )
                continue
            _n_matched += 1

            entry = {
                "program_num": prog_m.group(1),
                "post_position": prog_m.group(2),
                "morning_line": (prog_m.group(3) or "").strip(),
                "horse_name": "",
                "jockey": "",
                "trainer": "",
                "scratched": False,
            }

            # Horse name is in <b> tags
            name_m = re.search(r'<b>([^<]+)</b>', chunk[prog_m.end():])
            if name_m:
                entry["horse_name"] = name_m.group(1).strip()
                if "scratch" in entry["horse_name"].lower() or "(S)" in entry["horse_name"]:
                    entry["scratched"] = True

            # Jockey — handle double spaces in names
            jock_m = re.search(r'Jockey:\s*([^<\n]+?)(?:<br|<BR|\n|Trainer:)', chunk)
            if jock_m:
                entry["jockey"] = re.sub(r'\s+', ' ', jock_m.group(1)).strip()

            # Trainer
            train_m = re.search(r'Trainer:\s*([^<\n]+?)(?:<br|<BR|\n|$)', chunk)
            if train_m:
                entry["trainer"] = re.sub(r'\s+', ' ', train_m.group(1)).strip()

            # Check for scratch indicators in the chunk
            if re.search(r'(?i)scratched|<s>|class="scratch"', chunk):
                entry["scratched"] = True

            if entry["horse_name"]:
                _n_extracted += 1
                entries.append(entry)
            else:
                logger.warning(
                    f"Equibase parse drop [{track_name} R{race_num}]: "
                    f"chunk {_ci} matched Program: #{entry['program_num']} but no <b>horse name</b> — "
                    f"{chunk.strip()[:200]!r}"
                )

        logger.info(
            f"Equibase parse [{track_name} R{race_num}]: "
            f"{_n_chunks} chunks, {_n_matched} matched Program:, {_n_extracted} horses extracted"
        )
        race_details["entries"] = entries
        return race_details

    except Exception as e:
        logger.warning(f"Race entry error {race_url}: {e}")
        return None
def get_all_entries_today(track_code: str, track_name: str):
    """
    Full pipeline: fetch day card then all race entries for a track.
    Returns list of race dicts with full entries.
    """
    date_str = datetime.now().strftime("%Y%m%d")
    races_meta = get_day_card(track_code, track_name, date_str)
    if not races_meta:
        return []

    races = []
    for meta in races_meta:
        race = get_race_entries(
            meta["url"], track_code, track_name,
            meta["race_num"], meta["post_time"]
        )
        if race and race.get("entries"):
            races.append(race)

    return races


def get_scratches(track_code: str, date_str: str = None):
    """
    Detect scratches by comparing current Equibase entries against
    what we already have in the DB. If a horse was in our DB but is
    no longer on the Equibase page, it has been scratched.
    """
    # SCRATCH_TIME_GATE: don't run scratch detection before 7 AM ET
    # Overnight fetches produce false positives against incomplete DB state
    try:
        import pytz
        _et = pytz.timezone("America/New_York")
        _now_et = datetime.now(_et)
        if _now_et.hour < 10:
            logger.info(f"Scratch detection skipped — before 10 AM ET ({_now_et.strftime('%H:%M')} ET)")
            return []
    except Exception:
        pass
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    from db.database import get_todays_races, get_race_entries as db_get_entries

    scratches = []
    races_meta = get_day_card(track_code, track_code, date_str)

    for meta in races_meta:
        race = get_race_entries(
            meta["url"], track_code, track_code,
            meta["race_num"], meta["post_time"]
        )
        if not race:
            continue

        current_nums = {e["program_num"] for e in race.get("entries", [])}

        db_races = get_todays_races()
        for db_race in db_races:
            if (db_race["track_code"] == track_code and
                db_race["race_num"] == meta["race_num"]):
                db_entries = db_get_entries(db_race["id"])
                active_db = [e for e in db_entries if not e["scratched"]]

                # SCRATCH_SANITY_CHECK: if live fetch returned fewer than 50%
                # of the horses we have in DB, the page parsed incorrectly.
                # Skip scratch detection for this race to avoid false positives.
                # Sanity check removed — 10AM gate is primary protection
                # save_entry resets scratched=0 so DB always shows full field
                logger.info(f"Scratch check: {track_code} R{meta['race_num']} live={len(current_nums)} db={len(active_db)}")

                # CONSECUTIVE_MISS_GUARD: only scratch a horse if absent
                # from 2 consecutive fetches — one bad Equibase page = false positive
                absent = [e for e in active_db if e["program_num"] not in current_nums]
                if not absent:
                    break

                # Cap at 3 scratches per race per pass — more than that = bad page
                if len(absent) > 3:
                    logger.warning(
                        f"Scratch cap exceeded: {track_code} R{meta['race_num']} "
                        f"absent={len(absent)} — skipping entire race"
                    )
                    break

                # Second-chance: re-fetch the page and confirm absences
                import time
                time.sleep(2)
                race2 = get_race_entries(
                    meta["url"], track_code, track_code,
                    meta["race_num"], meta["post_time"]
                )
                if not race2:
                    logger.warning(f"Scratch second-fetch failed: {track_code} R{meta['race_num']} — skipping")
                    break
                confirm_nums = {e["program_num"] for e in race2.get("entries", [])}

                for db_entry in active_db:
                    prog = db_entry["program_num"]
                    if prog not in current_nums and prog not in confirm_nums:
                        scratches.append({
                            "race_num": meta["race_num"],
                            "program_num": prog,
                            "horse_name": db_entry["horse_name"]
                        })
                        logger.info(f"Scratch CONFIRMED (2-fetch): {track_code} R{meta['race_num']} #{prog} {db_entry['horse_name']}")
                    elif prog not in current_nums and prog in confirm_nums:
                        logger.info(f"Scratch FALSE POSITIVE avoided: {track_code} R{meta['race_num']} #{prog} {db_entry['horse_name']} reappeared on 2nd fetch")
                break

    return scratches



def get_scratches_desktop(track_code: str, date_str: str = None):
    """
    Detect scratches using Equibase DESKTOP entry page which explicitly
    marks scratched horses with class="scratch" and id="RACE-PROG#".
    This replaces the broken absence-detection approach.
    """
    import requests
    from bs4 import BeautifulSoup
    import re

    try:
        import pytz
        _et = pytz.timezone("America/New_York")
        _now_et = datetime.now(_et)
        if _now_et.hour < 10:
            logger.info(f"Scratch detection skipped — before 10 AM ET ({_now_et.strftime('%H:%M')} ET)")
            return []
    except Exception:
        pass

    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    # Desktop URL format: /static/entry/CD052326USA-EQB.html
    # date_str is YYYYMMDD, need MMDDYY
    try:
        mmddyy = date_str[4:6] + date_str[6:8] + date_str[2:4]
    except Exception:
        logger.warning(f"get_scratches_desktop: bad date_str {date_str}")
        return []

    url = f"https://www.equibase.com/static/entry/{track_code}{mmddyy}USA-EQB.html"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.warning(f"get_scratches_desktop: {url} returned {r.status_code}")
            return []
    except Exception as e:
        logger.warning(f"get_scratches_desktop: request failed {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    scratch_rows = soup.find_all("tr", class_="scratch")

    scratches = []
    for row in scratch_rows:
        # Horse name
        a = row.find("a")
        horse_name = a.get_text(strip=True) if a else None

        # Race and program number from odds cell id e.g. id="5-2"
        odds_td = row.find("td", id=re.compile(r"^\d+-\d+$"))
        if not odds_td:
            continue
        try:
            parts = odds_td["id"].split("-")
            race_num = int(parts[0])
            prog_num = str(int(parts[1]))
        except Exception:
            continue

        scratches.append({
            "race_num": race_num,
            "program_num": prog_num,
            "horse_name": horse_name or "Unknown"
        })
        logger.info(f"Scratch (desktop): {track_code} R{race_num} #{prog_num} {horse_name}")

    logger.info(f"get_scratches_desktop: {track_code} found {len(scratches)} scratches")
    return scratches


def get_jockey_stats(jockey_name: str):
    """Placeholder — jockey stats require Equibase account."""
    return None


def get_trainer_stats(trainer_name: str):
    """Placeholder — trainer stats require Equibase account."""
    return None
