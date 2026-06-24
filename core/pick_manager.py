"""
Pick generation — handicaps today's races and saves agent picks.
Only re-handicaps races that are new, dirty (entries/scratches changed), or need TAINTED_PARSE regen.
"""

import logging
import re
from datetime import datetime, timedelta

import pytz

from db.database import (
    get_conn,
    get_todays_races,
    get_race_entries as db_get_race_entries,
    get_latest_odds_map,
    save_agent_picks,
    save_agent_entry_scores,
    save_agent_race_analysis,
    save_agent_value_bets,
)

logger = logging.getLogger("racing_agent")
EASTERN = pytz.timezone("America/New_York")


def _check_tainted_regen(race_id: int, conn) -> tuple[bool, int, int]:
    """Return (force_regen, old_entry_count, new_active_count)."""
    if conn.execute(
        "SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race_id,)
    ).fetchone():
        return False, 0, 0

    top = conn.execute(
        "SELECT data_quality FROM agent_picks WHERE race_id=? AND rank=1",
        (race_id,),
    ).fetchone()
    if not top or top["data_quality"] != "TAINTED_PARSE":
        return False, 0, 0

    active = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE race_id=? AND scratched=0",
        (race_id,),
    ).fetchone()["n"]
    if active < 4:
        return False, 0, active

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE race_id=?", (race_id,)
    ).fetchone()["n"]
    return True, total, active


def _race_is_frozen(race: dict, force_regen: bool) -> bool:
    """True if race has results or is within 30 min of post time."""
    if force_regen:
        return False

    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race["id"],)
        ).fetchone():
            return True

    post_time = (race.get("post_time") or "").strip()
    race_date = race.get("race_date") or ""
    if not post_time or not race_date:
        return False

    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", post_time, re.IGNORECASE)
    if not match:
        return False

    hour, minute = int(match.group(1)), int(match.group(2))
    ampm = (match.group(3) or "").upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    elif not ampm and hour < 8:
        hour += 12

    now_et = datetime.now(EASTERN)
    post_dt = EASTERN.localize(
        datetime.strptime(race_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
    )
    return now_et >= post_dt - timedelta(minutes=30)


def _entries_changed_since_picks(race_id: int, conn) -> bool:
    """True if entries or scratches updated after the last pick save."""
    last_pick = conn.execute(
        "SELECT MAX(created_ts) AS ts FROM agent_picks WHERE race_id=?",
        (race_id,),
    ).fetchone()["ts"]
    if not last_pick:
        return True

    last_entry = conn.execute(
        "SELECT MAX(fetched_ts) AS ts FROM entries WHERE race_id=?",
        (race_id,),
    ).fetchone()["ts"]
    if last_entry and last_entry > last_pick:
        return True

    scratched = conn.execute(
        "SELECT 1 FROM entries WHERE race_id=? AND scratched=1 "
        "AND scratch_time IS NOT NULL AND scratch_time > ? LIMIT 1",
        (race_id, last_pick),
    ).fetchone()
    return scratched is not None


def _odds_changed_since_picks(race_id: int, conn) -> bool:
    """True if live odds updated after the last pick save."""
    last_pick = conn.execute(
        "SELECT MAX(created_ts) AS ts FROM agent_picks WHERE race_id=?",
        (race_id,),
    ).fetchone()["ts"]
    if not last_pick:
        return True

    last_odds = conn.execute(
        "SELECT MAX(fetched_ts) AS ts FROM odds WHERE race_id=?",
        (race_id,),
    ).fetchone()["ts"]
    return bool(last_odds and last_odds > last_pick)


def _archive_tainted_picks(race_id: int):
    with get_conn() as conn:
        old_picks = conn.execute(
            "SELECT rank, program_num, horse_name, confidence, role "
            "FROM agent_picks WHERE race_id=? ORDER BY rank",
            (race_id,),
        ).fetchall()
        arc_ts = datetime.now().isoformat()
        for op in old_picks:
            conn.execute(
                "INSERT INTO agent_picks_history "
                "(race_id, rank, program_num, horse_name, confidence, "
                "role, rendered_ts, trigger, data_quality) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    race_id, op["rank"], op["program_num"], op["horse_name"],
                    op["confidence"] or "", op["role"] or "", arc_ts,
                    "tainted_parse_superseded", "TAINTED_PARSE",
                ),
            )


