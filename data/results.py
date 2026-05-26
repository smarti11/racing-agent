"""
Results Scraper
================
Fetches race results from Equibase mobile site.
URL pattern mirrors entries exactly — just swap "entries" for "results".

Results page format:
  5 Projectability $3.12 $2.10 $2.10   (win/place/show payouts)
  1 El Paco $2.90 $2.18                 (place/show only)
  4 Major Bourbon $2.10                 (show only)
  Exacta 5-1 $3.23
  Trifecta 5-1-4 $2.49
  Superfecta 5-1-4-6 $0.92
  Also Ran: 6 Klimt Master, 3 Juniors Pal
  Scratches: Stevie Wonderful
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


def get_results_for_race(track_code: str, date_str: str, race_num: int) -> dict:
    """
    Fetch result for a single race.
    date_str: YYYYMMDD format
    Returns dict with winner, place, show, payouts, exotics.
    """
    rr = str(race_num).zfill(2)
    url = f"{BASE}/results{track_code}{date_str}{rr}.html"

    try:
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return parse_result_page(resp.text, track_code, date_str, race_num)

    except Exception as e:
        logger.warning(f"Results fetch error {track_code} R{race_num}: {e}")
        return None


def parse_result_page(html: str, track_code: str, date_str: str, race_num: int) -> dict:
    """Parse Equibase mobile results HTML."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "track_code": track_code,
        "race_num": race_num,
        "date_str": date_str,
        "winner_num": None,
        "winner_name": None,
        "winner_win_payout": None,
        "winner_place_payout": None,
        "winner_show_payout": None,
        "second_num": None,
        "second_name": None,
        "second_place_payout": None,
        "second_show_payout": None,
        "third_num": None,
        "third_name": None,
        "third_show_payout": None,
        "exacta": None,
        "trifecta": None,
        "superfecta": None,
        "daily_double": None,
        "pick3": None,        # PICK_N_PARSING_APPLIED
        "pick4": None,
        "pick5": None,
        "pick6": None,
        "also_ran": [],
        "scratches": [],
    }

    # Find the finish order table
    # Format: "5 Projectability $3.12 $2.10 $2.10"
    finish_pos = 0
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match finish line: number horsename $X.XX [$X.XX [$X.XX]]
        m = re.match(r'^(\d+[A-Za-z]?)\s+(.+?)(?:\s+\$(\d+\.\d+))?(?:\s+\$(\d+\.\d+))?(?:\s+\$(\d+\.\d+))?$', line)
        if m and m.group(2) and not any(k in line for k in ["Exacta","Trifecta","Superfecta","Daily","Pick","Quinella"]):
            num  = m.group(1)
            name = m.group(2).strip()
            p1   = float(m.group(3)) if m.group(3) else None
            p2   = float(m.group(4)) if m.group(4) else None
            p3   = float(m.group(5)) if m.group(5) else None

            # Validate it's actually a horse (name has letters, not all numbers)
            if re.search(r'[A-Za-z]', name) and len(name) > 1:
                if finish_pos == 0:
                    result["winner_num"]          = num
                    result["winner_name"]          = name
                    result["winner_win_payout"]    = p1
                    result["winner_place_payout"]  = p2
                    result["winner_show_payout"]   = p3
                    finish_pos += 1
                elif finish_pos == 1:
                    result["second_num"]           = num
                    result["second_name"]          = name
                    result["second_place_payout"]  = p1
                    result["second_show_payout"]   = p2
                    finish_pos += 1
                elif finish_pos == 2:
                    result["third_num"]            = num
                    result["third_name"]           = name
                    result["third_show_payout"]    = p1
                    finish_pos += 1

        # Exotics
        if line.startswith("Exacta") or line.startswith("Perfecta"):
            m2 = re.search(r'\$(\d+\.\d+)', line)
            if m2:
                result["exacta"] = {"combo": line.split("$")[0].strip(), "payout": float(m2.group(1))}

        if line.startswith("Trifecta"):
            m2 = re.search(r'\$(\d+\.\d+)', line)
            if m2:
                result["trifecta"] = {"combo": line.split("$")[0].strip(), "payout": float(m2.group(1))}

        if line.startswith("Superfecta"):
            m2 = re.search(r'\$(\d+\.\d+)', line)
            if m2:
                result["superfecta"] = {"combo": line.split("$")[0].strip(), "payout": float(m2.group(1))}

        if line.startswith("Daily Double") or line.startswith("Double"):
            m2 = re.search(r'\$(\d+\.\d+)', line)
            if m2:
                result["daily_double"] = {"combo": line.split("$")[0].strip(), "payout": float(m2.group(1))}

        # PICK_N_PARSING_APPLIED: Pick 3 / 4 / 5 / 6
        # Equibase formats: "Pick 3 1-2-3 $42.20", "Pick Four ...", etc.
        for _pick_key, _pick_patterns in (
            ("pick3", ("Pick 3", "Pick Three")),
            ("pick4", ("Pick 4", "Pick Four")),
            ("pick5", ("Pick 5", "Pick Five")),
            ("pick6", ("Pick 6", "Pick Six")),
        ):
            if any(line.startswith(p) for p in _pick_patterns):
                _m = re.search(r'\$(\d+\.\d+)', line)
                if _m:
                    result[_pick_key] = {
                        "combo": line.split("$")[0].strip(),
                        "payout": float(_m.group(1)),
                    }

        # Also ran
        if "Also Ran:" in line or "Also ran:" in line:
            also = line.split(":", 1)[1].strip()
            result["also_ran"] = [a.strip() for a in also.split(",") if a.strip()]

        # Scratches
        if line == "Scratches" or line == "Scratches:":
            j = i + 1
            while j < len(lines) and j < i + 5:
                if lines[j] and not lines[j].startswith("["):
                    result["scratches"].append(lines[j])
                j += 1

        i += 1

    if result["winner_name"]:
        logger.info(f"{track_code} R{race_num}: Winner = #{result['winner_num']} {result['winner_name']} (${result['winner_win_payout']})")

    return result if result["winner_name"] else None


def get_todays_results_all_tracks(tracks: list) -> list:
    """
    Fetch all available results for today across all tracks.
    Returns list of result dicts.
    """
    date_str = datetime.now().strftime("%Y%m%d")
    all_results = []

    for track in tracks:
        code = track["code"]
        name = track["name"]

        # Check if this track has results today
        index_url = f"{BASE}/results{code}.html"
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(index_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            has_today = False
            for link in soup.find_all("a", href=True):
                href = link["href"].split("/")[-1]
                if re.match(rf"results{code}{date_str}\.html", href):
                    has_today = True
                    break

            if not has_today:
                continue

            # Fetch day results index
            day_url = f"{BASE}/results{code}{date_str}.html"
            time.sleep(REQUEST_DELAY)
            resp2 = requests.get(day_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp2.status_code != 200:
                continue

            soup2 = BeautifulSoup(resp2.text, "html.parser")
            race_count = 0
            for link in soup2.find_all("a", href=True):
                href = link["href"].split("/")[-1]
                m = re.match(rf"results{code}(\d{{8}})(\d{{2}})\.html", href)
                if m:
                    race_num = int(m.group(2))
                    result = get_results_for_race(code, date_str, race_num)
                    if result:
                        result["track_name"] = name
                        all_results.append(result)
                        race_count += 1

            if race_count:
                logger.info(f"{name}: Fetched {race_count} results")

        except Exception as e:
            logger.warning(f"Results error for {name}: {e}")
            continue

    logger.info(f"Total results fetched: {len(all_results)}")
    return all_results
