"""
Form Analyzer
==============
Analyzes horse form using our own historical results database.
As results accumulate over days/weeks, this gets more powerful.

Provides:
  - Last 3 finishes (e.g. "1-3-2")
  - Days since last race
  - Jockey win % from our data
  - Trainer win % from our data
  - Jockey/trainer combo win %
  - Class level changes (rising/dropping)
  - Trainer patterns (hot/cold)
"""

import logging
import sqlite3
from datetime import datetime, date
from config.settings import DB_PATH

logger = logging.getLogger("racing_agent")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_horse_form(horse_name: str, current_date: str = None) -> dict:
    """
    Get last 3 race results for a horse from our database.
    Returns dict with form string, days since last race, etc.
    """
    if not current_date:
        current_date = date.today().isoformat()

    conn = get_conn()
    try:
        # Find races where this horse ran and finished
        rows = conn.execute("""
            SELECT r.race_date, r.track_name, r.race_num, r.conditions,
                   rs.winner_num, rs.winner_name, rs.second_num, rs.third_num,
                   e.program_num, e.morning_line
            FROM entries e
            JOIN races r ON r.id = e.race_id
            LEFT JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.horse_name) = LOWER(?)
              AND r.race_date < ?
              AND rs.winner_name IS NOT NULL
            ORDER BY r.race_date DESC
            LIMIT 3
        """, (horse_name, current_date)).fetchall()

        if not rows:
            return {"form": "---", "days_since": None, "last_3": []}

        form_parts = []
        last_3 = []
        days_since = None

        for i, row in enumerate(rows):
            prog   = str(row["program_num"])
            w_num  = str(row["winner_num"] or "")
            s_num  = str(row["second_num"] or "")
            t_num  = str(row["third_num"] or "")

            if prog == w_num:
                finish = "1"
            elif prog == s_num:
                finish = "2"
            elif prog == t_num:
                finish = "3"
            else:
                finish = "4+"

            form_parts.append(finish)
            last_3.append({
                "date":     row["race_date"],
                "track":    row["track_name"],
                "finish":   finish,
                "conditions": row["conditions"] or "",
            })

            if i == 0:
                try:
                    last_date = datetime.strptime(row["race_date"], "%Y-%m-%d").date()
                    today = datetime.strptime(current_date, "%Y-%m-%d").date()
                    days_since = (today - last_date).days
                except Exception:
                    days_since = None

        form_str = "-".join(form_parts) if form_parts else "---"
        return {
            "form": form_str,
            "days_since": days_since,
            "last_3": last_3,
        }

    except Exception as e:
        logger.warning(f"Form fetch error for {horse_name}: {e}")
        return {"form": "---", "days_since": None, "last_3": []}
    finally:
        conn.close()


def get_jockey_stats_from_db(jockey_name: str) -> dict:
    """Calculate jockey win % from our results database."""
    conn = get_conn()
    try:
        # Count starts and wins
        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
        """, (f"%{jockey_name}%",)).fetchone()["n"]

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
              AND e.program_num = rs.winner_num
        """, (f"%{jockey_name}%",)).fetchone()["n"]

        win_pct = round(wins / starts * 100, 1) if starts >= 5 else None
        return {"starts": starts, "wins": wins, "win_pct": win_pct}

    except Exception:
        return {"starts": 0, "wins": 0, "win_pct": None}
    finally:
        conn.close()


def get_trainer_stats_from_db(trainer_name: str) -> dict:
    """Calculate trainer win % from our results database."""
    conn = get_conn()
    try:
        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
        """, (f"%{trainer_name}%",)).fetchone()["n"]

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
              AND e.program_num = rs.winner_num
        """, (f"%{trainer_name}%",)).fetchone()["n"]

        win_pct = round(wins / starts * 100, 1) if starts >= 5 else None
        return {"starts": starts, "wins": wins, "win_pct": win_pct}

    except Exception:
        return {"starts": 0, "wins": 0, "win_pct": None}
    finally:
        conn.close()


def get_jockey_trainer_combo(jockey: str, trainer: str) -> dict:
    """Calculate jockey+trainer combo win % from our database."""
    conn = get_conn()
    try:
        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
              AND LOWER(e.trainer) LIKE LOWER(?)
        """, (f"%{jockey}%", f"%{trainer}%")).fetchone()["n"]

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
              AND LOWER(e.trainer) LIKE LOWER(?)
              AND e.program_num = rs.winner_num
        """, (f"%{jockey}%", f"%{trainer}%")).fetchone()["n"]

        win_pct = round(wins / starts * 100, 1) if starts >= 5 else None
        return {"starts": starts, "wins": wins, "win_pct": win_pct}

    except Exception:
        return {"starts": 0, "wins": 0, "win_pct": None}
    finally:
        conn.close()


def get_trainer_hot_cold(trainer_name: str, days: int = 14) -> str:
    """
    Check if trainer is hot or cold in last N days.
    Returns: HOT / COLD / NORMAL / UNKNOWN
    """
    conn = get_conn()
    try:
        cutoff = datetime.now().date()
        from datetime import timedelta
        cutoff_str = (cutoff - timedelta(days=days)).isoformat()

        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
              AND r.race_date >= ?
        """, (f"%{trainer_name}%", cutoff_str)).fetchone()["n"]

        if starts < 3:
            return "UNKNOWN"

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
              AND r.race_date >= ?
              AND e.program_num = rs.winner_num
        """, (f"%{trainer_name}%", cutoff_str)).fetchone()["n"]

        win_pct = wins / starts
        if win_pct >= 0.25:
            return "HOT"
        elif win_pct <= 0.08:
            return "COLD"
        return "NORMAL"

    except Exception:
        return "UNKNOWN"
    finally:
        conn.close()


