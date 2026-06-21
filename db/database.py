"""
Racing Agent Database
=====================
SQLite database for storing entries, scratches, odds and picks.
"""

import sqlite3
import logging
from datetime import datetime
import pytz
EASTERN = pytz.timezone("US/Eastern")
from pathlib import Path
from config.settings import DB_PATH

logger = logging.getLogger("racing_agent")


def get_conn():
    Path(DB_PATH).parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS races (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            track_code  TEXT NOT NULL,
            track_name  TEXT NOT NULL,
            race_date   TEXT NOT NULL,
            race_num    INTEGER NOT NULL,
            race_name   TEXT,
            distance    TEXT,
            surface     TEXT,
            purse       TEXT,
            conditions  TEXT,
            post_time   TEXT,
            fetched_ts  TEXT NOT NULL,
            UNIQUE(track_code, race_date, race_num)
        );

        CREATE TABLE IF NOT EXISTS entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id         INTEGER NOT NULL,
            program_num     TEXT NOT NULL,
            horse_name      TEXT NOT NULL,
            jockey          TEXT,
            trainer         TEXT,
            morning_line    TEXT,
            weight          TEXT,
            scratched        INTEGER DEFAULT 0,
            scratch_time     TEXT,
            fetched_ts       TEXT NOT NULL,
            first_fetched_ts TEXT,
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS odds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     INTEGER NOT NULL,
            program_num TEXT NOT NULL,
            horse_name  TEXT NOT NULL,
            odds        TEXT NOT NULL,
            odds_type   TEXT NOT NULL,
            fetched_ts  TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS picks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     INTEGER NOT NULL,
            program_num TEXT NOT NULL,
            horse_name  TEXT NOT NULL,
            bet_type    TEXT NOT NULL,
            confidence  INTEGER,
            notes       TEXT,
            result      TEXT,
            payout      REAL,
            created_ts  TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS jockey_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            jockey      TEXT NOT NULL,
            track_code  TEXT,
            wins        INTEGER DEFAULT 0,
            starts      INTEGER DEFAULT 0,
            win_pct     REAL DEFAULT 0,
            updated_ts  TEXT NOT NULL,
            UNIQUE(jockey, track_code)
        );

        CREATE TABLE IF NOT EXISTS agent_picks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     INTEGER NOT NULL,
            rank        INTEGER NOT NULL,
            program_num TEXT NOT NULL,
            horse_name  TEXT NOT NULL,
            confidence  TEXT,
            role        TEXT,
            result      TEXT,
            created_ts  TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS results (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id              INTEGER NOT NULL,
            winner_num           TEXT NOT NULL,
            winner_name          TEXT NOT NULL,
            winner_win_payout    REAL,
            winner_place_payout  REAL,
            winner_show_payout   REAL,
            second_num           TEXT,
            second_name          TEXT,
            second_place_payout  REAL,
            second_show_payout   REAL,
            third_num            TEXT,
            third_name           TEXT,
            third_show_payout    REAL,
            exacta_payout        REAL,
            trifecta_payout      REAL,
            superfecta_payout    REAL,
            posted_ts            TEXT NOT NULL,
            UNIQUE(race_id),
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS trainer_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trainer     TEXT NOT NULL,
            track_code  TEXT,
            wins        INTEGER DEFAULT 0,
            starts      INTEGER DEFAULT 0,
            win_pct     REAL DEFAULT 0,
            updated_ts  TEXT NOT NULL,
            UNIQUE(trainer, track_code)
        );

        CREATE TABLE IF NOT EXISTS agent_entry_scores (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id      INTEGER NOT NULL,
            program_num  TEXT NOT NULL,
            score        REAL,
            speed_fig    REAL,
            pace_role    TEXT,
            form         TEXT,
            days_since   INTEGER,
            layoff_flag  TEXT,
            class_change TEXT,
            trainer_hot  TEXT,
            value        REAL,
            j_win_pct    REAL,
            t_win_pct    REAL,
            created_ts   TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id),
            UNIQUE(race_id, program_num) ON CONFLICT REPLACE
        );

        CREATE TABLE IF NOT EXISTS agent_race_analysis (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id             INTEGER NOT NULL UNIQUE ON CONFLICT REPLACE,
            pace_scenario_name  TEXT,
            pace_scenario_notes TEXT,
            pace_post_bias      TEXT,
            lone_speed          INTEGER,
            created_ts          TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS agent_value_bets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id      INTEGER NOT NULL,
            program_num  TEXT NOT NULL,
            horse_name   TEXT NOT NULL,
            odds_str     TEXT,
            odds_source  TEXT,
            model_prob   REAL,
            market_prob  REAL,
            final_prob   REAL,
            edge         REAL,
            kelly_f      REAL,
            created_ts   TEXT NOT NULL,
            FOREIGN KEY(race_id) REFERENCES races(id),
            UNIQUE(race_id, program_num) ON CONFLICT REPLACE
        );
        """)
        _migrations = [
            "ALTER TABLE entries ADD COLUMN first_fetched_ts TEXT",
            "ALTER TABLE agent_entry_scores ADD COLUMN win_prob REAL",
            "ALTER TABLE agent_entry_scores ADD COLUMN calibrated_prob REAL",
            "ALTER TABLE agent_entry_scores ADD COLUMN market_prob REAL",
            "ALTER TABLE agent_entry_scores ADD COLUMN final_prob REAL",
            "ALTER TABLE agent_entry_scores ADD COLUMN edge REAL",
            "ALTER TABLE agent_entry_scores ADD COLUMN live_odds TEXT",
            "ALTER TABLE agent_entry_scores ADD COLUMN odds_source TEXT",
            "ALTER TABLE agent_picks ADD COLUMN final_prob REAL",
            "ALTER TABLE agent_picks ADD COLUMN market_prob REAL",
        ]
        for sql in _migrations:
            try:
                conn.execute(sql)
            except Exception:
                pass
        conn.execute(
            "UPDATE entries SET first_fetched_ts = fetched_ts WHERE first_fetched_ts IS NULL"
        )
    logger.info("Racing database initialized")


def save_race(track_code, track_name, race_date, race_num, details={}):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO races
              (track_code, track_name, race_date, race_num,
               race_name, distance, surface, purse, conditions,
               post_time, fetched_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_code, race_date, race_num) DO UPDATE SET
              track_name = excluded.track_name,
              race_name  = excluded.race_name,
              distance   = excluded.distance,
              surface    = excluded.surface,
              purse      = excluded.purse,
              conditions = excluded.conditions,
              post_time  = excluded.post_time,
              fetched_ts = excluded.fetched_ts
            /* RACE_UPSERT_APPLIED */
        """, (
            track_code, track_name, race_date, race_num,
            details.get("race_name"), details.get("distance"),
            details.get("surface"), details.get("purse"),
            details.get("conditions"), details.get("post_time"),
            datetime.now().isoformat()
        ))
        return conn.execute(
            "SELECT id FROM races WHERE track_code=? AND race_date=? AND race_num=?",
            (track_code, race_date, race_num)
        ).fetchone()["id"]


def save_entry(race_id, program_num, horse_name, details={}):
    with get_conn() as conn:
        # Preserve any existing scratched flag set by mark_scratched()
        # (manual scratches must survive entries refreshes from Equibase)
        existing = conn.execute(
            "SELECT scratched, scratch_time FROM entries WHERE race_id=? AND program_num=?",
            (race_id, program_num)
        ).fetchone()
        was_scratched = existing["scratched"] if existing else 0
        existing_scratch_time = existing["scratch_time"] if existing else None

        _now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO entries
              (race_id, program_num, horse_name, jockey, trainer,
               morning_line, weight, fetched_ts, first_fetched_ts, scratched, scratch_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(race_id, program_num) DO UPDATE SET
              horse_name       = excluded.horse_name,
              jockey           = excluded.jockey,
              trainer          = excluded.trainer,
              morning_line     = excluded.morning_line,
              weight           = excluded.weight,
              fetched_ts       = excluded.fetched_ts,
              scratched        = entries.scratched,
              scratch_time     = entries.scratch_time
            /* first_fetched_ts intentionally omitted — frozen on first insert */
        """, (
            race_id, program_num, horse_name,
            details.get("jockey"), details.get("trainer"),
            details.get("morning_line"), details.get("weight"),
            _now, _now,
            was_scratched, existing_scratch_time
        ))


def mark_scratched(race_id, program_num):
    with get_conn() as conn:
        conn.execute("""
            UPDATE entries SET scratched=1, scratch_time=?
            WHERE race_id=? AND program_num=?
        """, (datetime.now().isoformat(), race_id, program_num))
        logger.info(f"Marked #{program_num} scratched in race {race_id}")


def mark_unscratched(race_id, program_num):
    """Clear a false scratch when horse reappears on live entries."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT scratched FROM entries WHERE race_id=? AND program_num=?",
            (race_id, program_num),
        ).fetchone()
        if not row or not row["scratched"]:
            return False
        conn.execute("""
            UPDATE entries SET scratched=0, scratch_time=NULL
            WHERE race_id=? AND program_num=?
        """, (race_id, program_num))
        logger.info(f"Un-scratched #{program_num} in race {race_id} (reappeared on live card)")
        return True


def save_odds(race_id, program_num, horse_name, odds, odds_type="live"):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO odds (race_id, program_num, horse_name, odds, odds_type, fetched_ts)
            VALUES (?,?,?,?,?,?)
        """, (race_id, program_num, horse_name, odds, odds_type, datetime.now().isoformat()))


def get_todays_races():
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.*, COUNT(e.id) as entry_count,
                   SUM(e.scratched) as scratch_count
            FROM races r
            LEFT JOIN entries e ON e.race_id = r.id
            WHERE r.race_date = ?
            GROUP BY r.id
            ORDER BY r.track_name, r.race_num
        """, (today,)).fetchall()


