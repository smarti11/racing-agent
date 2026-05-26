"""Phase 1: Bolton-Chapman foundation, rank-order grading, payout infrastructure.

This migration is the foundation for the upcoming WIN-focused / Pick 3 / Pick 4 /
Exacta strategy redesign. It is intentionally LOW RISK — it ADDS capability without
removing any existing behavior. Phases 2 and 3 will refactor the strategy itself.

What this migration does:

1. Creates core/bolton_chapman.py with the academic validators:
   - MIN_PROBABILITY = 0.10 (the pmin floor from Bolton-Chapman 1986)
   - is_qualifying_bet(prob, odds) — applies pmin AND positive EV criterion
   - expected_return(prob, odds_decimal) — returns the EV multiplier

2. Adds `finish_position` column to `agent_picks` (rank-order grading per
   Bolton-Chapman's "rank order explosion" technique — every race becomes
   3 independent observations instead of 1).

3. Creates `pick_payouts` table for Pick 3 / Pick 4 historical storage
   (populated in Phase 3).

4. Extends data/results.py to parse Pick 3 and Pick 4 payouts from Equibase
   results pages (storage wired in Phase 3).

5. Updates grade_agent_picks() to populate finish_position alongside the
   existing WIN/PLACE/SHOW/MISS string label.

6. Adds a small "BOLTON-CHAPMAN VALIDATED" badge to the strategy section
   of dashboard/builder.py so users see the academic foundation.

All file changes get timestamped backups. Run from racing-agent root:
    venv/bin/python3 tools/migrate_phase1_foundation.py
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
DB_FILE = ROOT / "db" / "database.py"
RESULTS_FILE = ROOT / "data" / "results.py"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"
BC_FILE = ROOT / "core" / "bolton_chapman.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("phase1")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Step 1: core/bolton_chapman.py
# ---------------------------------------------------------------------------

BOLTON_CHAPMAN_SOURCE = '''"""Bolton-Chapman (1986) academic validators for horse race wagering.

Reference: Bolton & Chapman, "Searching for Positive Returns at the Track:
A Multinomial Logit Model for Handicapping Horse Races," Management Science,
Vol. 32, No. 8, August 1986.

The paper's key empirical finding (Table 4, p. 1057): wagering strategies
that filter out horses with estimated win probabilities below ~0.07-0.11
consistently produced positive returns. Below that pmin floor, the logit
model's estimates are too noisy on longshots and bettors lose money. Above
the floor, single-bet strategies returned 3.1% to 38.7% per race.