def detect_class_change(current_conditions: str, last_conditions: str) -> str:
    """
    Detect if horse is dropping or rising in class.
    Returns: DROP / RISE / SAME / UNKNOWN
    """
    if not current_conditions or not last_conditions:
        return "UNKNOWN"

    CLASS_ORDER = [
        "maiden claiming",
        "maiden special",
        "claiming",
        "starter",
        "optional",
        "allowance",
        "stakes",
        "grade 3",
        "grade 2",
        "grade 1",
    ]

    def get_class_level(conditions: str) -> int:
        cond = conditions.lower()
        for i, level in enumerate(CLASS_ORDER):
            if level in cond:
                return i
        return 3  # default to claiming level

    current_level = get_class_level(current_conditions)
    last_level    = get_class_level(last_conditions)

    if current_level < last_level:
        return "DROP"    # Dropping in class — positive
    elif current_level > last_level:
        return "RISE"    # Rising in class — harder
    return "SAME"


def get_layoff_flag(days_since: int) -> str:
    """
    Flag horses returning from layoffs.
    Returns: FRESH / SHORT_LAYOFF / LAYOFF / LONG_LAYOFF / UNKNOWN
    """
    if days_since is None:
        return "UNKNOWN"
    if days_since <= 14:
        return "FRESH"
    elif days_since <= 30:
        return "SHORT_LAYOFF"
    elif days_since <= 60:
        return "LAYOFF"
    else:
        return "LONG_LAYOFF"


def get_full_form_analysis(entry: dict, current_conditions: str) -> dict:
    """
    Full form analysis for a single horse entry.
    Returns comprehensive form dict for use in handicapping and display.
    """
    horse   = entry.get("horse_name", "")
    jockey  = entry.get("jockey", "") or ""
    trainer = entry.get("trainer", "") or ""

    # Split jockey/trainer if they're merged (common parsing issue)
    if "Trainer:" in jockey:
        parts = jockey.split("Trainer:")
        jockey  = parts[0].strip()
        trainer = parts[1].strip() if len(parts) > 1 else trainer

    form_data   = get_horse_form(horse)
    j_stats     = get_jockey_stats_from_db(jockey)
    t_stats     = get_trainer_stats_from_db(trainer)
    combo_stats = get_jockey_trainer_combo(jockey, trainer)
    trainer_hot = get_trainer_hot_cold(trainer)
    layoff_flag = get_layoff_flag(form_data.get("days_since"))

    # Class change from last race
    class_change = "UNKNOWN"
    if form_data.get("last_3"):
        last_conditions = form_data["last_3"][0].get("conditions", "")
        class_change = detect_class_change(current_conditions, last_conditions)

    return {
        "horse_name":    horse,
        "jockey":        jockey,
        "trainer":       trainer,
        "form":          form_data.get("form", "---"),
        "days_since":    form_data.get("days_since"),
        "last_3":        form_data.get("last_3", []),
        "layoff_flag":   layoff_flag,
        "class_change":  class_change,
        "j_win_pct":     j_stats.get("win_pct"),
        "j_starts":      j_stats.get("starts", 0),
        "t_win_pct":     t_stats.get("win_pct"),
        "t_starts":      t_stats.get("starts", 0),
        "combo_win_pct": combo_stats.get("win_pct"),
        "combo_starts":  combo_stats.get("starts", 0),
        "trainer_hot":   trainer_hot,
    }


def get_jockey_recent_win_pct(jockey_name: str, days: int = 7) -> dict:
    """Same shape as get_jockey_stats_from_db but filtered to last N days.
    Returns {win_pct: float|None, starts: int, wins: int, days: int}."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_conn()
    try:
        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
              AND r.race_date >= ?
        """, (f"%{jockey_name}%", cutoff)).fetchone()["n"]

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.jockey) LIKE LOWER(?)
              AND r.race_date >= ?
              AND e.program_num = rs.winner_num
        """, (f"%{jockey_name}%", cutoff)).fetchone()["n"]

        win_pct = round(wins / starts * 100, 1) if starts >= 5 else None
        return {"win_pct": win_pct, "starts": starts, "wins": wins, "days": days}
    finally:
        conn.close()


def get_trainer_recent_win_pct(trainer_name: str, days: int = 7) -> dict:
    """Same shape as get_trainer_stats_from_db but filtered to last N days."""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_conn()
    try:
        starts = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
              AND r.race_date >= ?
        """, (f"%{trainer_name}%", cutoff)).fetchone()["n"]

        wins = conn.execute("""
            SELECT COUNT(*) as n FROM entries e
            JOIN races r ON r.id = e.race_id
            JOIN results rs ON rs.race_id = e.race_id
            WHERE LOWER(e.trainer) LIKE LOWER(?)
              AND r.race_date >= ?
              AND e.program_num = rs.winner_num
        """, (f"%{trainer_name}%", cutoff)).fetchone()["n"]

        win_pct = round(wins / starts * 100, 1) if starts >= 5 else None
        return {"win_pct": win_pct, "starts": starts, "wins": wins, "days": days}
    finally:
        conn.close()