def get_race_entries(race_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT e.*, o.odds as live_odds
            FROM entries e
            LEFT JOIN (
                SELECT o1.program_num, o1.odds
                FROM odds o1
                INNER JOIN (
                    SELECT program_num, MAX(fetched_ts) AS max_ts
                    FROM odds WHERE race_id=? GROUP BY program_num
                ) latest ON o1.program_num = latest.program_num
                    AND o1.fetched_ts = latest.max_ts
                WHERE o1.race_id=?
            ) o ON o.program_num = e.program_num
            WHERE e.race_id=?
            ORDER BY CAST(e.program_num AS INTEGER)
        """, (race_id, race_id, race_id)).fetchall()


def get_latest_odds_map(race_id: int) -> dict:
    """Return {program_num: odds_str} for latest live odds in a race."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT o1.program_num, o1.odds
            FROM odds o1
            INNER JOIN (
                SELECT program_num, MAX(fetched_ts) AS max_ts
                FROM odds WHERE race_id=? GROUP BY program_num
            ) latest ON o1.program_num = latest.program_num
                AND o1.fetched_ts = latest.max_ts
            WHERE o1.race_id=?
        """, (race_id, race_id)).fetchall()
    return {str(r["program_num"]): r["odds"] for r in rows}


def save_result(race_id: int, result_data: dict):
    """Save official race result and auto-grade agent picks."""
    winner_num  = result_data.get("winner_num")
    winner_name = result_data.get("winner_name")
    second_num  = result_data.get("second_num")
    third_num   = result_data.get("third_num")
    win_pay     = result_data.get("winner_win_payout")
    place_pay   = result_data.get("winner_place_payout")
    show_pay    = result_data.get("winner_show_payout")

    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO results
            (race_id, winner_num, winner_name,
             winner_win_payout, winner_place_payout, winner_show_payout,
             second_num, second_name, second_place_payout, second_show_payout,
             third_num, third_name, third_show_payout,
             exacta_payout, trifecta_payout, superfecta_payout,
             daily_double_payout,
             posted_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            race_id, winner_num, winner_name,
            result_data.get("winner_win_payout"),
            result_data.get("winner_place_payout"),
            result_data.get("winner_show_payout"),
            second_num,
            result_data.get("second_name"),
            result_data.get("second_place_payout"),
            result_data.get("second_show_payout"),
            third_num,
            result_data.get("third_name"),
            result_data.get("third_show_payout"),
            result_data.get("exacta", {}).get("payout") if result_data.get("exacta") else None,
            result_data.get("trifecta", {}).get("payout") if result_data.get("trifecta") else None,
            result_data.get("superfecta", {}).get("payout") if result_data.get("superfecta") else None,
            result_data.get("daily_double", {}).get("payout") if result_data.get("daily_double") else None,
            datetime.now().isoformat()
        ))

        # Auto-grade picks for this race
        picks = conn.execute(
            "SELECT id, program_num FROM picks WHERE race_id=? AND result IS NULL",
            (race_id,)
        ).fetchall()

        for pick in picks:
            pn = str(pick["program_num"])
            if pn == str(winner_num):
                grade = "WIN"
                payout = win_pay or 0
            elif pn == str(second_num):
                grade = "PLACE"
                payout = place_pay or 0
            elif pn == str(third_num):
                grade = "SHOW"
                payout = show_pay or 0
            else:
                grade = "LOSS"
                payout = 0
            conn.execute(
                "UPDATE picks SET result=?, payout=? WHERE id=?",
                (grade, payout, pick["id"])
            )


def get_todays_results():
    """Get all results posted today."""
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        return conn.execute("""
            SELECT rs.*, r.track_name, r.race_num
            FROM results rs
            JOIN races r ON r.id = rs.race_id
            WHERE r.race_date = ?
            ORDER BY r.track_name, r.race_num
        """, (today,)).fetchall()


def save_agent_picks(race_id: int, picks: list):
    """
    Save agent's top 3 picks for a race. FREEZE_GUARD_APPLIED.

    Behavior:
    - If race has results in `results` table, the live agent_picks row is
      FROZEN: this function will NOT modify agent_picks. It still logs to
      agent_picks_history for forensic record.
    - Pre-race: continues DELETE-then-INSERT into agent_picks so scratches
      and updated form trigger re-handicapping. Every save also appends to
      agent_picks_history with trigger='agent_save'.
    """
    now_iso = datetime.now().isoformat()

    with get_conn() as conn:
        # FREEZE CHECK — frozen if results posted OR post time has passed
        race_done = conn.execute(
            "SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race_id,)
        ).fetchone() is not None

        # POST_TIME_FREEZE: also freeze once post time has passed
        # Prevents picks from changing after the race has started
        if not race_done:
            try:
                import pytz
                from datetime import date as _date
                _et = pytz.timezone("America/New_York")
                _now_et = datetime.now(_et)
                _race_row = conn.execute(
                    "SELECT post_time, race_date FROM races WHERE id=?",
                    (race_id,)
                ).fetchone()
                if _race_row and _race_row["post_time"] and _race_row["race_date"]:
                    _pt = _race_row["post_time"].strip()  # e.g. "2:14 PM" or "14:14"
                    _rd = _race_row["race_date"]  # YYYY-MM-DD
                    # Parse post_time — handle both 12h and 24h formats
                    import re as _re
                    _m = _re.match(
                        r"(\d{1,2}):(\d{2})\s*(AM|PM)?", _pt, _re.IGNORECASE
                    )
                    if _m:
                        _hr, _min = int(_m.group(1)), int(_m.group(2))
                        _ampm = (_m.group(3) or "").upper()
                        if _ampm == "PM" and _hr != 12:
                            _hr += 12
                        elif _ampm == "AM" and _hr == 12:
                            _hr = 0
                        elif not _ampm and _hr < 8:
                            _hr += 12  # no AM/PM stored; times < 8 are PM (no US racing at 1-7 AM)
                        from datetime import datetime as _dt
                        _post_dt = _et.localize(
                            _dt.strptime(_rd, "%Y-%m-%d").replace(
                                hour=_hr, minute=_min
                            )
                        )
                        from datetime import timedelta as _td
                        _freeze_dt = _post_dt - _td(minutes=30)
                        if _now_et >= _freeze_dt:
                            race_done = True  # POST_TIME_FREEZE 30min
            except Exception as _pte:
                pass  # if post time parse fails, don't freeze

        # Always log to history (audit trail; never deleted)
        for pick in picks:
            conn.execute(
                "INSERT INTO agent_picks_history "
                "(race_id, rank, program_num, horse_name, confidence, role, "
                "rendered_ts, trigger) VALUES (?,?,?,?,?,?,?,?)",
                (
                    race_id,
                    pick.get("rank", 1),
                    str(pick.get("program_num", "")),
                    pick.get("horse_name", ""),
                    pick.get("confidence", ""),
                    pick.get("role", ""),
                    now_iso,
                    "agent_save_frozen" if race_done else "agent_save",
                ),
            )

        if race_done:
            # Race is over: do NOT modify agent_picks (FREEZE)
            return

        # Pre-race: DELETE-then-INSERT live picks (scratches still apply)
        conn.execute("DELETE FROM agent_picks WHERE race_id=?", (race_id,))

        for pick in picks:
            conn.execute("""
                INSERT INTO agent_picks
                (race_id, rank, program_num, horse_name, confidence, role,
                 created_ts, score, win_prob, morning_line, calibrated_prob,
                 final_prob, market_prob, data_quality)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                race_id,
                pick.get("rank", 1),
                str(pick.get("program_num", "")),
                pick.get("horse_name", ""),
                pick.get("confidence", ""),
                pick.get("role", ""),
                now_iso,
                pick.get("score"),
                pick.get("win_prob"),
                pick.get("morning_line"),
                pick.get("calibrated_prob"),
                pick.get("final_prob"),
                pick.get("market_prob"),
                pick.get("data_quality", "OK"),
            ))


def save_agent_entry_scores(race_id: int, scored: list):
    """Persist score_horse() output for all active entries.
    Written alongside save_agent_picks() — skipped automatically when freeze fires."""
    if not scored:
        return
    now_iso = datetime.now().isoformat()
    with get_conn() as conn:
        for h in scored:
            conn.execute("""
                INSERT INTO agent_entry_scores
                (race_id, program_num, score, speed_fig, pace_role, form,
                 days_since, layoff_flag, class_change, trainer_hot, value,
                 j_win_pct, t_win_pct, win_prob, calibrated_prob, market_prob,
                 final_prob, edge, live_odds, odds_source, created_ts)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                race_id,
                str(h.get("program_num", "")),
                h.get("score"),
                h.get("speed_fig"),
                h.get("pace_role", ""),
                h.get("form"),
                h.get("days_since"),
                h.get("layoff_flag", ""),
                h.get("class_change", ""),
                h.get("trainer_hot", ""),
                h.get("value"),
                h.get("j_win_pct_db"),
                h.get("t_win_pct_db"),
                h.get("win_prob"),
                h.get("calibrated_prob"),
                h.get("market_prob"),
                h.get("final_prob"),
                h.get("edge"),
                h.get("odds_str"),
                h.get("odds_source", ""),
                now_iso,
            ))


def save_agent_value_bets(race_id: int, bets: list):
    """Persist positive-edge runners for a race."""
    if not bets:
        with get_conn() as conn:
            conn.execute("DELETE FROM agent_value_bets WHERE race_id=?", (race_id,))
        return
    now_iso = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM agent_value_bets WHERE race_id=?", (race_id,))
        for h in bets:
            conn.execute("""
                INSERT INTO agent_value_bets
                (race_id, program_num, horse_name, odds_str, odds_source,
                 model_prob, market_prob, final_prob, edge, kelly_f, created_ts)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                race_id,
                str(h.get("program_num", "")),
                h.get("horse_name", ""),
                h.get("odds_str"),
                h.get("odds_source", ""),
                h.get("calibrated_prob") or h.get("win_prob"),
                h.get("market_prob"),
                h.get("final_prob"),
                h.get("edge"),
                h.get("kelly_f"),
                now_iso,
            ))


