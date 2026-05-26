"""Pick 3 / Pick 4 sequence picker.

Strategy summary:
- Empirical sequence detection: identify which Pick 3/4 windows each track
  actually offers (from historical pick_payouts data).
- Top-2 per leg: each leg uses the top 2 horses by base score (from Phase 2A
  top2_picks). Combos = 2^N (8 for Pick 3, 16 for Pick 4) × $0.50 base.
- Filter C: no LOW CONF legs allowed.
- Bolton-Chapman: each leg's combined top-2 probability must be >= MIN_PROBABILITY
  (0.10), and the full sequence EV must exceed cost.
- EV estimation: track-average historical payout (from pick_payouts).

Designed to be called by the agent during save_todays_picks() OR manually
via tools for ad-hoc analysis.
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy imports done inside functions to avoid circular dependencies
ROOT = Path(__file__).parent.parent

PICK3_COST = 8 * 0.50    # $0.50 × 2^3 combos = $4.00
PICK4_COST = 16 * 0.50   # $0.50 × 2^4 combos = $8.00

# Minimum historical payout records before we trust the track average
MIN_PAYOUT_HISTORY = 5


def _get_conn():
    from db.database import get_conn
    return get_conn()


def detect_track_sequences(track_code: str, lookback_days: int = 90) -> dict:
    """Empirically detect which Pick 3 / Pick 4 windows a track offers.

    Looks at pick_payouts records over the last N days and identifies which
    starting race numbers had Pick 3 / Pick 4 payouts posted.

    Returns dict like:
      {"PICK3": [5, 7], "PICK4": [3, 7]}  # starting race numbers
    """
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    out = {"PICK3": set(), "PICK4": set()}
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT pp.bet_type, r.race_num, COUNT(*) AS n
            FROM pick_payouts pp
            JOIN races r ON r.id = pp.race_id
            WHERE r.track_code = ? AND r.race_date >= ?
              AND pp.bet_type IN ('PICK3', 'PICK4')
            GROUP BY pp.bet_type, r.race_num
            HAVING n >= 2
        """, (track_code, cutoff)).fetchall()
    for row in rows:
        if row["bet_type"] in out:
            out[row["bet_type"]].add(int(row["race_num"]))
    return {k: sorted(v) for k, v in out.items()}


def track_avg_payout(track_code: str, bet_type: str,
                     lookback_days: int = 90) -> tuple:
    """Average historical payout for this bet type at this track.

    Returns (avg_payout, n_records). If n_records < MIN_PAYOUT_HISTORY,
    avg_payout is None.
    """
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    with _get_conn() as conn:
        row = conn.execute("""
            SELECT AVG(pp.payout) AS avg, COUNT(*) AS n
            FROM pick_payouts pp
            JOIN races r ON r.id = pp.race_id
            WHERE r.track_code = ? AND pp.bet_type = ? AND r.race_date >= ?
        """, (track_code, bet_type, cutoff)).fetchone()
    if not row or row["n"] < MIN_PAYOUT_HISTORY:
        return None, (row["n"] if row else 0)
    return float(row["avg"]), int(row["n"])


def _get_top2_for_race(race_id: int):
    """Fetch the agent's top 2 picks for a race (from agent_picks)."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT program_num, horse_name, confidence,
                   calibrated_prob, win_prob, morning_line
            FROM agent_picks
            WHERE race_id = ? AND rank <= 2
            ORDER BY rank
        """, (race_id,)).fetchall()
    return [dict(r) for r in rows]


def _race_id_for(track_code: str, race_date: str, race_num: int):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM races WHERE track_code=? AND race_date=? AND race_num=?",
            (track_code, race_date, race_num),
        ).fetchone()
    return row["id"] if row else None


def build_sequence_legs(track_code: str, race_date: str,
                        start_race: int, n_legs: int):
    """Pull the top-2 picks for each of n_legs consecutive races.

    Returns list of leg dicts, or None if any leg is missing data.
    Each leg dict has 'race_num', 'horses' (list of top-2 horse dicts),
    'top1_prob', 'top2_prob', 'min_confidence'.
    """
    legs = []
    for offset in range(n_legs):
        race_num = start_race + offset
        race_id = _race_id_for(track_code, race_date, race_num)
        if race_id is None:
            return None  # missing race
        horses = _get_top2_for_race(race_id)
        if len(horses) < 2:
            return None  # need at least 2 horses
        # Use calibrated_prob if available, else win_prob
        def _prob(h):
            return float(h.get("calibrated_prob") or h.get("win_prob") or 0)
        top1_prob = _prob(horses[0])
        top2_prob = _prob(horses[1])
        confs = [h.get("confidence") for h in horses]
        # Lowest confidence in the leg drives Filter C
        order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_conf = min((c for c in confs if c), key=lambda c: order.get(c, 0),
                       default=None)
        legs.append({
            "race_num":     race_num,
            "race_id":      race_id,
            "horses":       horses,
            "top1_prob":    top1_prob,
            "top2_prob":    top2_prob,
            "top12_prob":   top1_prob + top2_prob,
            "min_conf":     min_conf,
        })
    return legs


