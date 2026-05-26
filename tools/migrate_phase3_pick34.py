"""Phase 3: Pick 3 / Pick 4 strategy.

Builds the multi-race sequence betting strategy on top of Phase 1's
foundation (pick_payouts table, BC validators) and Phase 2A's top2 selector.

What this migration does:

1. Creates `agent_pick_sequences` table — one row per recommended
   multi-race wager (Pick 3 or Pick 4). Includes legs, EV, cost,
   recommendation status, result fields.

2. Creates `core/pick4_picker.py` module with:
   - detect_track_sequences(track_code, lookback_days) — empirically
     finds the Pick 3/4 starting races per track from pick_payouts
   - track_avg_payout(track_code, bet_type) — historical average
   - build_today_sequences(track_code, race_date) — match today's slate
     to historical sequence patterns
   - score_sequence(legs, bet_type, track_code) — applies Filter C
     (no LOW CONF legs), BC sequence qualification, computes EV
   - recommend_sequences_for_date(race_date) — top-level driver

3. Adds Pick 3 / Pick 4 strategy panels to dashboard/builder.py
   with separate baseline counters (300 / 200 sequences).

4. Smoke-tests synthetic 4-leg sequences against BC criteria and
   sequence probability math.

DOES NOT wire into racing_agent.py's save_todays_picks yet — that's a
follow-on step once we verify the picker on tonight's data. The picker
can be called manually via tools or via the dashboard.

Run from racing-agent root:
    venv/bin/python3 tools/migrate_phase3_pick34.py
"""

import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "db" / "racing.db"
PICKER_FILE = ROOT / "core" / "pick4_picker.py"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase3")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Step 1: agent_pick_sequences table
# ---------------------------------------------------------------------------

def create_sequences_table():
    logger.info("Step 1: Creating agent_pick_sequences table ...")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_pick_sequences (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_type        TEXT NOT NULL,        -- 'PICK3' or 'PICK4'
                track_code      TEXT NOT NULL,
                race_date       TEXT NOT NULL,
                start_race_num  INTEGER NOT NULL,
                legs_json       TEXT NOT NULL,        -- JSON: [{race, horses:[{num,name,prob}]}]
                sequence_prob   REAL,                 -- multiplicative leg probability
                est_payout      REAL,                 -- track-average payout
                cost            REAL,                 -- $0.50 × combos
                expected_value  REAL,                 -- prob × payout - cost
                bc_qualifies    INTEGER,              -- 1 = passes Bolton-Chapman
                bc_reason       TEXT,
                filter_c_pass   INTEGER,              -- 1 = no LOW CONF legs
                recommended     INTEGER NOT NULL,     -- 1 = BET, 0 = SKIP
                created_ts      TEXT NOT NULL,
                -- Result tracking (populated post-race)
                actual_winners  TEXT,                 -- JSON list of winning prog_nums
                hit             INTEGER,              -- 1 = all legs hit, 0 = miss
                actual_payout   REAL,                 -- actual Pick 3/4 payout
                graded_ts       TEXT,
                UNIQUE(bet_type, track_code, race_date, start_race_num)
            );
            CREATE INDEX IF NOT EXISTS idx_seq_date
                ON agent_pick_sequences(race_date);
            CREATE INDEX IF NOT EXISTS idx_seq_recommended
                ON agent_pick_sequences(recommended, race_date);
            CREATE INDEX IF NOT EXISTS idx_seq_type
                ON agent_pick_sequences(bet_type, race_date);
        """)
    logger.info("  Created/verified")


# ---------------------------------------------------------------------------
# Step 2: core/pick4_picker.py source
# ---------------------------------------------------------------------------

PICKER_SOURCE = '''"""Pick 3 / Pick 4 sequence picker.

Strategy summary:
- Empirical sequence detection: identify which Pick 3/4 windows each track
  actually offers (from historical pick_payouts data).
- Top-2 per leg: each leg uses the top 2 horses by base score (from Phase 2A
  top2_picks). Combos = 2^N (8 for Pick 3, 16 for Pick 4) × $0.50 base.