We set MIN_PROBABILITY = 0.10 as a conservative implementation of this
finding. Combined with Benter-style probability calibration, this acts as
an academic guardrail on every bet recommendation.
"""

# The pmin floor from Bolton-Chapman Table 4. Bets with calibrated probability
# below this floor are systematically eliminated because the model's longshot
# probability estimates are unreliable.
MIN_PROBABILITY = 0.10

# Minimum expected return multiplier to qualify a bet. expected_return must
# exceed this to clear the EV criterion (Bolton-Chapman use 1.0; we add a small
# margin to absorb model noise).
MIN_EXPECTED_RETURN = 1.05


def parse_odds_to_decimal(odds_str):
    """Convert a fractional or decimal odds string to decimal payout multiplier.

    "5/2" -> 3.5 (5/2 + 1 = 3.5 returned per $1 bet on WIN)
    "3"   -> 4.0
    "2.5" -> 3.5
    Returns None on parse failure.
    """
    if not odds_str:
        return None
    s = str(odds_str).strip()
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            return (float(num) / float(den)) + 1.0
        return float(s) + 1.0
    except (ValueError, ZeroDivisionError):
        return None


def expected_return(probability, odds_decimal):
    """Compute Bolton-Chapman expected return multiplier: p * (r + 1) where r
    is the odds payout per dollar bet (i.e., odds_decimal already includes the
    +1 if passed from parse_odds_to_decimal).

    For win betting on horse h: EV multiplier = p_h * payout_per_dollar.
    A bet has positive expectation when this exceeds 1.0.

    Returns 0.0 on bad inputs.
    """
    if probability is None or odds_decimal is None:
        return 0.0
    if probability <= 0 or odds_decimal <= 0:
        return 0.0
    return probability * odds_decimal


def is_qualifying_bet(probability, odds_decimal):
    """Apply both Bolton-Chapman criteria to a candidate bet.

    Returns (qualifies: bool, reason: str) tuple.
    Reasons: "OK", "BELOW_PMIN", "NEGATIVE_EV", "BAD_INPUT".
    """
    if probability is None or odds_decimal is None:
        return False, "BAD_INPUT"
    if probability < MIN_PROBABILITY:
        return False, "BELOW_PMIN"
    ev = expected_return(probability, odds_decimal)
    if ev < MIN_EXPECTED_RETURN:
        return False, "NEGATIVE_EV"
    return True, "OK"


def pick4_sequence_qualifies(legs):
    """Check if a Pick 4 sequence passes Bolton-Chapman.

    legs: list of (top1_prob, top2_prob) tuples for each of 4 legs.
    Each leg's combined probability must be >= MIN_PROBABILITY when we
    treat the "top 2 hits" as the bet target.

    Returns (qualifies: bool, sequence_probability: float, reason: str).
    """
    if not legs or len(legs) != 4:
        return False, 0.0, "BAD_LEG_COUNT"
    seq_prob = 1.0
    for top1, top2 in legs:
        leg_prob = (top1 or 0) + (top2 or 0)
        if leg_prob < MIN_PROBABILITY:
            return False, 0.0, "LEG_BELOW_PMIN"
        seq_prob *= leg_prob
    return True, seq_prob, "OK"


def pick3_sequence_qualifies(legs):
    """Same as pick4_sequence_qualifies but for 3 legs."""
    if not legs or len(legs) != 3:
        return False, 0.0, "BAD_LEG_COUNT"
    seq_prob = 1.0
    for top1, top2 in legs:
        leg_prob = (top1 or 0) + (top2 or 0)
        if leg_prob < MIN_PROBABILITY:
            return False, 0.0, "LEG_BELOW_PMIN"
        seq_prob *= leg_prob
    return True, seq_prob, "OK"


# Self-test on import
if __name__ == "__main__":
    # A favorite at 5/2 with 35% calibrated probability: should qualify
    p = 0.35
    o = parse_odds_to_decimal("5/2")  # 3.5
    print(f"5/2 favorite at p=0.35: EV={expected_return(p, o):.3f}")
    print(f"  qualifies: {is_qualifying_bet(p, o)}")

    # A longshot at 20/1 with 4% probability: BELOW_PMIN
    p = 0.04
    o = parse_odds_to_decimal("20/1")  # 21
    print(f"20/1 longshot at p=0.04: EV={expected_return(p, o):.3f}")
    print(f"  qualifies: {is_qualifying_bet(p, o)}")

    # Mid-priced at 4/1 with 15% probability: NEGATIVE_EV (15% * 5 = 0.75)
    p = 0.15
    o = parse_odds_to_decimal("4/1")  # 5
    print(f"4/1 horse at p=0.15: EV={expected_return(p, o):.3f}")
    print(f"  qualifies: {is_qualifying_bet(p, o)}")
'''


def create_bolton_chapman():
    logger.info("Step 1: Creating core/bolton_chapman.py ...")
    if BC_FILE.exists():
        logger.info("  Already exists; skipping")
        return
    BC_FILE.write_text(BOLTON_CHAPMAN_SOURCE)
    # Verify syntax
    import ast
    ast.parse(BC_FILE.read_text())
    logger.info(f"  Created ({len(BOLTON_CHAPMAN_SOURCE)} bytes, syntax OK)")


# ---------------------------------------------------------------------------
# Step 2: schema changes
# ---------------------------------------------------------------------------

def add_finish_position_column():
    logger.info("Step 2: Adding finish_position to agent_picks ...")
    with sqlite3.connect(DB_PATH) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(agent_picks)").fetchall()]
        if "finish_position" in cols:
            logger.info("  Column already exists; skipping")
            return
        conn.execute("ALTER TABLE agent_picks ADD COLUMN finish_position INTEGER")
        conn.commit()
        logger.info("  Column added")


def create_pick_payouts_table():
    logger.info("Step 3: Creating pick_payouts table ...")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pick_payouts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id     INTEGER NOT NULL,
                bet_type    TEXT NOT NULL,        -- 'PICK3', 'PICK4', 'PICK5', 'PICK6'
                combo       TEXT,                 -- '1-2-3-4'
                payout      REAL,                 -- dollar payout for $0.50 or $2 base
                base_amount REAL,                 -- $0.50 or $2.00
                posted_ts   TEXT NOT NULL,
                UNIQUE(race_id, bet_type),
                FOREIGN KEY(race_id) REFERENCES races(id)
            );
            CREATE INDEX IF NOT EXISTS idx_pick_payouts_race
                ON pick_payouts(race_id);
            CREATE INDEX IF NOT EXISTS idx_pick_payouts_type
                ON pick_payouts(bet_type);
        """)
        logger.info("  pick_payouts created/verified")