def get_todays_value_bets() -> list:
    """All positive-edge bets for today's card."""
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT avb.*, r.track_name, r.race_num, r.post_time, r.track_code
            FROM agent_value_bets avb
            JOIN races r ON r.id = avb.race_id
            LEFT JOIN entries e ON e.race_id = avb.race_id
                AND e.program_num = avb.program_num
            WHERE r.race_date = ?
              AND (e.scratched IS NULL OR e.scratched = 0)
            ORDER BY avb.edge DESC
        """, (today,)).fetchall()
    return [dict(r) for r in rows]


def get_track_high_win_rate_14d() -> dict:
    """Return {track_name: win_pct} for HIGH confidence rank-1 picks, last 14 days."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT r.track_name,
                   COUNT(*) AS n,
                   SUM(CASE WHEN ap.result = 'WIN'
                            AND ap.program_num = res.winner_num THEN 1 ELSE 0 END) AS wins
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            LEFT JOIN results res ON res.race_id = ap.race_id
            WHERE ap.rank = 1
              AND ap.confidence = 'HIGH'
              AND ap.result IS NOT NULL AND ap.result != ''
              AND r.race_date >= date('now', '-14 days')
            GROUP BY r.track_name
            HAVING n >= 3
        """).fetchall()
    return {
        r["track_name"]: round(100.0 * r["wins"] / r["n"], 1)
        for r in rows
    }


def save_agent_race_analysis(race_id: int, pace_scenario: dict):
    """Persist race-level pace scenario. Written alongside save_agent_picks()."""
    if not pace_scenario:
        return
    now_iso = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO agent_race_analysis
            (race_id, pace_scenario_name, pace_scenario_notes,
             pace_post_bias, lone_speed, created_ts)
            VALUES (?,?,?,?,?,?)
        """, (
            race_id,
            pace_scenario.get("scenario", ""),
            pace_scenario.get("notes", ""),
            pace_scenario.get("post_bias", ""),
            1 if pace_scenario.get("lone_speed") else 0,
            now_iso,
        ))


