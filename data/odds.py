"""
Odds Scraper
============
Fetches morning line and live odds from TVG.com and TwinSpires.com
"""

import requests
import logging
import time
import json
from bs4 import BeautifulSoup
from config.settings import REQUEST_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger("racing_agent")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
}


def get_tvg_odds(track_code: str, race_num: int):
    """
    Fetch live odds from TVG for a specific race.
    Returns list of {program_num, horse_name, odds} dicts.
    """
    try:
        # TVG API endpoint for live odds
        url = f"https://www.tvg.com/ajax/race-program/{track_code}/{race_num}"
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200:
            return []

        # Try JSON first
        try:
            data = resp.json()
            runners = data.get("runners", data.get("horses", data.get("entries", [])))
            odds_list = []
            for runner in runners:
                odds_list.append({
                    "program_num": str(runner.get("programNumber", runner.get("num", ""))),
                    "horse_name":  runner.get("horseName", runner.get("name", "")),
                    "odds":        str(runner.get("morningLineOdds", runner.get("odds", ""))),
                })
            return [o for o in odds_list if o["horse_name"]]
        except Exception:
            pass

        # Fallback to HTML parsing
        soup = BeautifulSoup(resp.text, "html.parser")
        odds_list = []
        for row in soup.select("tr.runner, tr.horse, .race-entry"):
            cells = row.find_all(["td", "span"])
            if len(cells) >= 2:
                odds_list.append({
                    "program_num": cells[0].text.strip(),
                    "horse_name":  cells[1].text.strip(),
                    "odds":        cells[-1].text.strip() if len(cells) > 2 else "N/A",
                })
        return odds_list

    except Exception as e:
        logger.warning(f"TVG odds error for {track_code} R{race_num}: {e}")
        return []


def get_twinspiresodds(track_code: str, race_num: int):
    """
    Fetch odds from TwinSpires as backup source.
    Returns list of {program_num, horse_name, odds} dicts.
    """
    try:
        url = f"https://www.twinspires.com/horse-racing/{track_code.lower()}/race-{race_num}"
        time.sleep(REQUEST_DELAY)
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        odds_list = []

        for row in soup.select(".runner-row, .horse-row, tr.entry"):
            num_el   = row.select_one(".program-number, .num, td:first-child")
            name_el  = row.select_one(".horse-name, .name, td:nth-child(2)")
            odds_el  = row.select_one(".odds, .morning-line, td.ml")

            if num_el and name_el:
                odds_list.append({
                    "program_num": num_el.text.strip(),
                    "horse_name":  name_el.text.strip(),
                    "odds":        odds_el.text.strip() if odds_el else "N/A",
                })

        return odds_list

    except Exception as e:
        logger.warning(f"TwinSpires odds error for {track_code} R{race_num}: {e}")
        return []


def get_best_odds(track_code: str, race_num: int):
    """
    Try TVG first, fall back to TwinSpires.
    Returns best available odds list.
    """
    odds = get_tvg_odds(track_code, race_num)
    if odds:
        logger.info(f"Got {len(odds)} odds from TVG for {track_code} R{race_num}")
        return odds, "TVG"

    odds = get_twinspiresodds(track_code, race_num)
    if odds:
        logger.info(f"Got {len(odds)} odds from TwinSpires for {track_code} R{race_num}")
        return odds, "TwinSpires"

    logger.warning(f"No odds available for {track_code} R{race_num}")
    return [], "N/A"