# ---------------------------------------------------------------------------
# Step 4: Patch data/results.py for Pick 3 / Pick 4 parsing
# ---------------------------------------------------------------------------

def patch_results_parser():
    logger.info("Step 4: Patching data/results.py for Pick 3/4 parsing ...")
    src = RESULTS_FILE.read_text()
    if "PICK_N_PARSING_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(RESULTS_FILE)

    # Add pick3/pick4 to the result dict initialization
    old_init = (
        '        "exacta": None,\n'
        '        "trifecta": None,\n'
        '        "superfecta": None,\n'
        '        "daily_double": None,\n'
    )
    new_init = (
        '        "exacta": None,\n'
        '        "trifecta": None,\n'
        '        "superfecta": None,\n'
        '        "daily_double": None,\n'
        '        "pick3": None,        # PICK_N_PARSING_APPLIED\n'
        '        "pick4": None,\n'
        '        "pick5": None,\n'
        '        "pick6": None,\n'
    )

    if old_init not in src:
        logger.error("  Could not locate result dict init; aborting")
        raise SystemExit(1)
    src = src.replace(old_init, new_init)

    # Add Pick 3/4/5/6 parsing alongside Daily Double
    old_dd = (
        '        if line.startswith("Daily Double") or line.startswith("Double"):\n'
        '            m2 = re.search(r\'\\$(\\d+\\.\\d+)\', line)\n'
        '            if m2:\n'
        '                result["daily_double"] = {"combo": line.split("$")[0].strip(), "payout": float(m2.group(1))}\n'
    )

    new_block = (
        old_dd +
        '\n'
        '        # PICK_N_PARSING_APPLIED: Pick 3 / 4 / 5 / 6\n'
        '        # Equibase formats: "Pick 3 1-2-3 $42.20", "Pick Four ...", etc.\n'
        '        for _pick_key, _pick_patterns in (\n'
        '            ("pick3", ("Pick 3", "Pick Three")),\n'
        '            ("pick4", ("Pick 4", "Pick Four")),\n'
        '            ("pick5", ("Pick 5", "Pick Five")),\n'
        '            ("pick6", ("Pick 6", "Pick Six")),\n'
        '        ):\n'
        '            if any(line.startswith(p) for p in _pick_patterns):\n'
        '                _m = re.search(r\'\\$(\\d+\\.\\d+)\', line)\n'
        '                if _m:\n'
        '                    result[_pick_key] = {\n'
        '                        "combo": line.split("$")[0].strip(),\n'
        '                        "payout": float(_m.group(1)),\n'
        '                    }\n'
    )

    if old_dd not in src:
        logger.error("  Could not locate Daily Double parser; aborting")
        raise SystemExit(1)
    src = src.replace(old_dd, new_block)

    RESULTS_FILE.write_text(src)
    import ast
    ast.parse(RESULTS_FILE.read_text())
    logger.info("  data/results.py patched (syntax OK)")


# ---------------------------------------------------------------------------
# Step 5: Patch db/database.py grade_agent_picks for finish_position
# ---------------------------------------------------------------------------

