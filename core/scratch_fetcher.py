"""Fetch scratches from Equibase's late-changes pages.
Faster than waiting for entries to refresh - this hits the dedicated scratch feed
that Equibase publishes for each track, updated near-real-time."""

import logging
import re
import requests
from bs4 import BeautifulSoup

from config.settings import CANADIAN_TRACKS

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
URL_TEMPLATE = "https://www.equibase.com/static/latechanges/html/latechanges{code}-{country}.html"


def fetch_track_late_changes(track_code):
    """Returns (scratches, reinstated) from the track's late-changes page.

    scratches:  (race_num, program_num, horse_name, reason) for horses whose
                LATEST status is scratched.
    reinstated: (race_num, program_num, horse_name) for horses reported
                scratched and then reversed ("Will Run (Previously Reported
                as scratched)"). Equibase posts follow-up changes as rows
                with no PGM/Horse cells directly under the horse they apply
                to, so rows are replayed in order and the last status wins.
    Returns ([], []) on any error so caller can continue with other tracks."""
    country = "CAN" if track_code in CANADIAN_TRACKS else "USA"
    url = URL_TEMPLATE.format(code=track_code, country=country)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"[SCRATCH FETCH] {track_code}: HTTP {resp.status_code}")
            return [], []
    except Exception as e:
        logger.warning(f"[SCRATCH FETCH] {track_code}: {e}")
        return [], []
    return parse_late_changes(resp.content)


def parse_late_changes(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="fullChanges")
    if not table:
        return [], []

    # (race, pgm) -> {"name", "status": "scratched"|"running"|None, "reason", "was_scratched"}
    horses = {}
    current_race = None
    current_key = None

    for tr in table.find_all("tr"):
        # Race header rows look like: <tr class="group-header">...<th class="race">Race: 2</th>...
        race_th = tr.find("th", class_="race")
        if race_th:
            m = re.search(r"Race:\s*(\d+)", race_th.get_text(strip=True))
            if m:
                current_race = int(m.group(1))
            current_key = None
            continue

        changes_td = tr.find("td", class_="changes")
        if not changes_td or not current_race:
            # Race-level notes (colspan=3, e.g. "Temp Rail ...") end any horse block
            current_key = None
            continue

        pgm_td = tr.find("td", class_="pgm")
        horse_td = tr.find("td", class_="horse")
        if pgm_td and horse_td:
            # Extract program number — text is like "#3"
            pgm_text = pgm_td.get_text(strip=True).lstrip("#").strip()
            # Remove non-digits except A/B suffixes (coupled entries)
            pgm_match = re.match(r"^(\d+[A-Za-z]?)", pgm_text)
            if not pgm_match:
                current_key = None
                continue
            current_key = (current_race, pgm_match.group(1))
            horses.setdefault(current_key, {
                "name": horse_td.get_text(strip=True), "status": None,
                "reason": "", "was_scratched": False,
            })
        elif current_key is None:
            continue  # follow-up row with no horse to attach to

        changes_text = changes_td.get_text(strip=True)
        h = horses[current_key]
        if changes_text.startswith("Scratched"):
            h["status"] = "scratched"
            h["was_scratched"] = True
            h["reason"] = changes_text.replace("Scratched", "").strip(" -")
        elif changes_text.startswith("Will Run"):
            h["status"] = "running"

    scratches, reinstated = [], []
    for (race_num, pgm), h in horses.items():
        if h["status"] == "scratched":
            scratches.append((race_num, pgm, h["name"], h["reason"]))
        elif h["status"] == "running" and h["was_scratched"]:
            reinstated.append((race_num, pgm, h["name"]))
    return scratches, reinstated


def fetch_track_scratches(track_code):
    """Returns list of (race_num, program_num, horse_name, reason) tuples for
    horses currently scratched (reversed scratches excluded)."""
    return fetch_track_late_changes(track_code)[0]


def fetch_and_mark_scratches_for_today():
    """Fetch scratch data for all tracks running today and mark them in DB.
    Returns count of new scratches found."""
    from db.database import get_conn, mark_scratched, mark_unscratched
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

        scratches, reinstated = fetch_track_late_changes(track_code)

        for race_num, program_num, horse_name in reinstated:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT id FROM races WHERE race_date = ? AND track_code = ? AND race_num = ?",
                    (today, track_code, race_num),
                ).fetchone()
            if row and mark_unscratched(row["id"], program_num, source="late_changes",
                                        only_if_source="late_changes"):
                new_scratches += 1
                logger.info(
                    f"[SCRATCH REVERSED] {track_name} R{race_num} #{program_num} "
                    f"{horse_name} — will run"
                )

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

                mark_scratched(race_id, program_num, source="late_changes")
                new_scratches += 1
                logger.info(
                    f"[SCRATCH FROM EQB] {track_name} R{race_num} #{program_num} "
                    f"{horse_name} — {reason}"
                )

    if new_scratches > 0:
        # Touch regen flag so the agent loop refreshes picks + dashboard promptly
        from pathlib import Path
        flag_path = Path.home() / "agents/racing-agent/.regen_now"
        try:
            flag_path.parent.mkdir(parents=True, exist_ok=True)
            flag_path.touch()
        except Exception:
            pass

    logger.info(f"[SCRATCH FETCHER] Found {new_scratches} new scratches across {len(tracks)} tracks")
    return new_scratches