def get_todays_entry_scores() -> dict:
    """Return {race_id: {program_num: score_dict}} for today's races."""
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT aes.*
            FROM agent_entry_scores aes
            JOIN races r ON r.id = aes.race_id
            WHERE r.race_date = ?
        """, (today,)).fetchall()
    result = {}
    for r in rows:
        rid = r["race_id"]
        if rid not in result:
            result[rid] = {}
        result[rid][r["program_num"]] = dict(r)
    return result


def get_todays_race_analyses() -> dict:
    """Return {race_id: analysis_dict} for today's races."""
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ara.*
            FROM agent_race_analysis ara
            JOIN races r ON r.id = ara.race_id
            WHERE r.race_date = ?
        """, (today,)).fetchall()
    return {r["race_id"]: dict(r) for r in rows}


def grade_agent_picks(race_id: int, result_data: dict):
    """
    Grade agent picks against actual result. RANK_ORDER_GRADING_APPLIED.

    Sets BOTH:
      - result: WIN / PLACE / SHOW / MISS  (legacy text label)
      - finish_position: 1 / 2 / 3 / NULL  (rank-order; NULL = not in top 3)

    The rank-order data enables Bolton-Chapman style analysis: every race
    becomes 3 independent observations instead of 1 (Chapman & Staelin 1982
    explosion process).
    """
    winner_num = str(result_data.get("winner_num", "") or "")
    second_num = str(result_data.get("second_num", "") or "")
    third_num  = str(result_data.get("third_num", "") or "")

    with get_conn() as conn:
        picks = conn.execute(
            "SELECT id, program_num FROM agent_picks WHERE race_id=? AND result IS NULL",
            (race_id,)
        ).fetchall()

        for pick in picks:
            pn = str(pick["program_num"])
            if pn == winner_num:
                grade, pos = "WIN", 1
            elif pn == second_num:
                grade, pos = "PLACE", 2
            elif pn == third_num:
                grade, pos = "SHOW", 3
            else:
                grade, pos = "MISS", None
            conn.execute(
                "UPDATE agent_picks SET result=?, finish_position=? WHERE id=?",
                (grade, pos, pick["id"])
            )


def get_agent_pick_stats() -> dict:
    """
    Calculate comprehensive WPS stats for agent picks.
    Returns stats broken down by pick rank and confidence.
    """
    conn = get_conn()
    try:
        # Total graded picks
        total = conn.execute(
            "SELECT COUNT(*) as n FROM agent_picks WHERE result IS NOT NULL"
        ).fetchone()["n"]

        if total == 0:
            return {
                "total_races": 0,
                "top_pick_win_pct": 0,
                "top_pick_wps_pct": 0,
                "any_pick_wps_pct": 0,
                "exacta_pct": 0,
                "by_rank": {},
                "by_confidence": {},
                "recent": []
            }

        # Stats by rank
        by_rank = {}
        for rank in [1, 2, 3]:
            rows = conn.execute("""
                SELECT result, COUNT(*) as n
                FROM agent_picks
                WHERE rank=? AND result IS NOT NULL
                GROUP BY result
            """, (rank,)).fetchall()

            total_rank = sum(r["n"] for r in rows)
            wins   = next((r["n"] for r in rows if r["result"]=="WIN"),   0)
            places = next((r["n"] for r in rows if r["result"]=="PLACE"), 0)
            shows  = next((r["n"] for r in rows if r["result"]=="SHOW"),  0)
            misses = next((r["n"] for r in rows if r["result"]=="MISS"),  0)

            if total_rank > 0:
                by_rank[rank] = {
                    "total":     total_rank,
                    "wins":      wins,
                    "places":    places,
                    "shows":     shows,
                    "misses":    misses,
                    "win_pct":   round(wins / total_rank * 100, 1),
                    "wps_pct":   round((wins+places+shows) / total_rank * 100, 1),
                }

        # Stats by confidence level
        by_conf = {}
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            rows = conn.execute("""
                SELECT result, COUNT(*) as n
                FROM agent_picks
                WHERE rank=1 AND confidence=? AND result IS NOT NULL
                GROUP BY result
            """, (conf,)).fetchall()

            total_conf = sum(r["n"] for r in rows)
            wins   = next((r["n"] for r in rows if r["result"]=="WIN"),   0)
            places = next((r["n"] for r in rows if r["result"]=="PLACE"), 0)
            shows  = next((r["n"] for r in rows if r["result"]=="SHOW"),  0)

            if total_conf > 0:
                by_conf[conf] = {
                    "total":   total_conf,
                    "wins":    wins,
                    "wps_pct": round((wins+places+shows) / total_conf * 100, 1),
                    "win_pct": round(wins / total_conf * 100, 1),
                }

        # Any of top 3 picks in WPS
        total_races = conn.execute("""
            SELECT COUNT(DISTINCT race_id) as n
            FROM agent_picks WHERE result IS NOT NULL
        """).fetchone()["n"]

        races_with_wps = conn.execute("""
            SELECT COUNT(DISTINCT race_id) as n
            FROM agent_picks
            WHERE result IN ('WIN','PLACE','SHOW')
        """).fetchone()["n"]

        # Exacta hits (top 2 picks = 1st and 2nd finishers)
        exacta_hits = conn.execute("""
            SELECT COUNT(DISTINCT a1.race_id) as n
            FROM agent_picks a1
            JOIN agent_picks a2 ON a2.race_id = a1.race_id
            WHERE a1.rank=1 AND a1.result='WIN'
              AND a2.rank=2 AND a2.result='PLACE'
        """).fetchone()["n"]

        # Top pick win/WPS
        top_total = by_rank.get(1, {}).get("total", 0)
        top_wins  = by_rank.get(1, {}).get("wins", 0)
        top_wps   = by_rank.get(1, {}).get("wins", 0) + by_rank.get(1, {}).get("places", 0) + by_rank.get(1, {}).get("shows", 0)

        # Recent results (last 10 graded races)
        recent = conn.execute("""
            SELECT ap.race_id, ap.rank, ap.horse_name, ap.confidence,
                   ap.result, r.track_name, r.race_num, r.race_date
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            WHERE ap.rank=1 AND ap.result IS NOT NULL
            ORDER BY r.race_date DESC, r.race_num DESC
            LIMIT 10
        """).fetchall()

        return {
            "total_races":      total_races,
            "top_pick_win_pct": round(top_wins / top_total * 100, 1) if top_total else 0,
            "top_pick_wps_pct": round(top_wps  / top_total * 100, 1) if top_total else 0,
            "any_pick_wps_pct": round(races_with_wps / total_races * 100, 1) if total_races else 0,
            "exacta_pct":       round(exacta_hits / total_races * 100, 1) if total_races else 0,
            "by_rank":          by_rank,
            "by_confidence":    by_conf,
            "recent":           [dict(r) for r in recent],
        }

    except Exception as e:
        logger.warning(f"Pick stats error: {e}")
        return {"total_races": 0, "top_pick_win_pct": 0, "top_pick_wps_pct": 0,
                "any_pick_wps_pct": 0, "exacta_pct": 0, "by_rank": {}, "by_confidence": {}, "recent": []}
    finally:
        conn.close()


def get_roi_stats(bet_amount: float = 0.50) -> dict:
    """
    Calculate actual ROI betting $0.50 ATB on each of top 3 picks.
    Uses DISTINCT race_id to avoid cartesian product inflation.
    """
    conn = get_conn()
    try:
        scale = bet_amount / 2.0

        # Get all unique races where we have picks AND results
        races = conn.execute("""
            SELECT DISTINCT rs.race_id
            FROM results rs
            JOIN agent_picks ap ON ap.race_id = rs.race_id
            WHERE rs.winner_num IS NOT NULL
        """).fetchall()

        total_races = len(races)
        if total_races == 0:
            return {"total_races":0,"total_wagered":0,"total_returned":0,
                    "net_profit":0,"roi_pct":0,"win_hits":0,"place_hits":0,
                    "show_hits":0,"by_bet_type":{},"by_confidence":{},
                    "by_rank":{},"recent_races":[],"exacta_box":{},"trifecta_box":{}}

        total_wagered  = total_races * bet_amount * 3 * 3  # 3 picks x 3 bets
        total_returned = 0.0
        win_hits = place_hits = show_hits = 0
        win_returned = place_returned = show_returned = 0.0
        by_rank = {1:{"wagered":0,"returned":0,"races":0,"win_hits":0,"place_hits":0,"show_hits":0},
                   2:{"wagered":0,"returned":0,"races":0,"win_hits":0,"place_hits":0,"show_hits":0},
                   3:{"wagered":0,"returned":0,"races":0,"win_hits":0,"place_hits":0,"show_hits":0}}
        by_conf = {"HIGH":{"wagered":0,"returned":0,"races":0},
                   "MEDIUM":{"wagered":0,"returned":0,"races":0},
                   "LOW":{"wagered":0,"returned":0,"races":0}}
        exacta_hits = exacta_returned = 0.0
        trifecta_hits = trifecta_returned = 0.0
        recent_races = []

        for race_row in races:
            rid = race_row["race_id"]

            # Get result
            rs = conn.execute("""
                SELECT winner_num, second_num, third_num,
                       winner_win_payout, winner_place_payout, winner_show_payout,
                       second_place_payout, second_show_payout, third_show_payout,
                       exacta_payout, trifecta_payout
                FROM results WHERE race_id=?
            """, (rid,)).fetchone()
            if not rs:
                continue

            w = str(rs["winner_num"] or "")
            p = str(rs["second_num"] or "")
            t = str(rs["third_num"] or "")

            # Get top 3 picks (one of each rank)
            picks = conn.execute("""
                SELECT rank, program_num, confidence
                FROM agent_picks
                WHERE race_id=? AND rank IN (1,2,3)
                GROUP BY rank
                HAVING id = MIN(id)
            """, (rid,)).fetchall()

            if len(picks) < 1:
                continue

            pick_map = {p["rank"]: str(p["program_num"]) for p in picks}
            pick_nums = set(pick_map.values())
            conf = next((p["confidence"] for p in picks if p["rank"]==1), "LOW") or "LOW"

            race_wagered  = bet_amount * 3 * len(picks)
            race_returned = 0.0

            for pk in picks:
                rank = pk["rank"]
                prog = str(pk["program_num"])
                by_rank[rank]["races"]   += 1
                by_rank[rank]["wagered"] += bet_amount * 3

                ret = 0.0
                if prog == w:
                    # WIN + PLACE + SHOW
                    wp = (rs["winner_win_payout"] or 0) * scale
                    pp = (rs["winner_place_payout"] or 0) * scale
                    sp = (rs["winner_show_payout"] or 0) * scale
                    ret = wp + pp + sp
                    if wp: win_hits += 1; win_returned += wp; by_rank[rank]["win_hits"] += 1
                    if pp: place_hits += 1; place_returned += pp; by_rank[rank]["place_hits"] += 1
                    if sp: show_hits += 1; show_returned += sp; by_rank[rank]["show_hits"] += 1
                elif prog == p:
                    # PLACE + SHOW
                    pp = (rs["second_place_payout"] or 0) * scale
                    sp = (rs["second_show_payout"] or 0) * scale
                    ret = pp + sp
                    if pp: place_hits += 1; place_returned += pp; by_rank[rank]["place_hits"] += 1
                    if sp: show_hits += 1; show_returned += sp; by_rank[rank]["show_hits"] += 1
                elif prog == t:
                    # SHOW only
                    sp = (rs["third_show_payout"] or 0) * scale
                    ret = sp
                    if sp: show_hits += 1; show_returned += sp; by_rank[rank]["show_hits"] += 1

                by_rank[rank]["returned"] += ret
                race_returned += ret

            total_returned += race_returned

            # Confidence tracking (rank 1 only)
            if conf in by_conf:
                by_conf[conf]["wagered"]  += bet_amount * 3
                by_conf[conf]["returned"] += next((by_rank[r]["returned"] for r in [1] if r in by_rank), 0)
                by_conf[conf]["races"]    += 1

            # Exacta box
            if rs["exacta_payout"] and w in pick_nums and p in pick_nums and w != p:
                exacta_hits += 1
                exacta_returned += (rs["exacta_payout"] / 2.0) * bet_amount

            # Trifecta box
            if rs["trifecta_payout"] and w in pick_nums and p in pick_nums and t in pick_nums:
                if len({w,p,t}) == 3:
                    trifecta_hits += 1
                    trifecta_returned += (rs["trifecta_payout"] / 6.0) * bet_amount

            # Recent races
            rinfo = conn.execute(
                "SELECT track_name, race_num, race_date FROM races WHERE id=?", (rid,)
            ).fetchone()
            if rinfo:
                net = race_returned - race_wagered
                recent_races.append({
                    "date":     rinfo["race_date"],
                    "track":    rinfo["track_name"],
                    "race_num": rinfo["race_num"],
                    "wagered":  round(race_wagered, 2),
                    "returned": round(race_returned, 2),
                    "profit":   round(net, 2),
                })

        # Calculate ROI per rank
        for rank in by_rank:
            d = by_rank[rank]
            if d["wagered"] > 0:
                d["roi_pct"]    = round((d["returned"]-d["wagered"])/d["wagered"]*100, 1)
                d["net_profit"] = round(d["returned"]-d["wagered"], 2)
            else:
                d["roi_pct"] = 0; d["net_profit"] = 0

        # Confidence ROI
        for conf in by_conf:
            d = by_conf[conf]
            if d["wagered"] > 0:
                d["roi_pct"]    = round((d["returned"]-d["wagered"])/d["wagered"]*100, 1)
                d["net_profit"] = round(d["returned"]-d["wagered"], 2)
            else:
                d["roi_pct"] = 0; d["net_profit"] = 0

        net_profit = total_returned - total_wagered
        roi_pct    = round(net_profit/total_wagered*100, 1) if total_wagered else 0

        ex_wagered  = total_races * bet_amount * 6
        ex_net      = exacta_returned - ex_wagered
        tri_wagered = total_races * bet_amount * 6
        tri_net     = trifecta_returned - tri_wagered

        recent_races.sort(key=lambda x: (x["date"], x["race_num"]), reverse=True)

        return {
            "bet_amount":     bet_amount,
            "total_races":    total_races,
            "total_wagered":  round(total_wagered, 2),
            "total_returned": round(total_returned, 2),
            "net_profit":     round(net_profit, 2),
            "roi_pct":        roi_pct,
            "win_hits":       win_hits,
            "place_hits":     place_hits,
            "show_hits":      show_hits,
            "by_bet_type": {
                "win":   {"hits":win_hits,   "returned":round(win_returned,2)},
                "place": {"hits":place_hits, "returned":round(place_returned,2)},
                "show":  {"hits":show_hits,  "returned":round(show_returned,2)},
            },
            "by_confidence": by_conf,
            "by_rank":       by_rank,
            "recent_races":  recent_races[:20],
            "exacta_box": {
                "wagered":       round(ex_wagered, 2),
                "returned":      round(exacta_returned, 2),
                "net_profit":    round(ex_net, 2),
                "roi_pct":       round(ex_net/ex_wagered*100,1) if ex_wagered else 0,
                "hits":          int(exacta_hits),
                "combos":        6,
                "cost_per_race": round(bet_amount*6, 2),
            },
            "trifecta_box": {
                "wagered":       round(tri_wagered, 2),
                "returned":      round(trifecta_returned, 2),
                "net_profit":    round(tri_net, 2),
                "roi_pct":       round(tri_net/tri_wagered*100,1) if tri_wagered else 0,
                "hits":          int(trifecta_hits),
                "combos":        6,
                "cost_per_race": round(bet_amount*6, 2),
            }
        }

    except Exception as e:
        logger.warning(f"ROI stats error: {e}")
        import traceback; traceback.print_exc()
        return {"total_races":0,"total_wagered":0,"total_returned":0,
                "net_profit":0,"roi_pct":0,"win_hits":0,"place_hits":0,
                "show_hits":0,"by_bet_type":{},"by_confidence":{},"by_rank":{},
                "recent_races":[],"exacta_box":{},"trifecta_box":{}}
    finally:
        conn.close()


def get_optimized_roi_stats(bet_high: float = 2.00, bet_med_pl: float = 0.50,
                              bet_med_sh: float = 0.50, bet_low_sh: float = 0.50,
                              exacta_bet: float = 0.50) -> dict:
    """
    Calculate ROI using the optimized betting strategy:
    - HIGH CONF:   $2.00 WIN on Pick #1 only
    - MEDIUM CONF: $0.50 PLACE + $0.50 SHOW on Pick #1 only
    - LOW CONF:    $0.50 SHOW on Pick #1 only
    - Exacta box:  $0.50 x 6 combos = $3.00/race (all 3 picks)
    - Pick #2 and #3: informational only, no ATB bet
    """
    conn = get_conn()
    try:
        scale = 1.0 / 2.0  # Equibase payouts per $2

        races = conn.execute("""
            SELECT DISTINCT rs.race_id
            FROM results rs
            JOIN agent_picks ap ON ap.race_id = rs.race_id
            WHERE rs.winner_num IS NOT NULL
              AND ap.rank = 1
        """).fetchall()

        total_races   = len(races)
        if total_races == 0:
            return {"total_races": 0, "total_wagered": 0, "total_returned": 0,
                    "net_profit": 0, "roi_pct": 0, "by_confidence": {},
                    "exacta": {}, "recent_races": []}

        total_wagered  = 0.0
        total_returned = 0.0
        exacta_hits    = 0
        exacta_returned = 0.0

        by_conf = {
            "HIGH":   {"races":0,"wagered":0,"returned":0,"win_hits":0},
            "MEDIUM": {"races":0,"wagered":0,"returned":0,"place_hits":0,"show_hits":0},
            "LOW":    {"races":0,"wagered":0,"returned":0,"show_hits":0},
        }
        recent_races = []

        for race_row in races:
            rid = race_row["race_id"]

            rs = conn.execute("""
                SELECT winner_num, second_num, third_num,
                       winner_win_payout, winner_place_payout, winner_show_payout,
                       second_place_payout, second_show_payout, third_show_payout,
                       exacta_payout
                FROM results WHERE race_id=?
            """, (rid,)).fetchone()
            if not rs:
                continue

            w = str(rs["winner_num"] or "")
            p = str(rs["second_num"] or "")
            t = str(rs["third_num"] or "")

            # Get Pick #1
            pk1 = conn.execute("""
                SELECT program_num, confidence FROM agent_picks
                WHERE race_id=? AND rank=1
                GROUP BY rank HAVING id=MIN(id)
            """, (rid,)).fetchone()
            if not pk1:
                continue

            prog = str(pk1["program_num"])
            conf = (pk1["confidence"] or "LOW").upper()
            if conf not in by_conf:
                conf = "LOW"

            # Determine bet amount and type by confidence
            race_wagered  = 0.0
            race_returned = 0.0

            if conf == "HIGH":
                race_wagered = bet_high
                if prog == w and rs["winner_win_payout"]:
                    ret = rs["winner_win_payout"] * (bet_high / 2.0)
                    race_returned += ret
                    by_conf["HIGH"]["win_hits"] += 1

            elif conf == "MEDIUM":
                race_wagered = bet_med_pl + bet_med_sh
                if prog == w:
                    if rs["winner_place_payout"]:
                        race_returned += rs["winner_place_payout"] * (bet_med_pl / 2.0)
                        by_conf["MEDIUM"]["place_hits"] += 1
                    if rs["winner_show_payout"]:
                        race_returned += rs["winner_show_payout"] * (bet_med_sh / 2.0)
                        by_conf["MEDIUM"]["show_hits"] += 1
                elif prog == p:
                    if rs["second_place_payout"]:
                        race_returned += rs["second_place_payout"] * (bet_med_pl / 2.0)
                        by_conf["MEDIUM"]["place_hits"] += 1
                    if rs["second_show_payout"]:
                        race_returned += rs["second_show_payout"] * (bet_med_sh / 2.0)
                        by_conf["MEDIUM"]["show_hits"] += 1
                elif prog == t:
                    if rs["third_show_payout"]:
                        race_returned += rs["third_show_payout"] * (bet_med_sh / 2.0)
                        by_conf["MEDIUM"]["show_hits"] += 1

            else:  # LOW
                race_wagered = bet_low_sh
                if prog == w and rs["winner_show_payout"]:
                    race_returned += rs["winner_show_payout"] * (bet_low_sh / 2.0)
                    by_conf["LOW"]["show_hits"] += 1
                elif prog == p and rs["second_show_payout"]:
                    race_returned += rs["second_show_payout"] * (bet_low_sh / 2.0)
                    by_conf["LOW"]["show_hits"] += 1
                elif prog == t and rs["third_show_payout"]:
                    race_returned += rs["third_show_payout"] * (bet_low_sh / 2.0)
                    by_conf["LOW"]["show_hits"] += 1

            by_conf[conf]["races"]    += 1
            by_conf[conf]["wagered"]  += race_wagered
            by_conf[conf]["returned"] += race_returned

            # Exacta box on all 3 picks
            picks_query = conn.execute("""
                SELECT program_num FROM agent_picks
                WHERE race_id=? AND rank IN (1,2,3)
                GROUP BY rank HAVING id=MIN(id)
            """, (rid,)).fetchall()
            pick_nums = {str(pk["program_num"]) for pk in picks_query}
            ex_race_wagered = exacta_bet * 6
            ex_race_returned = 0.0

            if rs["exacta_payout"] and w in pick_nums and p in pick_nums and w != p:
                exacta_hits += 1
                ex_race_returned = (rs["exacta_payout"] / 2.0) * exacta_bet
                exacta_returned += ex_race_returned

            total_wagered  += race_wagered + ex_race_wagered
            total_returned += race_returned + ex_race_returned

            # Recent
            rinfo = conn.execute(
                "SELECT track_name, race_num, race_date FROM races WHERE id=?", (rid,)
            ).fetchone()
            if rinfo:
                race_total_wagered = race_wagered + ex_race_wagered
                race_total_returned = race_returned + ex_race_returned
                recent_races.append({
                    "date":     rinfo["race_date"],
                    "track":    rinfo["track_name"],
                    "race_num": rinfo["race_num"],
                    "conf":     conf,
                    "wagered":  round(race_total_wagered, 2),
                    "returned": round(race_total_returned, 2),
                    "profit":   round(race_total_returned - race_total_wagered, 2),
                })

        # ROI per confidence
        for c in by_conf:
            d = by_conf[c]
            if d["wagered"] > 0:
                d["roi_pct"]    = round((d["returned"]-d["wagered"])/d["wagered"]*100, 1)
                d["net_profit"] = round(d["returned"]-d["wagered"], 2)
            else:
                d["roi_pct"] = 0
                d["net_profit"] = 0

        net_profit = total_returned - total_wagered
        roi_pct    = round(net_profit/total_wagered*100, 1) if total_wagered else 0
        ex_wagered = total_races * exacta_bet * 6
        ex_net     = exacta_returned - ex_wagered

        recent_races.sort(key=lambda x:(x["date"],x["race_num"]), reverse=True)

        return {
            "total_races":    total_races,
            "total_wagered":  round(total_wagered, 2),
            "total_returned": round(total_returned, 2),
            "net_profit":     round(net_profit, 2),
            "roi_pct":        roi_pct,
            "by_confidence":  by_conf,
            "exacta": {
                "wagered":    round(ex_wagered, 2),
                "returned":   round(exacta_returned, 2),
                "net_profit": round(ex_net, 2),
                "roi_pct":    round(ex_net/ex_wagered*100,1) if ex_wagered else 0,
                "hits":       exacta_hits,
            },
            "recent_races": recent_races[:20],
        }
    except Exception as e:
        logger.warning(f"Optimized ROI error: {e}")
        return {"total_races":0,"total_wagered":0,"total_returned":0,"net_profit":0,"roi_pct":0,"by_confidence":{},"exacta":{},"recent_races":[]}
    finally:
        conn.close()


def get_todays_agent_picks():
    """Get all agent picks for today with their grades."""
    today = datetime.now(EASTERN).date().isoformat()
    with get_conn() as conn:
        return conn.execute("""
            SELECT ap.*, r.track_name, r.race_num, r.race_date
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            WHERE r.race_date = ?
            ORDER BY r.track_name, r.race_num, ap.rank
        """, (today,)).fetchall()


def save_pick(race_id, program_num, horse_name, bet_type, confidence=None, notes=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO picks (race_id, program_num, horse_name, bet_type,
                               confidence, notes, created_ts)
            VALUES (?,?,?,?,?,?,?)
        """, (race_id, program_num, horse_name, bet_type,
              confidence, notes, datetime.now().isoformat()))