- Filter C: no LOW CONF legs allowed.
- Bolton-Chapman: each leg\'s combined top-2 probability must be >= MIN_PROBABILITY
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
              AND pp.bet_type IN (\'PICK3\', \'PICK4\')
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
    """Fetch the agent\'s top 2 picks for a race (from agent_picks)."""
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
    Each leg dict has \'race_num\', \'horses\' (list of top-2 horse dicts),
    \'top1_prob\', \'top2_prob\', \'min_confidence\'.
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
                        f"EV ${scored[\'expected_value\']:.2f}, "
                        f"seq_prob {scored[\'sequence_prob\']:.4f}, "
                        f"est_payout ${scored[\'est_payout\']:.2f}"
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
    print(f"\\nTotal candidates: {len(recs)}, recommended: {n_rec}")
'''


def create_picker_module():
    logger.info("Step 2: Creating core/pick4_picker.py ...")
    if PICKER_FILE.exists():
        logger.info("  Already exists; skipping")
        return
    PICKER_FILE.write_text(PICKER_SOURCE)
    import ast
    ast.parse(PICKER_FILE.read_text())
    logger.info(f"  Created ({len(PICKER_SOURCE)} bytes, syntax OK)")


# ---------------------------------------------------------------------------
# Step 3: Dashboard panels for Pick 3 / Pick 4 with baseline counters
# ---------------------------------------------------------------------------

DASHBOARD_PANEL_SOURCE = '''
def _build_pick34_panels():
    """Build Pick 3 and Pick 4 strategy panels for the dashboard."""
    try:
        from db.database import get_conn
        with get_conn() as conn:
            # Per-bet-type stats from agent_pick_sequences
            stats = {}
            for bet_type in ("PICK3", "PICK4"):
                row = conn.execute("""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN recommended=1 THEN 1 ELSE 0 END) AS recommended,
                        SUM(CASE WHEN hit=1 THEN 1 ELSE 0 END) AS hits,
                        SUM(CASE WHEN recommended=1 THEN cost ELSE 0 END) AS wagered,
                        SUM(CASE WHEN hit=1 THEN actual_payout ELSE 0 END) AS returned
                    FROM agent_pick_sequences
                    WHERE bet_type=?
                """, (bet_type,)).fetchone()
                stats[bet_type] = dict(row) if row else {}

            # Today\'s recommended sequences
            from datetime import date as _date
            today = _date.today().isoformat()
            today_rows = conn.execute("""
                SELECT bet_type, track_code, start_race_num,
                       sequence_prob, est_payout, expected_value, cost
                FROM agent_pick_sequences
                WHERE race_date=? AND recommended=1
                ORDER BY expected_value DESC
                LIMIT 20
            """, (today,)).fetchall()
            today_recs = [dict(r) for r in today_rows]

        return stats, today_recs
    except Exception as _e:
        return {}, []


def _render_pick34_panel(bet_type: str, stats: dict, today_recs: list,
                         threshold: int):
    """Render one strategy panel (Pick 3 or Pick 4)."""
    label = "PICK 3" if bet_type == "PICK3" else "PICK 4"
    cost = 4.00 if bet_type == "PICK3" else 8.00
    s = stats.get(bet_type, {})
    total = s.get("total", 0) or 0
    rec = s.get("recommended", 0) or 0
    hits = s.get("hits", 0) or 0
    wagered = s.get("wagered", 0) or 0
    returned = s.get("returned", 0) or 0
    net = returned - wagered
    roi = (100.0 * net / wagered) if wagered else 0

    # Baseline progress
    progress_pct = min(100.0, 100.0 * rec / threshold) if threshold else 0
    baseline_html = ""
    if rec < threshold:
        baseline_html = (
            f\'<div style="background:#1a1003;border:1px solid #ff8c00;\'
            f\'border-radius:4px;padding:6px 10px;margin-bottom:10px;\'
            f\'font-size:10px;color:#ffb86b">\'
            f\'⚠ {label} BASELINE: {rec} / {threshold} sequences \'
            f\'recommended ({progress_pct:.1f}%). Not yet publishing-ready.\'
            f\'</div>\'
        )

    today_html = ""
    if today_recs:
        seq_rows = ""
        for r in today_recs:
            if r["bet_type"] != bet_type:
                continue
            seq_rows += (
                f\'<tr><td style="padding:4px 8px;color:#c8d8f0">{r["track_code"]}</td>\'
                f\'<td style="padding:4px 8px;text-align:center;color:#4a6080">R{r["start_race_num"]}-{r["start_race_num"] + (2 if bet_type == "PICK3" else 3)}</td>\'
                f\'<td style="padding:4px 8px;text-align:right;color:#4a6080">{(r["sequence_prob"] or 0)*100:.2f}%</td>\'
                f\'<td style="padding:4px 8px;text-align:right;color:#4a6080">${r["est_payout"] or 0:.2f}</td>\'
                f\'<td style="padding:4px 8px;text-align:right;color:#00c896;font-weight:700">${r["expected_value"] or 0:+.2f}</td></tr>\'
            )
        if seq_rows:
            today_html = (
                \'<table style="width:100%;border-collapse:collapse;font-size:10px;margin-top:8px">\'
                \'<thead><tr style="background:#162038">\'
                \'<th style="padding:4px 8px;text-align:left;color:#4a6080">TRACK</th>\'
                \'<th style="padding:4px 8px;text-align:center;color:#4a6080">RACES</th>\'
                \'<th style="padding:4px 8px;text-align:right;color:#4a6080">SEQ PROB</th>\'
                \'<th style="padding:4px 8px;text-align:right;color:#4a6080">EST PAYOUT</th>\'
                \'<th style="padding:4px 8px;text-align:right;color:#4a6080">EV</th>\'
                \'</tr></thead><tbody>\' + seq_rows + \'</tbody></table>\'
            )

    color = "#00c896" if net >= 0 else "#ff4d6d"
    return (
        f\'<div style="margin:0 0 16px 0;background:#0f1729;border:0.5px solid #1e2d4a;border-radius:10px;padding:14px 18px">\'
        f\'<div style="font-size:11px;font-weight:700;color:#00c896;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:0.5px solid #00c89633">\'
        f\'{label} STRATEGY — ${cost:.2f}/sequence — TOP 2 PER LEG\'
        f\'</div>\'
        f\'{baseline_html}\'
        f\'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px">\'
        f\'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">SEQUENCES</div><div style="font-size:14px;font-weight:700;color:#fff">{rec}</div></div>\'
        f\'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">HITS</div><div style="font-size:14px;font-weight:700;color:#fff">{hits}</div></div>\'
        f\'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">NET P&L</div><div style="font-size:14px;font-weight:700;color:{color}">${net:+.2f}</div></div>\'
        f\'<div style="background:#162038;border-radius:6px;padding:8px 10px"><div style="font-size:9px;color:#4a6080">ROI</div><div style="font-size:14px;font-weight:700;color:{color}">{roi:+.1f}%</div></div>\'
        f\'</div>\'
        f\'{today_html}\'
        f\'</div>\'
    )


def build_pick34_section():
    """Top-level: returns the combined Pick 3 + Pick 4 HTML for dashboard."""
    stats, today_recs = _build_pick34_panels()
    p3 = _render_pick34_panel("PICK3", stats, today_recs, threshold=300)
    p4 = _render_pick34_panel("PICK4", stats, today_recs, threshold=200)
    return p3 + p4

# PHASE3_PICK34_PANELS_APPLIED
'''


def add_pick34_panels_to_builder():
    logger.info("Step 3: Adding Pick 3/4 panel renderer to builder.py ...")
    src = BUILDER_FILE.read_text()
    if "PHASE3_PICK34_PANELS_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(BUILDER_FILE)

    new_src = src.rstrip() + "\n\n" + DASHBOARD_PANEL_SOURCE + "\n"
    BUILDER_FILE.write_text(new_src)

    import ast
    ast.parse(BUILDER_FILE.read_text())
    logger.info("  Panel renderer added (syntax OK)")
    logger.info("  Note: panel functions are defined but not yet called from")
    logger.info("        the main build_html flow. Manual integration needed")
    logger.info("        once backfill has populated pick_payouts.")


# ---------------------------------------------------------------------------
# Step 4: Smoke test the picker
# ---------------------------------------------------------------------------

def smoke_test():
    logger.info("Step 4: Smoke-testing pick4_picker ...")
    # Force-reload
    for mod_name in ("core.pick4_picker", "core.bolton_chapman"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    from core import pick4_picker as p
    from core import bolton_chapman as bc

    # Test 1: filter_c_passes
    legs_low = [
        {"min_conf": "HIGH"}, {"min_conf": "MEDIUM"},
        {"min_conf": "LOW"},  {"min_conf": "HIGH"},
    ]
    assert p.filter_c_passes(legs_low) is False, "Filter C should fail with LOW leg"
    legs_ok = [
        {"min_conf": "HIGH"}, {"min_conf": "MEDIUM"},
        {"min_conf": "HIGH"}, {"min_conf": "HIGH"},
    ]
    assert p.filter_c_passes(legs_ok) is True, "Filter C should pass with no LOW"
    logger.info("  Test 1 (Filter C): PASS")

    # Test 2: BC sequence qualification math
    legs = [(0.35, 0.20), (0.30, 0.18), (0.40, 0.22), (0.28, 0.16)]
    q, seq_p, reason = bc.pick4_sequence_qualifies(legs)
    assert q is True, f"strong sequence should qualify, reason={reason}"
    expected_p = (0.55) * (0.48) * (0.62) * (0.44)
    assert abs(seq_p - expected_p) < 1e-6, f"seq_prob math off: {seq_p} vs {expected_p}"
    logger.info(f"  Test 2 (BC math): PASS (seq_prob={seq_p:.4f})")

    # Test 3: weak leg blocks
    legs_weak = [(0.35, 0.20), (0.03, 0.04), (0.40, 0.22), (0.28, 0.16)]
    q, _, reason = bc.pick4_sequence_qualifies(legs_weak)
    assert q is False and reason == "LEG_BELOW_PMIN", f"weak leg should fail: {reason}"
    logger.info("  Test 3 (weak leg rejected): PASS")

    # Test 4: Pick 3 vs Pick 4 cost calculation
    assert p.PICK3_COST == 4.0, f"Pick 3 cost should be $4, got {p.PICK3_COST}"
    assert p.PICK4_COST == 8.0, f"Pick 4 cost should be $8, got {p.PICK4_COST}"
    logger.info("  Test 4 (cost math): PASS")

    logger.info("  All smoke tests passed")


def main():
    logger.info("=" * 60)
    logger.info("PHASE 3 MIGRATION: PICK 3 / PICK 4 STRATEGY")
    logger.info("=" * 60)

    create_sequences_table()
    create_picker_module()
    add_pick34_panels_to_builder()
    smoke_test()

    logger.info("=" * 60)
    logger.info("PHASE 3 COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("What was added:")
    logger.info("  - agent_pick_sequences table (Pick 3/4 recommendations)")
    logger.info("  - core/pick4_picker.py (sequence detection + EV ranking)")
    logger.info("  - Dashboard panel renderers (Pick 3 / Pick 4 strategies)")
    logger.info("  - All Bolton-Chapman sequence qualification wired")
    logger.info("")
    logger.info("Not yet wired:")
    logger.info("  - racing_agent.py does NOT yet call the picker on cycle")
    logger.info("  - Dashboard build_html does NOT yet inject the panels")
    logger.info("  - pick_payouts must be backfilled before picker works")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Run the backfill (30-60 min, populates pick_payouts):")
    logger.info("       venv/bin/python3 tools/backfill_pick34_payouts.py --days 60")
    logger.info("  2. After backfill completes, manually run the picker:")
    logger.info("       venv/bin/python3 core/pick4_picker.py")
    logger.info("  3. Verify recommendations look sane before wiring into the agent")


if __name__ == "__main__":
    main()
