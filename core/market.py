"""Market probability normalization and Benter-style model blend.

Stage 1: fundamental softmax probabilities (core/probabilities.py)
Stage 2: logit blend with normalized market probabilities (this module)
Stage 3: edge scan across full field (scan_value_bets)
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from config.market import (
    ACTIONABLE_BLEND_ALPHA,
    ACTIONABLE_HIGH_CHALK_MAX_DEC,
    ACTIONABLE_MAX_PER_DAY,
    ACTIONABLE_MIN_DECIMAL,
    ACTIONABLE_MIN_EDGE,
    ACTIONABLE_MIN_REL_EDGE,
    ACTIONABLE_ONE_PER_RACE,
    ACTIONABLE_PREFER_LIVE,
    ACTIONABLE_SKIP_HIGH_CHALK,
    MARKET_BLEND_ALPHA,
    MIN_EDGE,
    TAKEOUT,
    VALUE_BET_MIN_DECIMAL,
)
from core.kelly import compute_edge, kelly_bet, kelly_fraction, parse_odds_to_decimal


def _logit(p: float, eps: float = 1e-6) -> float:
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def normalize_market_probs(
    odds_by_program: Dict[str, str],
    takeout: float = TAKEOUT,
) -> Dict[str, float]:
    """Convert odds strings to fair win probabilities that sum to 1.0."""
    raw: Dict[str, float] = {}
    for pgm, odds_str in odds_by_program.items():
        if not odds_str:
            continue
        dec = parse_odds_to_decimal(str(odds_str))
        if dec and dec > 1.0:
            raw[str(pgm)] = 1.0 / dec

    if not raw:
        return {}

    total = sum(raw.values())
    if total <= 0:
        return {}

    # Remove overround, then re-normalize to a proper distribution.
    fair = {k: (v / total) * (1.0 - takeout) for k, v in raw.items()}
    s = sum(fair.values())
    if s <= 0:
        return {}
    return {k: v / s for k, v in fair.items()}


def blend_race_probabilities(
    horses: List[dict],
    alpha: float = MARKET_BLEND_ALPHA,
    prob_field: str = "final_prob",
) -> None:
    """Apply logit-space blend; sets prob_field on each horse in-place."""
    if not horses:
        return

    logits: List[float] = []
    for h in horses:
        model_p = h.get("calibrated_prob") or h.get("win_prob") or 0.0
        market_p = h.get("market_prob") or 0.0
        if market_p > 0 and model_p > 0:
            blended = alpha * _logit(model_p) + (1.0 - alpha) * _logit(market_p)
        elif model_p > 0:
            blended = _logit(model_p)
        elif market_p > 0:
            blended = _logit(market_p)
        else:
            blended = _logit(1.0 / len(horses))
        logits.append(blended)

    probs = [_sigmoid(x) for x in logits]
    total = sum(probs)
    if total <= 0:
        uniform = 1.0 / len(horses)
        for h in horses:
            h[prob_field] = uniform
        return

    for h, p in zip(horses, probs):
        h[prob_field] = p / total


def _best_odds_for_horse(
    program_num: str,
    live_odds: Optional[Dict[str, str]],
    ml_map: Optional[Dict[str, str]],
) -> tuple[Optional[str], str]:
    """Return (odds_str, source) preferring live over morning line."""
    pgm = str(program_num)
    live = (live_odds or {}).get(pgm)
    if live:
        return live, "live"
    ml = (ml_map or {}).get(pgm)
    if ml:
        return ml, "ml"
    return None, ""


def enrich_race_with_market(
    horses: List[dict],
    live_odds: Optional[Dict[str, str]] = None,
    ml_map: Optional[Dict[str, str]] = None,
    alpha: float = MARKET_BLEND_ALPHA,
    takeout: float = TAKEOUT,
) -> None:
    """Attach market_prob, final_prob, edge, kelly_f, and corrected value."""
    if not horses:
        return

    odds_input: Dict[str, str] = {}
    for h in horses:
        pgm = str(h.get("program_num", ""))
        odds_str, source = _best_odds_for_horse(pgm, live_odds, ml_map)
        h["odds_str"] = odds_str
        h["odds_source"] = source
        if odds_str:
            odds_input[pgm] = odds_str

    market_probs = normalize_market_probs(odds_input, takeout=takeout)
    for h in horses:
        pgm = str(h.get("program_num", ""))
        h["market_prob"] = market_probs.get(pgm, 0.0)
        if h.get("calibrated_prob") is None:
            h["calibrated_prob"] = h.get("win_prob")

    blend_race_probabilities(horses, alpha=alpha, prob_field="final_prob")
    # Separate, lower-trust blend for edge/Kelly sizing only — see
    # config.market.ACTIONABLE_BLEND_ALPHA for why this can't reuse final_prob.
    blend_race_probabilities(horses, alpha=ACTIONABLE_BLEND_ALPHA, prob_field="actionable_prob")

    for h in horses:
        final_p = h.get("final_prob") or 0.0
        actionable_p = h.get("actionable_prob") or 0.0
        mkt_p = h.get("market_prob") or 0.0
        odds_str = h.get("odds_str")
        h["edge"] = compute_edge(actionable_p, odds_str, takeout) if odds_str else None
        h["kelly_f"] = kelly_fraction(actionable_p, odds_str, takeout) if odds_str else 0.0
        if mkt_p > 0 and final_p > 0:
            h["value"] = round((final_p - mkt_p) / mkt_p * 100, 1)
        else:
            h["value"] = 0.0


def scan_value_bets(
    horses: List[dict],
    min_edge: float = MIN_EDGE,
    min_decimal: float = VALUE_BET_MIN_DECIMAL,
) -> List[dict]:
    """Return all runners with positive edge, sorted by edge descending."""
    bets: List[dict] = []
    for h in horses:
        edge = h.get("edge")
        if edge is None or edge < min_edge:
            continue
        dec = parse_odds_to_decimal(h.get("odds_str") or "")
        if dec and dec < min_decimal:
            continue
        bets.append(h)
    bets.sort(key=lambda x: x.get("edge") or 0.0, reverse=True)
    return bets


# Scratches recorded more than this long after a race's own post time are
# retroactive bookkeeping (e.g. a nightly reconciliation sweep), not a live
# market-moving event — see _race_post_datetime.
POST_SCRATCH_GRACE_MINUTES = 60


def _race_post_datetime(race_date: str, post_time: str) -> Optional[datetime]:
    """Parse post_time into a naive local datetime (matches scratch_time's
    naive-local storage via datetime.now().isoformat() in db.database.mark_scratched)."""
    if not post_time or not race_date:
        return None
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", post_time.strip(), re.IGNORECASE)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    ampm = (match.group(3) or "").upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    elif not ampm and hour < 8:
        hour += 12  # no AM/PM stored; times < 8 are PM (no US racing at 1-7 AM)
    try:
        return datetime.strptime(race_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
    except ValueError:
        return None


def _relative_edge(final_p: float, mkt_p: float) -> float:
    if not mkt_p or mkt_p <= 0 or not final_p:
        return 0.0
    return (final_p - mkt_p) / mkt_p


def _actionable_sort_key(h: dict) -> tuple:
    edge = h.get("edge") or 0.0
    live_rank = 0 if h.get("odds_source") == "live" else 1
    if not ACTIONABLE_PREFER_LIVE:
        live_rank = 0
    return (live_rank, -edge)


def select_actionable_bets(
    candidates: List[dict],
    high_chalk_keys: Optional[set] = None,
) -> List[dict]:
    """Narrow value candidates to a selective Benter-style bet list."""
    high_chalk_keys = high_chalk_keys or set()
    filtered: List[dict] = []

    for h in candidates:
        race_id = h.get("race_id")
        pgm = str(h.get("program_num", ""))
        if ACTIONABLE_SKIP_HIGH_CHALK and (race_id, pgm) in high_chalk_keys:
            continue

        # A scratch redistributes win probability across the remaining field,
        # but morning-line odds never update for it and live odds may lag it —
        # either way, edge/Kelly computed before the scratch price the wrong
        # field. Skip until this horse's value bet is recomputed post-scratch.
        last_scratch_ts = h.get("last_scratch_ts")
        created_ts = h.get("created_ts")
        if last_scratch_ts and created_ts and last_scratch_ts > created_ts:
            logger.warning(
                f"Skipping stale-post-scratch actionable candidate: race_id={race_id} "
                f"pgm={pgm} horse={h.get('horse_name')} "
                f"value_bet_created={created_ts} last_scratch={last_scratch_ts}"
            )
            continue

        edge = h.get("edge")
        if edge is None or edge < ACTIONABLE_MIN_EDGE:
            continue

        odds_str = h.get("odds_str") or ""
        dec = parse_odds_to_decimal(odds_str)
        if not dec or dec < ACTIONABLE_MIN_DECIMAL:
            continue

        actionable_p = h.get("actionable_prob") or 0.0
        mkt_p = h.get("market_prob") or 0.0
        if _relative_edge(actionable_p, mkt_p) < ACTIONABLE_MIN_REL_EDGE:
            continue

        kelly_f = h.get("kelly_f") or 0.0
        if kelly_f <= 0:
            continue

        bet_amt, _, _, should = kelly_bet(
            actionable_p, odds_str, min_edge=ACTIONABLE_MIN_EDGE,
        )
        if not should:
            continue

        out = dict(h)
        out["bet_amount"] = bet_amt
        out["rel_edge"] = _relative_edge(actionable_p, mkt_p)
        filtered.append(out)

    filtered.sort(key=_actionable_sort_key)

    if ACTIONABLE_ONE_PER_RACE:
        by_race: Dict[int, dict] = {}
        for h in filtered:
            rid = h.get("race_id")
            if rid is None:
                continue
            if rid not in by_race:
                by_race[rid] = h
        filtered = sorted(by_race.values(), key=_actionable_sort_key)

    return filtered[:ACTIONABLE_MAX_PER_DAY]


def rebuild_actionable_bets_for_date(race_date: str) -> int:
    """Rebuild today's actionable list from value bets + pick context."""
    from db.database import get_conn, save_agent_actionable_bets

    with get_conn() as conn:
        value_rows = conn.execute("""
            SELECT avb.*, r.track_name, r.race_num, r.post_time, r.track_code
            FROM agent_value_bets avb
            JOIN races r ON r.id = avb.race_id
            LEFT JOIN entries e ON e.race_id = avb.race_id
                AND e.program_num = avb.program_num
            WHERE r.race_date = ?
              AND (e.scratched IS NULL OR e.scratched = 0)
        """, (race_date,)).fetchall()

        race_ids = {row["race_id"] for row in value_rows}
        scratches_by_race: Dict[int, List[str]] = {}
        if race_ids:
            placeholders = ",".join("?" * len(race_ids))
            for row in conn.execute(f"""
                SELECT race_id, scratch_time FROM entries
                WHERE race_id IN ({placeholders}) AND scratched = 1
                  AND scratch_time IS NOT NULL
            """, tuple(race_ids)):
                scratches_by_race.setdefault(row["race_id"], []).append(row["scratch_time"])

        high_chalk_keys = set()
        if ACTIONABLE_SKIP_HIGH_CHALK:
            for row in conn.execute("""
                SELECT ap.race_id, ap.program_num, ap.morning_line
                FROM agent_picks ap
                JOIN races r ON r.id = ap.race_id
                WHERE r.race_date = ? AND ap.rank = 1 AND ap.confidence = 'HIGH'
            """, (race_date,)):
                dec = parse_odds_to_decimal(row["morning_line"] or "")
                if dec and dec < ACTIONABLE_HIGH_CHALK_MAX_DEC:
                    high_chalk_keys.add((row["race_id"], str(row["program_num"])))

    candidates = []
    for row in value_rows:
        d = dict(row)
        d["odds_source"] = d.get("odds_source") or (
            "live" if d.get("odds_str") else ""
        )

        race_scratches = scratches_by_race.get(d.get("race_id"), [])
        post_dt = _race_post_datetime(race_date, d.get("post_time") or "")
        market_moving_ts = None
        if post_dt is not None:
            cutoff = post_dt + timedelta(minutes=POST_SCRATCH_GRACE_MINUTES)
            for ts in race_scratches:
                try:
                    if datetime.fromisoformat(ts) <= cutoff:
                        if market_moving_ts is None or ts > market_moving_ts:
                            market_moving_ts = ts
                except ValueError:
                    continue
        elif race_scratches:
            # Can't parse this race's post time — fall back to "any scratch counts"
            market_moving_ts = max(race_scratches)
        d["last_scratch_ts"] = market_moving_ts

        candidates.append(d)

    actionable = select_actionable_bets(candidates, high_chalk_keys)
    save_agent_actionable_bets(race_date, actionable)
    return len(actionable)


def clean_odds_text(text: str) -> Optional[str]:
    """Extract a single odds fraction from Equibase desktop cell text."""
    if not text:
        return None
    s = re.sub(r"\s+", " ", text.strip())
    if not s or s.upper() in ("SCR", "-", "N/A"):
        return None
    # Cell may show "5/2" or "5-2" or "12" (meaning 12/1)
    for pat in (
        r"(\d+\.?\d*\s*[/\-]\s*\d+\.?\d*)",
        r"^(\d+\.?\d*)$",
    ):
        m = re.search(pat, s)
        if m:
            token = m.group(1).replace("-", "/")
            if parse_odds_to_decimal(token):
                return token
    return None