def filter_c_passes(legs: list) -> bool:
    """Filter C: no LOW CONF legs allowed."""
    return not any(leg.get("min_conf") == "LOW" for leg in legs)


def score_sequence(legs: list, bet_type: str, track_code: str) -> dict:
    """Compute Bolton-Chapman qualification + EV for a sequence.

    Returns dict with all the fields needed to persist a sequence
    recommendation.
    """
    from core import bolton_chapman as bc

    n_legs = len(legs)
    cost = PICK3_COST if bet_type == "PICK3" else PICK4_COST

    # Filter C check
    f_c = filter_c_passes(legs)

    # Bolton-Chapman sequence qualification
    leg_probs = [(leg["top1_prob"], leg["top2_prob"]) for leg in legs]
    if bet_type == "PICK3":
        bc_pass, seq_prob, bc_reason = bc.pick3_sequence_qualifies(leg_probs)
    else:
        bc_pass, seq_prob, bc_reason = bc.pick4_sequence_qualifies(leg_probs)

    # Track-average payout
    avg_payout, n_records = track_avg_payout(track_code, bet_type)

    # Expected value
    if avg_payout and seq_prob > 0:
        ev = (seq_prob * avg_payout) - cost
    else:
        ev = None

    # Recommendation: must pass Filter C AND BC AND have positive EV
    recommended = (
        f_c
        and bc_pass
        and (ev is not None and ev > 0)
    )

    return {
        "bet_type":       bet_type,
        "track_code":     track_code,
        "cost":           cost,
        "n_legs":         n_legs,
        "sequence_prob":  seq_prob,
        "est_payout":     avg_payout,
        "payout_n_history": n_records,
        "expected_value": ev,
        "filter_c_pass":  f_c,
        "bc_qualifies":   bc_pass,
        "bc_reason":      bc_reason,
        "recommended":    recommended,
    }


def recommend_sequences_for_date(race_date: str, verbose: bool = True):
    """Top-level driver: build all candidate sequences for a date, score them,
    persist to agent_pick_sequences.

    Returns list of recommendation dicts.
    """
    if verbose:
        logger.info(f"Building sequences for {race_date} ...")

    # Get all tracks racing today
    with _get_conn() as conn:
        track_rows = conn.execute(
            "SELECT DISTINCT track_code FROM races WHERE race_date=?",
            (race_date,),
        ).fetchall()
    tracks = [r["track_code"] for r in track_rows]

    if verbose:
        logger.info(f"  {len(tracks)} track(s) racing today")

    all_recs = []
    for track in tracks:
        patterns = detect_track_sequences(track)
        for bet_type, start_races in patterns.items():
            n_legs = 3 if bet_type == "PICK3" else 4
            for start_race in start_races:
                legs = build_sequence_legs(track, race_date, start_race, n_legs)
                if legs is None:
                    continue
                scored = score_sequence(legs, bet_type, track)
                rec = {**scored, "legs": legs, "start_race_num": start_race,
                       "race_date": race_date}
                all_recs.append(rec)
                if verbose and scored["recommended"]:
                    logger.info(
                        f"  RECOMMEND: {track} {bet_type} R{start_race} - "
                        f"EV ${scored['expected_value']:.2f}, "
                        f"seq_prob {scored['sequence_prob']:.4f}, "
                        f"est_payout ${scored['est_payout']:.2f}"
                    )

    # Persist
    persist_sequences(all_recs)

    return all_recs


def persist_sequences(recs: list):
    """Insert recommended (and rejected, for tracking) sequences into DB."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        for r in recs:
            legs_json = json.dumps([{
                "race_num": leg["race_num"],
                "race_id":  leg["race_id"],
                "horses": [{
                    "program_num": h["program_num"],
                    "horse_name":  h["horse_name"],
                    "confidence":  h["confidence"],
                    "prob":        float(h.get("calibrated_prob") or h.get("win_prob") or 0),
                } for h in leg["horses"]],
                "top12_prob": leg["top12_prob"],
            } for leg in r["legs"]])
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO agent_pick_sequences
                    (bet_type, track_code, race_date, start_race_num,
                     legs_json, sequence_prob, est_payout, cost,
                     expected_value, bc_qualifies, bc_reason,
                     filter_c_pass, recommended, created_ts)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    r["bet_type"], r["track_code"], r["race_date"],
                    r["start_race_num"], legs_json,
                    r["sequence_prob"], r["est_payout"], r["cost"],
                    r["expected_value"],
                    1 if r["bc_qualifies"] else 0,
                    r["bc_reason"],
                    1 if r["filter_c_pass"] else 0,
                    1 if r["recommended"] else 0,
                    now,
                ))
            except Exception as e:
                logger.warning(f"Persist error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    today = date.today().isoformat()
    recs = recommend_sequences_for_date(today, verbose=True)
    n_rec = sum(1 for r in recs if r["recommended"])
    print(f"\nTotal candidates: {len(recs)}, recommended: {n_rec}")