def get_stats_by_track() -> dict:
    """Win rate and ROI breakdown by track."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT r.track_name,
                   COUNT(DISTINCT r.id) as races,
                   SUM(CASE WHEN ap.rank=1 AND ap.result='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN ap.rank=1 AND ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps
            FROM races r
            JOIN agent_picks ap ON ap.race_id = r.id
            WHERE ap.result IS NOT NULL AND ap.rank = 1
            GROUP BY r.track_name
            ORDER BY races DESC
        """).fetchall()

        result = {}
        for row in rows:
            races = row["races"]
            if races == 0:
                continue
            result[row["track_name"]] = {
                "races": races,
                "wins": row["wins"],
                "wps": row["wps"],
                "win_pct": round(row["wins"] / races * 100, 1),
                "wps_pct": round(row["wps"] / races * 100, 1),
            }
        return result
    except Exception as e:
        logger.warning(f"Stats by track error: {e}")
        return {}
    finally:
        conn.close()


def get_stats_by_field_size() -> dict:
    """Win rate breakdown by field size buckets."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN ec.cnt <= 5 THEN 'Small (2-5)'
                    WHEN ec.cnt <= 8 THEN 'Medium (6-8)'
                    ELSE 'Large (9+)'
                END as bucket,
                COUNT(DISTINCT r.id) as races,
                SUM(CASE WHEN ap.rank=1 AND ap.result='WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN ap.rank=1 AND ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps,
                ROUND(AVG(ec.cnt), 1) as avg_field
            FROM races r
            JOIN agent_picks ap ON ap.race_id = r.id
            JOIN (
                SELECT race_id, COUNT(*) as cnt
                FROM entries WHERE scratched = 0
                GROUP BY race_id
            ) ec ON ec.race_id = r.id
            WHERE ap.result IS NOT NULL AND ap.rank = 1
            GROUP BY bucket
            ORDER BY avg_field
        """).fetchall()

        result = {}
        for row in rows:
            races = row["races"]
            if races == 0:
                continue
            result[row["bucket"]] = {
                "races": races,
                "wins": row["wins"],
                "wps": row["wps"],
                "win_pct": round(row["wins"] / races * 100, 1),
                "wps_pct": round(row["wps"] / races * 100, 1),
                "avg_field": row["avg_field"],
            }
        return result
    except Exception as e:
        logger.warning(f"Stats by field size error: {e}")
        return {}
    finally:
        conn.close()