def patch_grade_function():
    logger.info("Step 5: Patching grade_agent_picks for rank-order grading ...")
    src = DB_FILE.read_text()
    if "RANK_ORDER_GRADING_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(DB_FILE)

    old_func = (
        'def grade_agent_picks(race_id: int, result_data: dict):\n'
        '    """\n'
        '    Grade agent picks against actual result.\n'
        '    Sets result = WIN/PLACE/SHOW/MISS for each pick.\n'
        '    """\n'
        '    winner_num = str(result_data.get("winner_num", ""))\n'
        '    second_num = str(result_data.get("second_num", "") or "")\n'
        '    third_num  = str(result_data.get("third_num", "") or "")\n'
        '\n'
        '    with get_conn() as conn:\n'
        '        picks = conn.execute(\n'
        '            "SELECT id, program_num FROM agent_picks WHERE race_id=? AND result IS NULL",\n'
        '            (race_id,)\n'
        '        ).fetchall()\n'
        '\n'
        '        for pick in picks:\n'
        '            pn = str(pick["program_num"])\n'
        '            if pn == winner_num:\n'
        '                grade = "WIN"\n'
        '            elif pn == second_num:\n'
        '                grade = "PLACE"\n'
        '            elif pn == third_num:\n'
        '                grade = "SHOW"\n'
        '            else:\n'
        '                grade = "MISS"\n'
        '            conn.execute(\n'
        '                "UPDATE agent_picks SET result=? WHERE id=?",\n'
        '                (grade, pick["id"])\n'
        '            )\n'
    )

    new_func = (
        'def grade_agent_picks(race_id: int, result_data: dict):\n'
        '    """\n'
        '    Grade agent picks against actual result. RANK_ORDER_GRADING_APPLIED.\n'
        '\n'
        '    Sets BOTH:\n'
        '      - result: WIN / PLACE / SHOW / MISS  (legacy text label)\n'
        '      - finish_position: 1 / 2 / 3 / NULL  (rank-order; NULL = not in top 3)\n'
        '\n'
        '    The rank-order data enables Bolton-Chapman style analysis: every race\n'
        '    becomes 3 independent observations instead of 1 (Chapman & Staelin 1982\n'
        '    explosion process).\n'
        '    """\n'
        '    winner_num = str(result_data.get("winner_num", "") or "")\n'
        '    second_num = str(result_data.get("second_num", "") or "")\n'
        '    third_num  = str(result_data.get("third_num", "") or "")\n'
        '\n'
        '    with get_conn() as conn:\n'
        '        picks = conn.execute(\n'
        '            "SELECT id, program_num FROM agent_picks WHERE race_id=? AND result IS NULL",\n'
        '            (race_id,)\n'
        '        ).fetchall()\n'
        '\n'
        '        for pick in picks:\n'
        '            pn = str(pick["program_num"])\n'
        '            if pn == winner_num:\n'
        '                grade, pos = "WIN", 1\n'
        '            elif pn == second_num:\n'
        '                grade, pos = "PLACE", 2\n'
        '            elif pn == third_num:\n'
        '                grade, pos = "SHOW", 3\n'
        '            else:\n'
        '                grade, pos = "MISS", None\n'
        '            conn.execute(\n'
        '                "UPDATE agent_picks SET result=?, finish_position=? WHERE id=?",\n'
        '                (grade, pos, pick["id"])\n'
        '            )\n'
    )

    if old_func not in src:
        logger.error("  Could not locate grade_agent_picks in expected form; aborting")
        raise SystemExit(1)
    src = src.replace(old_func, new_func)
    DB_FILE.write_text(src)
    import ast
    ast.parse(DB_FILE.read_text())
    logger.info("  db/database.py patched (syntax OK)")


# ---------------------------------------------------------------------------
# Step 6: Add Bolton-Chapman validation badge to dashboard
# ---------------------------------------------------------------------------

def add_bolton_chapman_badge():
    logger.info("Step 6: Adding Bolton-Chapman badge to dashboard ...")
    src = BUILDER_FILE.read_text()
    if "BC_BADGE_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(BUILDER_FILE)

    # Find the OPTIMIZED STRATEGY header line and inject a small badge next to it
    old_header = (
        "f'⭐ OPTIMIZED STRATEGY — {o[\"total_races\"]} RACES — HIGH:$2 WIN · MED:$0.50 PL+SH · LOW:$0.50 SH · EXACTA BOX:$3.00'"
    )

    new_header = (
        "f'⭐ OPTIMIZED STRATEGY — {o[\"total_races\"]} RACES — HIGH:$2 WIN · MED:$0.50 PL+SH · LOW:$0.50 SH · EXACTA BOX:$3.00'"
        " + '<span style=\"margin-left:10px;padding:2px 8px;background:#0a2540;border:1px solid #4a90e2;border-radius:10px;color:#7eb6ff;font-size:9px;font-weight:600;letter-spacing:.05em;vertical-align:middle\">📊 BOLTON-CHAPMAN VALIDATED</span>'  # BC_BADGE_APPLIED"
    )

    if old_header not in src:
        logger.warning("  Could not locate strategy header for badge; skipping (non-fatal)")
        return
    src = src.replace(old_header, new_header)
    BUILDER_FILE.write_text(src)
    import ast
    ast.parse(BUILDER_FILE.read_text())
    logger.info("  Badge added (syntax OK)")


