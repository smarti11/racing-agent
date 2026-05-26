"""Fetch scratches from Equibase's late-changes pages.
Faster than waiting for entries to refresh - this hits the dedicated scratch feed
that Equibase publishes for each track, updated near-real-time."""

import logging
import re
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
URL_TEMPLATE = "https://www.equibase.com/static/latechanges/html/latechanges{code}-USA.html"


def fetch_track_scratches(track_code):
    """Returns list of (race_num, program_num, horse_name, reason) tuples for scratched horses.
    Returns empty list on any error so caller can continue with other tracks."""
    url = URL_TEMPLATE.format(code=track_code)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"[SCRATCH FETCH] {track_code}: HTTP {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"[SCRATCH FETCH] {track_code}: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    table = soup.find("table", id="fullChanges")
    if not table:
        return []

    scratches = []
    current_race = None

    for tr in table.find_all("tr"):
        # Race header rows look like: <tr class="group-header">...<th class="race">Race: 2</th>...
        race_th = tr.find("th", class_="race")
        if race_th:
            m = re.search(r"Race:\s*(\d+)", race_th.get_text(strip=True))
            if m:
                current_race = int(m.group(1))
            continue

        # Data rows have td.pgm, td.horse, td.changes
        pgm_td = tr.find("td", class_="pgm")
        horse_td = tr.find("td", class_="horse")
        changes_td = tr.find("td", class_="changes")

        if not (pgm_td and horse_td and changes_td and current_race):
            continue

        # Only process rows that say "Scratched"
        changes_text = changes_td.get_text(strip=True)
        if "Scratched" not in changes_text:
            continue

        # Extract program number — text is like "#3"
        pgm_text = pgm_td.get_text(strip=True).lstrip("#").strip()
        # Remove non-digits except A/B suffixes (coupled entries)
        pgm_match = re.match(r"^(\d+[A-Za-z]?)", pgm_text)
        if not pgm_match:
            continue
        program_num = pgm_match.group(1)

        horse_name = horse_td.get_text(strip=True)
        reason = changes_text.replace("Scratched", "").strip(" -")

        scratches.append((current_race, program_num, horse_name, reason))

    return scratches


def fetch_and_mark_scratches_for_today():
    """Fetch scratch data for all tracks running today and mark them in DB.
    Returns count of new scratches found."""
    from db.database import get_conn, mark_scratched
    from datetime import datetime
    import pytz
    EASTERN = pytz.timezone("US/Eastern")
    today = datetime.now(EASTERN).date().isoformat()

    with get_conn() as conn:
        tracks = conn.execute("""
            SELECT DISTINCT track_code, track_name
            FROM races
            WHERE race_date = ?
            ORDER BY track_code
        """, (today,)).fetchall()

    new_scratches = 0
    for track_row in tracks:
        track_code = track_row["track_code"]
        track_name = track_row["track_name"]
        if not track_code:
            continue

        scratches = fetch_track_scratches(track_code)
        if not scratches:
            continue

        for race_num, program_num, horse_name, reason in scratches:
            with get_conn() as conn:
                # Find race_id for this track + race_num + today
                row = conn.execute("""
                    SELECT r.id FROM races r
                    WHERE r.race_date = ? AND r.track_code = ? AND r.race_num = ?
                """, (today, track_code, race_num)).fetchone()
                if not row:
                    continue
                race_id = row["id"]

                # Check if already scratched
                ent = conn.execute("""
                    SELECT scratched FROM entries
                    WHERE race_id = ? AND program_num = ?
                """, (race_id, program_num)).fetchone()
                if not ent:
                    continue
                if ent["scratched"]:
                    continue  # already known

                mark_scratched(race_id, program_num)
                new_scratches += 1
                logger.info(
                    f"[SCRATCH FROM EQB] {track_name} R{race_num} #{program_num} "
                    f"{horse_name} — {reason}"
                )

    if new_scratches > 0:
        # Touch regen flag so dashboard updates promptly
        import os
        from pathlib import Path
        flag_path = Path(__file__).parent.parent / ".regen_now"
        try:
            flag_path.touch()
        except Exception:
            pass

    logger.info(f"[SCRATCH FETCHER] Found {new_scratches} new scratches across {len(tracks)} tracks")
    return new_scratches