def get_track_roi_by_confidence() -> dict:
    """ROI by track + confidence tier for Pick #1."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT r.track_name, ap.confidence,
                   COUNT(*) as races,
                   SUM(CASE WHEN ap.result='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps,
                   SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) as win_returns
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            LEFT JOIN results res ON res.race_id = ap.race_id
            WHERE ap.rank=1 AND ap.result IS NOT NULL
            GROUP BY r.track_name, ap.confidence
            ORDER BY r.track_name, ap.confidence
        """).fetchall()
        result = {}
        for row in rows:
            track = row["track_name"]
            conf = row["confidence"] or "NONE"
            if track not in result:
                result[track] = {}
            races = row["races"]
            wagered = races * 2.00
            returned = row["win_returns"] or 0
            roi = ((returned - wagered) / wagered * 100) if wagered else 0
            result[track][conf] = {
                "races": races, "wins": row["wins"], "wps": row["wps"],
                "win_pct": round(row["wins"]/races*100, 1),
                "wps_pct": round(row["wps"]/races*100, 1),
                "wagered": wagered, "returned": returned,
                "roi_pct": round(roi, 1),
            }
        return result
    except Exception as e:
        logger.warning(f"Track ROI error: {e}")
        return {}
    finally:
        conn.close()



def save_chart_time(race_data, race_id=None):
    import json
    from datetime import datetime as _dt
    with get_conn() as conn:
        fracs = json.dumps(race_data.get("fractional_times_sec", []))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO chart_times (race_id,track_code,race_date,race_num,distance_text,distance_yards,surface,track_condition,final_time_sec,fractional_times,weather,temp_f,purse,claiming_price,run_up_feet,class_type,fetched_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (race_id, race_data.get("track_code"), race_data.get("race_date"), race_data.get("race_num"), race_data.get("distance_text"), race_data.get("distance_yards"), race_data.get("surface"), race_data.get("track_condition"), race_data.get("final_time_sec"), fracs, race_data.get("weather"), race_data.get("temp_f"), race_data.get("purse"), race_data.get("claiming_price"), race_data.get("run_up_feet"), race_data.get("class_type"), _dt.now().isoformat()))
        except Exception as e:
            logger.warning(f"save_chart_time error: {e}")

def get_chart_times_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM chart_times").fetchone()[0]

def get_track_par(track_code, distance_yards, surface="Dirt", condition="Fast", min_races=5):
    import statistics
    with get_conn() as conn:
        rows = conn.execute("SELECT final_time_sec FROM chart_times WHERE track_code=? AND distance_yards=? AND surface=? AND track_condition=? AND final_time_sec IS NOT NULL ORDER BY race_date DESC LIMIT 50", (track_code, distance_yards, surface, condition)).fetchall()
        if len(rows) < min_races:
            rows = conn.execute("SELECT final_time_sec FROM chart_times WHERE distance_yards=? AND surface=? AND track_condition=? AND final_time_sec IS NOT NULL ORDER BY race_date DESC LIMIT 100", (distance_yards, surface, condition)).fetchall()
        if len(rows) < min_races:
            return None
        times = [r["final_time_sec"] for r in rows]
        return {"avg_time": round(statistics.mean(times), 2), "race_count": len(times), "std_dev": round(statistics.stdev(times), 2) if len(times) > 1 else 0, "track_code": track_code, "distance_yards": distance_yards, "surface": surface, "condition": condition}


def get_horse_speed_figure(horse_name, track_code=None, limit=3):
    """Look up best recent speed figure for a horse from chart data.
    Checks races where this horse ran (as winner or finisher)."""
    from data.speed_calc import compute_speed_figure
    with get_conn() as conn:
        # Find races where this horse was the winner
        rows = conn.execute(
            "SELECT ct.final_time_sec, ct.distance_yards "
            "FROM results res "
            "JOIN chart_times ct ON ct.race_id = res.race_id "
            "WHERE res.winner_name LIKE ? AND ct.final_time_sec IS NOT NULL "
            "ORDER BY ct.race_date DESC LIMIT ?",
            (horse_name + "%", limit)
        ).fetchall()
        # Also check races where horse ran (entries) and we have chart data
        if not rows:
            rows = conn.execute(
                "SELECT ct.final_time_sec, ct.distance_yards "
                "FROM entries e "
                "JOIN chart_times ct ON ct.race_id = e.race_id "
                "WHERE e.horse_name LIKE ? AND ct.final_time_sec IS NOT NULL "
                "ORDER BY ct.race_date DESC LIMIT ?",
                (horse_name + "%", limit)
            ).fetchall()
        # Fallback: match by track_code + race_date + race_num
        if not rows:
            rows = conn.execute(
                "SELECT ct.final_time_sec, ct.distance_yards "
                "FROM entries e "
                "JOIN races r ON r.id = e.race_id "
                "JOIN chart_times ct ON ct.track_code = r.track_code AND ct.race_date = r.race_date AND ct.race_num = r.race_num "
                "WHERE e.horse_name LIKE ? AND ct.final_time_sec IS NOT NULL "
                "ORDER BY ct.race_date DESC LIMIT ?",
                (horse_name + "%", limit)
            ).fetchall()
        if not rows:
            return None
        figures = []
        for r in rows:
            fig = compute_speed_figure(r["final_time_sec"], r["distance_yards"])
            if fig:
                figures.append(fig)
        if not figures:
            return None
        return max(figures)



def get_exacta_track_stats(min_races=10):
    """Get exacta box ROI by track for dashboard display.
    Filters excluded tracks. Only returns NYRA Bets eligible tracks."""
    try:
        from config.settings import EXCLUDED_TRACKS
    except Exception:
        EXCLUDED_TRACKS = []

    with get_conn() as conn:
        tracks = conn.execute(
            "SELECT DISTINCT r.track_name, r.track_code FROM races r "
            "JOIN results res ON res.race_id = r.id "
            "WHERE res.winner_num IS NOT NULL "
            "GROUP BY r.track_name HAVING COUNT(*) >= ?",
            (min_races,)
        ).fetchall()
        results = []
        for t in tracks:
            track_name = t["track_name"]
            # Skip excluded tracks
            if track_name in EXCLUDED_TRACKS:
                continue
            races = conn.execute(
                "SELECT r.id, res.winner_num, res.second_num, res.exacta_payout "
                "FROM races r JOIN results res ON res.race_id = r.id "
                "WHERE r.track_name = ? AND res.winner_num IS NOT NULL "
                "AND res.second_num IS NOT NULL",
                (track_name,)
            ).fetchall()
            total = hits = 0
            wagered = returned = 0.0
            for race in races:
                picks = conn.execute(
                    "SELECT program_num FROM agent_picks "
                    "WHERE race_id=? AND rank<=3 "
                    "AND data_quality IN ('OK','UNVERIFIED') "
                    "ORDER BY rank",
                    (race["id"],)
                ).fetchall()
                if len(picks) < 2:
                    continue
                pick_nums = [str(p["program_num"]) for p in picks]
                total += 1
                wagered += 6.0
                if (str(race["winner_num"]) in pick_nums and
                        str(race["second_num"]) in pick_nums):
                    hits += 1
                    if race["exacta_payout"]:
                        returned += race["exacta_payout"] / 2.0
            if total >= min_races:
                net = returned - wagered
                roi = net / wagered * 100 if wagered else 0
                hit_pct = hits / total * 100
                avg_ret = returned / hits if hits else 0
                # Tighter threshold: positive ROI + hit rate > 20% + avg payout > $8
                worthy = roi > 0 and hit_pct > 20 and avg_ret > 8
                results.append({
                    "track": track_name, "races": total, "hits": hits,
                    "hit_pct": round(hit_pct, 1), "wagered": round(wagered, 2),
                    "returned": round(returned, 2), "roi": round(roi, 1),
                    "avg_per_hit": round(avg_ret, 2), "exacta_worthy": worthy
                })
        results.sort(key=lambda x: x["roi"], reverse=True)
        return results