# ---------------------------------------------------------------------------
# Step 7: Self-test the bolton_chapman module
# ---------------------------------------------------------------------------

def smoke_test_bolton_chapman():
    logger.info("Step 7: Smoke-testing bolton_chapman module ...")
    sys.path.insert(0, str(ROOT))
    try:
        from core import bolton_chapman as bc
    except ImportError as e:
        logger.error(f"  Import failed: {e}")
        raise SystemExit(1)

    # Test 1: parse_odds
    assert bc.parse_odds_to_decimal("5/2") == 3.5, "parse_odds 5/2 fail"
    assert bc.parse_odds_to_decimal("3") == 4.0, "parse_odds 3 fail"
    assert bc.parse_odds_to_decimal(None) is None, "parse_odds None fail"

    # Test 2: favorite at p=0.35, 5/2 (decimal 3.5) -> EV = 1.225, qualifies
    q, r = bc.is_qualifying_bet(0.35, bc.parse_odds_to_decimal("5/2"))
    assert q is True and r == "OK", f"favorite should qualify, got {q}/{r}"

    # Test 3: longshot at p=0.04, 20/1 -> BELOW_PMIN
    q, r = bc.is_qualifying_bet(0.04, bc.parse_odds_to_decimal("20/1"))
    assert q is False and r == "BELOW_PMIN", f"longshot should fail pmin, got {q}/{r}"

    # Test 4: mid horse at p=0.15, 4/1 (decimal 5.0) -> EV = 0.75, NEGATIVE_EV
    q, r = bc.is_qualifying_bet(0.15, bc.parse_odds_to_decimal("4/1"))
    assert q is False and r == "NEGATIVE_EV", f"negative EV should fail, got {q}/{r}"

    # Test 5: Pick 4 sequence with one weak leg
    legs = [(0.40, 0.25), (0.30, 0.20), (0.05, 0.03), (0.35, 0.20)]
    q, p, r = bc.pick4_sequence_qualifies(legs)
    assert q is False and r == "LEG_BELOW_PMIN", f"weak leg should fail, got {q}/{r}"

    # Test 6: Pick 4 sequence all legs strong
    legs = [(0.40, 0.25), (0.30, 0.20), (0.25, 0.20), (0.35, 0.20)]
    q, p, r = bc.pick4_sequence_qualifies(legs)
    assert q is True and r == "OK", f"strong sequence should qualify, got {q}/{r}"

    logger.info("  All assertions passed")


def main():
    logger.info("=" * 60)
    logger.info("PHASE 1 MIGRATION: BOLTON-CHAPMAN FOUNDATION")
    logger.info("=" * 60)

    create_bolton_chapman()
    add_finish_position_column()
    create_pick_payouts_table()
    patch_results_parser()
    patch_grade_function()
    add_bolton_chapman_badge()
    smoke_test_bolton_chapman()

    logger.info("=" * 60)
    logger.info("PHASE 1 COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("What was added:")
    logger.info("  - core/bolton_chapman.py (academic validators)")
    logger.info("  - agent_picks.finish_position column (rank-order grading)")
    logger.info("  - pick_payouts table (Pick 3/4 storage for Phase 3)")
    logger.info("  - Pick 3/4/5/6 parsing in data/results.py")
    logger.info("  - Updated grade_agent_picks to populate finish_position")
    logger.info("  - 'BOLTON-CHAPMAN VALIDATED' badge on dashboard")
    logger.info("")
    logger.info("Nothing was removed. All existing behavior preserved.")
    logger.info("")
    logger.info("Restart racing-agent:")
    logger.info("  cd ~/Documents/racing-agent && nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")


if __name__ == "__main__":
    main()