def _handicap_and_save(race: dict, force_regen: bool, regen_old_n: int, regen_new_n: int) -> bool:
    from core.handicapper import handicap_race, get_top_pick, role_ranked_picks
    from core.probabilities import scores_to_probabilities
    from core.market import enrich_race_with_market, scan_value_bets

    entries = db_get_race_entries(race["id"])
    entry_dicts = [dict(e) for e in entries]
    scored = handicap_race(
        entry_dicts,
        race["conditions"] or "",
        race["track_code"] or "",
        race["distance"] or "",
    )
    if not scored:
        return False

    active_scored = [s for s in scored if not s.get("scratched")]
    n_active = len(active_scored)
    n_total = len(scored)
    if n_active < 3:
        data_quality = "TAINTED_SCRATCH"
        logger.warning(f"TAINTED_SCRATCH: only {n_active} active of {n_total} total")
    elif n_total < 4:
        data_quality = "TAINTED_PARSE"
        logger.warning(f"TAINTED_PARSE: only {n_total} entries in DB")
    else:
        data_quality = "OK"

    scores_to_probabilities(active_scored, temperature=8.0)
    prob_map = {s["program_num"]: s.get("win_prob", 0.0) for s in active_scored}

    calibrated_map = {}
    try:
        from core.calibrator import IsotonicCalibrator
        cal = IsotonicCalibrator.load("models/calibrator_pick1.json")
        calibrated_map = {pgm: cal.transform(p) for pgm, p in prob_map.items()}
    except Exception as e:
        logger.warning(f"Calibrator unavailable: {e}")

    for h in active_scored:
        pgm = h["program_num"]
        h["calibrated_prob"] = calibrated_map.get(pgm, h.get("win_prob"))

    ml_map = {str(e.get("program_num")): e.get("morning_line") for e in entry_dicts}
    live_odds = get_latest_odds_map(race["id"])
    enrich_race_with_market(active_scored, live_odds=live_odds, ml_map=ml_map)

    value_bets = scan_value_bets(active_scored)
    save_agent_value_bets(race["id"], value_bets)

    top = get_top_pick(scored)
    confidence = top.get("confidence", "LOW") if top else "LOW"
    if scored:
        scored[0]["confidence"] = confidence

    roles = role_ranked_picks(scored)
    prob_by_pgm = {h["program_num"]: h for h in active_scored}
    picks = []
    for i, horse in enumerate(roles["all"]):
        pgm = horse["program_num"]
        enriched = prob_by_pgm.get(pgm, {})
        picks.append({
            "rank": i + 1,
            "program_num": pgm,
            "horse_name": horse["horse_name"],
            "confidence": confidence if i == 0 else "",
            "role": horse.get("role", ""),
            "score": horse.get("score"),
            "win_prob": prob_map.get(pgm),
            "morning_line": ml_map.get(str(pgm)),
            "calibrated_prob": enriched.get("calibrated_prob"),
            "final_prob": enriched.get("final_prob"),
            "market_prob": enriched.get("market_prob"),
            "data_quality": data_quality,
        })

    save_agent_picks(race["id"], picks)
    save_agent_entry_scores(race["id"], scored)
    if scored:
        save_agent_race_analysis(race["id"], scored[0].get("pace_scenario") or {})

    if force_regen:
        logger.info(
            f"Regenerating picks {race['track_code']} R{race['race_num']}: "
            f"was TAINTED_PARSE with {regen_old_n} entries, "
            f"now {regen_new_n} active entries, new dq={data_quality}"
        )

    try:
        with get_conn() as conn:
            ea = conn.execute(
                "SELECT COUNT(*) n, "
                "SUM(CASE WHEN scratched=0 THEN 1 ELSE 0 END) active, "
                "MIN(first_fetched_ts) first_ts, MAX(fetched_ts) last_ts "
                "FROM entries WHERE race_id=?",
                (race["id"],),
            ).fetchone()
        logger.info(
            f"Entry audit {race['track_code']} R{race['race_num']}: "
            f"{ea['n']} entries ({ea['active']} active) | "
            f"first_fetched={(ea['first_ts'] or 'none')[:19]} "
            f"last_fetched={(ea['last_ts'] or 'none')[:19]} | "
            f"picks_created={datetime.now().isoformat()[:19]}"
        )
    except Exception:
        pass

    return True


def save_todays_picks() -> int:
    """Handicap dirty races only. Returns count of races updated."""
    races = get_todays_races()
    saved = 0
    skipped_frozen = 0
    skipped_clean = 0

    for race in races:
        race = dict(race)
        with get_conn() as conn:
            force_regen, regen_old_n, regen_new_n = _check_tainted_regen(race["id"], conn)

        if _race_is_frozen(race, force_regen):
            skipped_frozen += 1
            continue

        if not force_regen:
            with get_conn() as conn:
                entries_dirty = _entries_changed_since_picks(race["id"], conn)
                odds_dirty = _odds_changed_since_picks(race["id"], conn)
                if not entries_dirty and not odds_dirty:
                    skipped_clean += 1
                    continue

        if force_regen:
            _archive_tainted_picks(race["id"])

        try:
            if _handicap_and_save(race, force_regen, regen_old_n, regen_new_n):
                saved += 1
        except Exception as e:
            logger.warning(
                f"Pick save error for {race['track_name']} R{race['race_num']}: {e}"
            )

    logger.info(
        f"Saved role-based picks for {saved} races "
        f"(skipped {skipped_frozen} frozen, {skipped_clean} unchanged)"
    )

    try:
        from core.market import rebuild_actionable_bets_for_date
        today = datetime.now(EASTERN).date().isoformat()
        n_act = rebuild_actionable_bets_for_date(today)
        logger.info(f"Actionable bets rebuilt: {n_act} for {today}")
    except Exception as e:
        logger.warning(f"Actionable bet rebuild failed: {e}")

    return saved