def get_jt_combo_stats(jockey, trainer):
    """Get win% for a specific jockey-trainer combination."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN res.winner_name = e.horse_name THEN 1 ELSE 0 END) as wins "
            "FROM entries e "
            "JOIN races r ON r.id = e.race_id "
            "JOIN results res ON res.race_id = r.id "
            "WHERE e.jockey LIKE ? AND e.trainer LIKE ? AND e.scratched = 0",
            (jockey.strip() + "%", trainer.strip() + "%")
        ).fetchone()
        if rows and rows["total"] and rows["total"] >= 3:
            return {"starts": rows["total"], "wins": rows["wins"],
                    "win_pct": round(rows["wins"] / rows["total"] * 100, 1)}
        return None




def get_post_position_bias(track_code, min_races=20):
    """Get win% by post position for a track to detect bias."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT e.post_position, COUNT(*) as starts, "
            "SUM(CASE WHEN res.winner_num = e.program_num THEN 1 ELSE 0 END) as wins "
            "FROM entries e "
            "JOIN races r ON r.id = e.race_id "
            "JOIN results res ON res.race_id = r.id "
            "WHERE r.track_code = ? AND e.scratched = 0 AND e.post_position IS NOT NULL "
            "GROUP BY e.post_position "
            "HAVING COUNT(*) >= 5 "
            "ORDER BY CAST(e.post_position AS INTEGER)",
            (track_code,)
        ).fetchall()
        total_starts = sum(r["starts"] for r in rows) if rows else 0
        total_wins = sum(r["wins"] for r in rows) if rows else 0
        if total_starts < min_races:
            return None
        avg_win_pct = total_wins / total_starts * 100 if total_starts else 0
        bias = []
        for r in rows:
            pct = r["wins"] / r["starts"] * 100 if r["starts"] else 0
            edge = pct - avg_win_pct
            bias.append({
                "post": r["post_position"], "starts": r["starts"],
                "wins": r["wins"], "win_pct": round(pct, 1), "edge": round(edge, 1)
            })
        # Determine bias direction
        inside_pct = sum(b["wins"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) <= 3)
        inside_starts = sum(b["starts"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) <= 3)
        outside_pct = sum(b["wins"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) >= 6)
        outside_starts = sum(b["starts"] for b in bias if int(str(b["post"]).replace("A","").replace("B","") or 0) >= 6)
        inside_wp = inside_pct / inside_starts * 100 if inside_starts else 0
        outside_wp = outside_pct / outside_starts * 100 if outside_starts else 0
        if inside_wp > outside_wp + 5:
            direction = "INSIDE"
        elif outside_wp > inside_wp + 5:
            direction = "OUTSIDE"
        else:
            direction = "NEUTRAL"
        return {"bias": direction, "inside_wp": round(inside_wp, 1),
                "outside_wp": round(outside_wp, 1), "positions": bias}




def get_lone_speed_stats():
    """Get win stats when Pick #1 has LONE_SPEED pace scenario."""
    with get_conn() as conn:
        # Count wins where pace was LONE_SPEED
        total = conn.execute(
            "SELECT COUNT(*) FROM agent_picks ap "
            "WHERE ap.rank = 1 AND ap.result IS NOT NULL"
        ).fetchone()[0]
        # We don't store pace scenario per pick yet, so return overall stats
        return {"total_graded": total}




def get_dd_track_stats(min_dds=5):
    """Get Daily Double ROI by track for dashboard."""
    with get_conn() as conn:
        track_dates = conn.execute(
            "SELECT DISTINCT r.track_name, r.track_code, r.race_date "
            "FROM races r JOIN results res ON res.race_id = r.id "
            "WHERE res.winner_num IS NOT NULL "
            "ORDER BY r.race_date"
        ).fetchall()

        by_track = {}
        for td in track_dates:
            tn = td["track_name"]
            tc = td["track_code"]
            rd = td["race_date"]
            races = conn.execute(
                "SELECT r.id, r.race_num, res.winner_num, res.winner_win_payout "
                "FROM races r JOIN results res ON res.race_id = r.id "
                "WHERE r.track_code=? AND r.race_date=? AND res.winner_num IS NOT NULL "
                "ORDER BY r.race_num", (tc, rd)
            ).fetchall()
            if len(races) < 2:
                continue
            for i in range(len(races) - 1):
                r1, r2 = races[i], races[i + 1]
                if r2["race_num"] != r1["race_num"] + 1:
                    continue
                p1 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r1["id"],)
                ).fetchone()
                p2 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r2["id"],)
                ).fetchone()
                if not p1 or not p2:
                    continue
                if tn not in by_track:
                    by_track[tn] = {"dds": 0, "hits": 0, "wagered": 0, "returned": 0}
                by_track[tn]["dds"] += 1
                by_track[tn]["wagered"] += 1.0
                if p1["result"] == "WIN" and p2["result"] == "WIN":
                    by_track[tn]["hits"] += 1
                    w1 = r1["winner_win_payout"] or 0
                    w2 = r2["winner_win_payout"] or 0
                    if w1 > 0 and w2 > 0:
                        est = round((w1/2) * (w2/2) * 2 * 1.10, 2)
                        by_track[tn]["returned"] += est

        results = []
        for t, d in by_track.items():
            if d["dds"] >= min_dds:
                net = d["returned"] - d["wagered"]
                roi = net / d["wagered"] * 100 if d["wagered"] else 0
                hit_pct = d["hits"] / d["dds"] * 100
                avg_ret = d["returned"] / d["hits"] if d["hits"] else 0
                worthy = roi > 0
                results.append({
                    "track": t, "dds": d["dds"], "hits": d["hits"],
                    "hit_pct": round(hit_pct, 1), "wagered": d["wagered"],
                    "returned": round(d["returned"], 2), "roi": round(roi, 1),
                    "avg_per_hit": round(avg_ret, 2), "dd_worthy": worthy
                })
        results.sort(key=lambda x: x["roi"], reverse=True)
        return results



def get_dd_track_stats_measured(min_dds=5):
    """Daily Double ROI by track using REAL measured payouts from results.daily_double_payout.
    Same shape as get_dd_track_stats. Skips DDs where measured payout is missing."""
    with get_conn() as conn:
        track_dates = conn.execute(
            "SELECT DISTINCT r.track_name, r.track_code, r.race_date "
            "FROM races r JOIN results res ON res.race_id = r.id "
            "WHERE res.winner_num IS NOT NULL "
            "ORDER BY r.race_date"
        ).fetchall()

        by_track = {}
        for td in track_dates:
            tn = td["track_name"]
            tc = td["track_code"]
            rd = td["race_date"]
            races = conn.execute(
                "SELECT r.id, r.race_num, res.winner_num, res.daily_double_payout "
                "FROM races r JOIN results res ON res.race_id = r.id "
                "WHERE r.track_code=? AND r.race_date=? AND res.winner_num IS NOT NULL "
                "ORDER BY r.race_num", (tc, rd)
            ).fetchall()
            if len(races) < 2:
                continue
            for i in range(len(races) - 1):
                r1, r2 = races[i], races[i + 1]
                if r2["race_num"] != r1["race_num"] + 1:
                    continue
                # Need a measured payout on the SECOND leg's row
                dd_pay = r2["daily_double_payout"]
                if dd_pay is None:
                    continue
                p1 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r1["id"],)
                ).fetchone()
                p2 = conn.execute(
                    "SELECT program_num, result FROM agent_picks WHERE race_id=? AND rank=1",
                    (r2["id"],)
                ).fetchone()
                if not p1 or not p2:
                    continue
                if tn not in by_track:
                    by_track[tn] = {"dds": 0, "hits": 0, "wagered": 0, "returned": 0}
                by_track[tn]["dds"] += 1
                by_track[tn]["wagered"] += 1.0
                if p1["result"] == "WIN" and p2["result"] == "WIN":
                    by_track[tn]["hits"] += 1
                    # $1 DD bet returns dd_pay/2 (since $2 base unit pays dd_pay)
                    by_track[tn]["returned"] += dd_pay / 2.0

        results = []
        for t, d in by_track.items():
            if d["dds"] >= min_dds:
                net = d["returned"] - d["wagered"]
                roi = net / d["wagered"] * 100 if d["wagered"] else 0
                hit_pct = d["hits"] / d["dds"] * 100
                avg_ret = d["returned"] / d["hits"] if d["hits"] else 0
                worthy = roi > 0
                results.append({
                    "track": t, "dds": d["dds"], "hits": d["hits"],
                    "hit_pct": round(hit_pct, 1), "wagered": d["wagered"],
                    "returned": round(d["returned"], 2), "roi": round(roi, 1),
                    "avg_per_hit": round(avg_ret, 2), "dd_worthy": worthy,
                    "source": "measured"
                })
        results.sort(key=lambda x: x["roi"], reverse=True)
        return results


def get_dd_track_stats_hybrid(min_dds_measured=10, min_dds_modeled=5):
    """Returns DD stats per track. Uses MEASURED data when track has >= min_dds_measured 
    real DD payouts; falls back to MODELED estimate (existing logic) otherwise.
    Each row tagged with 'source' = 'measured' or 'modeled'.
    Excludes tracks not available on NYRA Bets."""
    try:
        from config.settings import EXCLUDED_TRACKS
    except Exception:
        EXCLUDED_TRACKS = []

    measured = get_dd_track_stats_measured(min_dds=min_dds_measured)
    measured = [m for m in measured if m["track"] not in EXCLUDED_TRACKS]
    measured_tracks = {m["track"] for m in measured}

    modeled_full = get_dd_track_stats(min_dds=min_dds_modeled)
    modeled_filtered = [m for m in modeled_full
                        if m["track"] not in measured_tracks
                        and m["track"] not in EXCLUDED_TRACKS]
    for m in modeled_filtered:
        m["source"] = "modeled"

    combined = measured + modeled_filtered
    combined.sort(key=lambda x: (x["source"] != "measured", -x["roi"]))
    return combined



