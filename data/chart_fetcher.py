import os, logging, subprocess, requests
import pytz
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("racing_agent")
BASE_URL = "https://www.equibase.com/static/chart/PDF"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
CACHE_DIR = Path.home() / "agents/racing-agent/data/charts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def fetch_chart_pdf(track_code, date_str, force=False):
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None
    mmddyy = dt.strftime("%m%d%y")
    url = f"{BASE_URL}/{track_code}{mmddyy}USA.pdf"
    cache_path = CACHE_DIR / f"{track_code}_{date_str}.pdf"
    if cache_path.exists() and not force:
        return cache_path
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        if not resp.content.startswith(b"%PDF"):
            return None
        cache_path.write_bytes(resp.content)
        logger.info(f"Chart fetched: {track_code} {date_str} ({len(resp.content)} bytes)")
        return cache_path
    except Exception as e:
        logger.warning(f"Chart fetch error {track_code} {date_str}: {e}")
        return None

def pdf_to_text(pdf_path):
    if not pdf_path or not pdf_path.exists():
        return ""
    try:
        result = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, timeout=30)
        return result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        logger.error("pdftotext not installed. Run: brew install poppler")
        return ""
    except Exception as e:
        logger.warning(f"PDF extraction error: {e}")
        return ""

def get_chart_text(track_code, date_str):
    pdf_path = fetch_chart_pdf(track_code, date_str)
    return pdf_to_text(pdf_path) if pdf_path else ""

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    text = get_chart_text("PRX", "20260414")
    if text:
        print(f"Extracted {len(text)} chars")
        print(text[:500])
    else:
        print("Failed to fetch chart")


def fetch_all_todays_charts():
    from db.database import get_todays_races, save_chart_time
    from data.chart_parser import parse_chart_text
    today = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y%m%d")
    races = get_todays_races()
    race_lookup = {(r["track_code"], r["race_num"]): r["id"] for r in races}
    track_codes = list({r["track_code"] for r in races})
    if not track_codes:
        logger.info("No tracks to fetch charts for")
        return 0
    total_saved = 0
    for code in track_codes:
        text = get_chart_text(code, today)
        if not text:
            continue
        parsed_races = parse_chart_text(text, code, today)
        for race_data in parsed_races:
            race_id = race_lookup.get((code, race_data["race_num"]))
            save_chart_time(race_data, race_id)
            total_saved += 1
        logger.info(f"Chart parsed: {code} -- {len(parsed_races)} races saved")
    logger.info(f"Chart batch complete: {total_saved} race times saved")
    return total_saved