def get_dd_spot_checks(limit=20):
    """Return recent measured DDs alongside the modeled prediction for each.
    Used by dashboard to show modeled-vs-measured drift over time."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                r.track_name,
                r.race_date,
                r.race_num,
                res1.winner_win_payout AS w1,
                res2.winner_win_payout AS w2,
                res2.daily_double_payout AS measured_pay,
                res2.posted_ts
            FROM races r
            JOIN results res2 ON res2.race_id = r.id
            JOIN races r1 ON r1.track_code = r.track_code 
                          AND r1.race_date = r.race_date 
                          AND r1.race_num = r.race_num - 1
            JOIN results res1 ON res1.race_id = r1.id
            WHERE res2.daily_double_payout IS NOT NULL
              AND res1.winner_win_payout IS NOT NULL
              AND res2.winner_win_payout IS NOT NULL
            ORDER BY res2.posted_ts DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        results = []
        for row in rows:
            w1 = row["w1"] or 0
            w2 = row["w2"] or 0
            # Correct formula: implied probs from $2 win payouts, 80% payout rate
            if w1 > 0 and w2 > 0:
                _p1 = 2.0 / w1  # implied win prob from $2 payout
                _p2 = 2.0 / w2
                modeled = round((1.0 / (_p1 * _p2)) * 0.80, 2)  # $1 DD with takeout
            else:
                modeled = 0
            measured = row["measured_pay"] or 0
            diff_pct = round(100 * (measured - modeled) / modeled, 1) if modeled > 0 else 0
            results.append({
                "track": row["track_name"],
                "date": row["race_date"],
                "leg2_race": row["race_num"],
                "w1": w1,
                "w2": w2,
                "modeled": modeled,
                "measured": measured,
                "diff_pct": diff_pct,
            })
        return results



def get_todays_bet_slate():
    """Return today's actionable bets: HIGH/MEDIUM CONF Pick #1 at profitable tracks.
    Reads from agent_picks_history (latest snapshot per race) since agent_picks
    is populated nightly retrospectively. Falls back to agent_picks if history empty."""
    from datetime import datetime
    import pytz
    EASTERN = pytz.timezone("US/Eastern")
    today = datetime.now(EASTERN).date().isoformat()
    
    with get_conn() as conn:
        # Try history table first (live data during racing hours)
        rows = conn.execute("""
            WITH latest_picks AS (
                SELECT 
                    aph.race_id,
                    aph.program_num,
                    aph.horse_name,
                    aph.confidence,
                    aph.rendered_ts,
                    ap.calibrated_prob,
                    ap.final_prob,
                    ap.market_prob,
                    ap.morning_line,
                    ap2.win_prob AS rank2_prob,
                    ROW_NUMBER() OVER (
                        PARTITION BY aph.race_id 
                        ORDER BY aph.rendered_ts DESC
                    ) AS rn
                FROM agent_picks_history aph
                JOIN races r ON aph.race_id = r.id
                LEFT JOIN agent_picks ap ON ap.race_id = aph.race_id
                    AND ap.program_num = aph.program_num
                    AND ap.rank = 1
                LEFT JOIN agent_picks ap2 ON ap2.race_id = aph.race_id
                    AND ap2.rank = 2
                WHERE r.race_date = ?
                  AND aph.rank = 1
                  AND 1=1  /* HISTORY_REENABLED */
                  AND NOT EXISTS (
                      SELECT 1 FROM entries e
                      WHERE e.race_id = aph.race_id
                        AND e.program_num = aph.program_num
                        AND e.scratched = 1
                  )
            )
            SELECT 
                r.id AS race_id,
                r.track_name,
                r.race_num,
                r.post_time,
                lp.program_num,
                lp.horse_name,
                lp.confidence,
                lp.calibrated_prob,
                lp.final_prob,
                lp.market_prob,
                lp.morning_line,
                res.winner_num,
                CASE WHEN res.winner_num = lp.program_num THEN 'WIN'
                     WHEN res.second_num = lp.program_num THEN 'PLACE'
                     WHEN res.third_num = lp.program_num THEN 'SHOW'
                     WHEN res.winner_num IS NOT NULL THEN 'MISS'
                     ELSE NULL END AS result_status
            FROM latest_picks lp
            JOIN races r ON lp.race_id = r.id
            LEFT JOIN results res ON res.race_id = r.id
            WHERE lp.rn = 1
              AND lp.confidence IN ('HIGH', 'MEDIUM')
            ORDER BY r.track_name, r.race_num
        """, (today,)).fetchall()
        
        # Fallback: if history empty, use agent_picks (works for past dates, not today)
        if not rows:
            rows = conn.execute("""
                SELECT 
                    r.id AS race_id,
                    r.track_name,
                    r.race_num,
                    r.post_time,
                    ap.program_num,
                    ap.horse_name,
                    ap.confidence,
                    ap.calibrated_prob,
                    ap.final_prob,
                    ap.market_prob,
                    ap.morning_line,
                    ap2.win_prob AS rank2_prob,
                    res.winner_num,
                    CASE WHEN res.winner_num = ap.program_num THEN 'WIN'
                         WHEN res.second_num = ap.program_num THEN 'PLACE'
                         WHEN res.third_num = ap.program_num THEN 'SHOW'
                         WHEN res.winner_num IS NOT NULL THEN 'MISS'
                         ELSE NULL END AS result_status
                FROM agent_picks ap
                JOIN races r ON ap.race_id = r.id
                LEFT JOIN agent_picks ap2 ON ap2.race_id = ap.race_id
                    AND ap2.rank = 2
                LEFT JOIN results res ON res.race_id = r.id
                WHERE r.race_date = ?
                  AND ap.rank = 1
                  AND ap.confidence IN ('HIGH', 'MEDIUM')
                  AND NOT EXISTS (
                      SELECT 1 FROM entries e
                      WHERE e.race_id = ap.race_id
                        AND e.program_num = ap.program_num
                        AND e.scratched = 1
                  )
                ORDER BY r.track_name, r.race_num
            """, (today,)).fetchall()
        
        # Build profitable-track set from historical Pick #1 ROI
        track_stats = conn.execute("""
            SELECT 
                r.track_name,
                COUNT(*) AS races,
                SUM(CASE WHEN ap.result='WIN' AND ap.program_num=res.winner_num 
                         THEN res.winner_win_payout ELSE 0 END) AS total_returned,
                SUM(CASE WHEN ap.result IS NOT NULL THEN 1 ELSE 0 END) AS graded
            FROM agent_picks ap
            JOIN races r ON ap.race_id = r.id
            LEFT JOIN results res ON res.race_id = r.id
            WHERE ap.rank = 1
              AND ap.result IS NOT NULL
              AND ap.result != ''
            GROUP BY r.track_name
            HAVING graded >= 3  /* BASELINE_RELAXED */
        """).fetchall()
        
        profitable_tracks = set()
        track_roi_map = {}
        for ts in track_stats:
            wagered = ts["graded"] * 2.0
            roi = (ts["total_returned"] - wagered) / wagered * 100 if wagered else 0
            track_roi_map[ts["track_name"]] = round(roi, 1)
            if roi > 0:
                profitable_tracks.add(ts["track_name"])
        
        # Build slate, filtering to profitable tracks
        slate = []
        for r in rows:
            # BASELINE_RELAXED: show all tracks during baseline building
            # Re-enable profitable_tracks filter after 300+ HIGH CONF graded
            # if r["track_name"] not in profitable_tracks:
            #     continue
            
            conf = r["confidence"]
            if conf == "HIGH":
                bet_type = "$2 WIN"
                stake = 2.00
            elif conf == "MEDIUM":
                bet_type = "$0.50 PL+SH"
                stake = 1.00
            else:
                continue
            
            # Sort key: convert post_time like "2:14" to comparable string "0214"
            pt = r["post_time"] or ""
            try:
                if ":" in pt:
                    h, m = pt.split(":")
                    h_int = int(h)
                    # Assume PM if hour < 12 (most US racing is PM)
                    if h_int < 12:
                        h_int += 12
                    sortable = f"{h_int:02d}{int(m):02d}"
                else:
                    sortable = "9999"
            except (ValueError, AttributeError):
                sortable = "9999"
            
            status = r["result_status"]
            if status is None:
                status_display = "upcoming"
            elif status == "WIN":
                status_display = "WON"
            elif status == "MISS":
                status_display = "lost"
            else:
                status_display = status.lower()
            
            slate.append({
                "race_id": r["race_id"],
                "track": r["track_name"],
                "race_num": r["race_num"],
                "post_time": pt,
                "post_time_sortable": sortable,
                "program_num": r["program_num"],
                "horse_name": r["horse_name"],
                "confidence": conf,
                "bet_type": bet_type,
                "stake": stake,
                "track_roi": track_roi_map.get(r["track_name"], 0.0),
                "status": status_display,
                "calibrated_prob": r["calibrated_prob"] if "calibrated_prob" in r.keys() else None,
                "final_prob": r["final_prob"] if "final_prob" in r.keys() else None,
                "market_prob": r["market_prob"] if "market_prob" in r.keys() else None,
                "morning_line": r["morning_line"] if "morning_line" in r.keys() else None,
                "rank2_prob": r["rank2_prob"] if "rank2_prob" in r.keys() else None,
            })
        
        # Sort: upcoming first by post time ascending, then completed by post time descending
        upcoming = [s for s in slate if s["status"] == "upcoming"]
        completed = [s for s in slate if s["status"] != "upcoming"]
        upcoming.sort(key=lambda x: x["post_time_sortable"])
        completed.sort(key=lambda x: x["post_time_sortable"], reverse=True)
        return upcoming + completed


def get_pick_record():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as n FROM picks WHERE result IS NOT NULL").fetchone()["n"]
        wins  = conn.execute("SELECT COUNT(*) as n FROM picks WHERE result='WIN'").fetchone()["n"]
        roi   = conn.execute("SELECT COALESCE(SUM(payout),0) as t FROM picks").fetchone()["t"]
        return {"total": total, "wins": wins, "win_pct": round(wins/total*100,1) if total else 0, "roi": round(roi,2)}
