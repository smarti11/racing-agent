"""Phase 2A: Top-2 selection with Bolton-Chapman gating.

Replaces the PLACE/SHOW role-based picker with a clean top-2-by-score picker.
The dashboard remains untouched in this phase (it's PHASE 2B's job). Phase 2A
only changes WHICH horses get selected; it doesn't touch HOW they're displayed.

What this migration does:

1. Adds `top2_picks(scored_horses)` function to core/handicapper.py.
   - Returns the top 2 horses by base score, both tagged with their
     Bolton-Chapman qualification status.
   - Keeps the WEAK_SIGNAL_TRACKS skip logic intact.
   - Each pick gets confidence (already computed) and bc_qualifies flag.

2. Leaves place_score, show_score, role_ranked_picks IN PLACE for now.
   They become unused but stay as fallbacks. Phase 2B removes them.

3. Patches dashboard/builder.py to call top2_picks instead of
   role_ranked_picks. The return shape is mapped so existing PLACE/SHOW
   panels don't crash — they just receive top-2 horses instead of
   PLACE/SHOW-optimized horses. Phase 2B will refactor the panels.

4. Updates the dashboard's agent_picks_history INSERT to log only the
   actually-bet horses (top 2), with role labels 'WIN' and 'BACKUP'
   instead of WIN/PLACE/SHOW.

5. Smoke-tests the new picker against synthetic horse data.

All file changes get timestamped backups. Run from racing-agent root:
    venv/bin/python3 tools/migrate_phase2a_top2.py
"""

import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

HANDICAPPER_FILE = ROOT / "core" / "handicapper.py"
BUILDER_FILE = ROOT / "dashboard" / "builder.py"
DB_PATH = ROOT / "db" / "racing.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("phase2a")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Step 1: Add top2_picks function to handicapper.py
# ---------------------------------------------------------------------------

TOP2_PICKS_SOURCE = '''

# ── Top-2 Picker (Phase 2A) ────────────────────────────────────────────────
# Pure score-based top-2 selection with Bolton-Chapman EV gating.
# Replaces role_ranked_picks (which used separate PLACE/SHOW scoring functions).
# The PLACE/SHOW logic is preserved above as dead code for now; Phase 2B removes it.

def top2_picks(scored_horses: list) -> dict:
    """Top-2 horse selection for WIN / Exacta / Pick 3 / Pick 4 strategies.

    Both picks come from raw base score (no PLACE/SHOW reshuffling).
    Each pick is tagged with Bolton-Chapman qualification status so downstream
    bet-placement logic can filter on the academic criteria.

    Returns a dict with keys (kept compatible with existing callers):
      "win":     top horse dict (role=WIN, confidence, bc_qualifies, bc_reason)
      "place":   2nd horse dict (role=BACKUP, ...) — name kept for compat
      "show":    None (no longer used; kept as None for compat)
      "all":     [win, backup]  list of 2 picks for dashboard top-3 panel
      "top2":    same as all (explicit name)
    """
    if not scored_horses:
        return {"win": None, "place": None, "show": None, "all": [], "top2": []}

    active = [h for h in scored_horses if h.get("score", 0) > 0]
    if not active:
        return {"win": None, "place": None, "show": None, "all": [], "top2": []}

    # Weak-signal track filter (unchanged from role_ranked_picks)
    _tc = active[0].get("track_code", "")
    if _tc in WEAK_SIGNAL_TRACKS:
        _conf = active[0].get("confidence", "LOW")
        if _conf != "HIGH":
            logger.info(
                "[WEAK TRACK SKIP] track=%s horse=%r confidence=%s — "
                "skipping (only HIGH CONF bets placed at weak-signal tracks)",
                _tc, active[0].get("horse_name"), _conf,
            )
            return {"win": None, "place": None, "show": None, "all": [], "top2": []}

    # Bolton-Chapman gating
    try:
        from core import bolton_chapman as bc
    except ImportError:
        bc = None

    def _annotate(horse: dict, role: str, rank: int) -> dict:
        h = horse.copy()
        h["role"] = role
        h["rank"] = rank
        # Bolton-Chapman qualification
        qualifies, reason = False, "NO_BC_MODULE"
        if bc is not None:
            prob = h.get("calibrated_prob") or h.get("win_prob")
            ml = h.get("morning_line", "")
            odds_dec = bc.parse_odds_to_decimal(ml) if ml else None
            qualifies, reason = bc.is_qualifying_bet(prob, odds_dec)
        h["bc_qualifies"] = qualifies
        h["bc_reason"] = reason
        # Bet recommendation by role + BC gate
        if role == "WIN":
            if qualifies and h.get("confidence") == "HIGH":
                h["bet_recommendation"] = "$2.00 WIN"
            else:
                h["bet_recommendation"] = "SKIP" if not qualifies else "Pass"
        else:  # BACKUP
            # Backup horse used in exacta box / Pick 3 / Pick 4 sequences
            h["bet_recommendation"] = "Exacta/Multi-race only"
        return h

    win_horse = _annotate(active[0], "WIN", 1)
    backup_horse = _annotate(active[1], "BACKUP", 2) if len(active) > 1 else None

    picks = [win_horse]
    if backup_horse:
        picks.append(backup_horse)

    return {
        "win":   win_horse,
        "place": backup_horse,  # legacy key, holds the BACKUP horse for now
        "show":  None,          # explicitly None; Phase 2B will clean up consumers
        "all":   picks,
        "top2":  picks,
    }
'''


def patch_handicapper():
    logger.info("Step 1: Adding top2_picks to core/handicapper.py ...")
    src = HANDICAPPER_FILE.read_text()
    if "TOP2_PICKS_APPLIED" in src or "def top2_picks" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(HANDICAPPER_FILE)

    # Append at the end of the file with a sentinel marker
    new_src = src.rstrip() + "\n\n# TOP2_PICKS_APPLIED\n" + TOP2_PICKS_SOURCE + "\n"
    HANDICAPPER_FILE.write_text(new_src)

    import ast
    ast.parse(HANDICAPPER_FILE.read_text())
    logger.info("  top2_picks function added (syntax OK)")


# ---------------------------------------------------------------------------
# Step 2: Patch builder.py to call top2_picks instead of role_ranked_picks
# ---------------------------------------------------------------------------

def patch_builder_caller():
    logger.info("Step 2: Patching builder.py to use top2_picks ...")
    src = BUILDER_FILE.read_text()
    if "TOP2_CALLER_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return
    backup_file(BUILDER_FILE)

    old_call = (
        '                # Get role-based picks\n'
        '                from core.handicapper import role_ranked_picks\n'
        '                roles = role_ranked_picks(scored)\n'
        '                role_top3 = roles["all"] if roles["all"] else scored[:3]'
    )

    new_call = (
        '                # Top-2 picker (Phase 2A). TOP2_CALLER_APPLIED.\n'
        '                # PLACE/SHOW have been retired; we use top 2 by base score\n'
        '                # for WIN / Exacta / Pick 3 / Pick 4 bets.\n'
        '                from core.handicapper import top2_picks\n'
        '                roles = top2_picks(scored)\n'
        '                role_top3 = roles["all"] if roles["all"] else scored[:2]'
    )

    if old_call not in src:
        logger.error("  Could not locate role_ranked_picks call site; aborting")
        raise SystemExit(1)
    src = src.replace(old_call, new_call)

    BUILDER_FILE.write_text(src)
    import ast
    ast.parse(BUILDER_FILE.read_text())
    logger.info("  builder.py call site patched (syntax OK)")


# ---------------------------------------------------------------------------
# Step 3: Patch the history-render INSERT to log top-2 with new role names
# ---------------------------------------------------------------------------

def patch_history_logging():
    logger.info("Step 3: Patching agent_picks_history role labels in builder.py ...")
    src = BUILDER_FILE.read_text()
    if "TOP2_HISTORY_APPLIED" in src:
        logger.info("  Already patched; skipping")
        return

    # The history block uses _role_names = ["WIN", "PLACE", "SHOW"] and loops
    # over role_top3[:3]. We change to ["WIN", "BACKUP"] and loop over [:2].
    old_block = (
        '                    _role_names = ["WIN", "PLACE", "SHOW"]\n'
        '                    _trigger = "dashboard_render_postrace" if _race_done else "dashboard_render"\n'
        '                    with _get_conn() as _conn:\n'
        '                        for _idx, _pick in enumerate(role_top3[:3]):\n'
    )

    new_block = (
        '                    _role_names = ["WIN", "BACKUP"]  # TOP2_HISTORY_APPLIED\n'
        '                    _trigger = "dashboard_render_postrace" if _race_done else "dashboard_render"\n'
        '                    with _get_conn() as _conn:\n'
        '                        for _idx, _pick in enumerate(role_top3[:2]):\n'
    )

    if old_block not in src:
        logger.warning("  History block not in expected form; skipping (non-fatal)")
        return

    src = src.replace(old_block, new_block)
    BUILDER_FILE.write_text(src)
    import ast
    ast.parse(BUILDER_FILE.read_text())
    logger.info("  History logging updated (WIN/BACKUP labels)")


# ---------------------------------------------------------------------------
# Step 4: Smoke test the new picker
# ---------------------------------------------------------------------------

def smoke_test():
    logger.info("Step 4: Smoke-testing top2_picks ...")
    # Force-reload handicapper since we just patched it
    for mod_name in ("core.handicapper", "core.bolton_chapman"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    from core.handicapper import top2_picks

    # Test 1: Empty input
    r = top2_picks([])
    assert r["win"] is None, "empty input should give None win"
    assert r["top2"] == [], "empty input should give empty top2"
    logger.info("  Test 1 (empty input): PASS")

    # Test 2: Two horses, both with scores
    horses = [
        {
            "program_num": "5",
            "horse_name":  "Test Win Horse",
            "score":       82.5,
            "confidence":  "HIGH",
            "calibrated_prob": 0.35,
            "morning_line": "5/2",
            "track_code":  "CD",
        },
        {
            "program_num": "3",
            "horse_name":  "Test Backup Horse",
            "score":       74.0,
            "confidence":  "MEDIUM",
            "calibrated_prob": 0.18,
            "morning_line": "4/1",
            "track_code":  "CD",
        },
    ]
    r = top2_picks(horses)
    assert r["win"]["program_num"] == "5", "WIN should be horse #5"
    assert r["win"]["role"] == "WIN", "WIN horse should have role=WIN"
    assert r["win"]["rank"] == 1, "WIN should be rank 1"
    assert r["place"]["program_num"] == "3", "BACKUP should be horse #3"
    assert r["place"]["role"] == "BACKUP", "Backup should have role=BACKUP"
    assert r["place"]["rank"] == 2, "Backup should be rank 2"
    assert r["show"] is None, "show should be None (Phase 2A)"
    assert len(r["top2"]) == 2, "top2 should have 2 entries"
    logger.info("  Test 2 (two horses with scores): PASS")

    # Test 3: BC qualification — favorite at 5/2 with 35% prob should qualify
    assert r["win"].get("bc_qualifies") is True, \
        f"WIN should qualify BC, got reason={r['win'].get('bc_reason')}"
    logger.info("  Test 3 (BC qualification): PASS")

    # Test 4: BC rejection — backup at 4/1 with 18% prob: EV=0.9, NEGATIVE_EV
    assert r["place"].get("bc_qualifies") is False, \
        f"Backup should fail BC EV, got reason={r['place'].get('bc_reason')}"
    assert r["place"].get("bc_reason") == "NEGATIVE_EV", \
        f"Backup should fail with NEGATIVE_EV, got {r['place'].get('bc_reason')}"
    logger.info("  Test 4 (BC rejection of weak EV): PASS")

    # Test 5: Single horse only
    r = top2_picks([horses[0]])
    assert r["win"] is not None, "single horse should give a WIN"
    assert r["place"] is None, "single horse should give no backup"
    assert len(r["top2"]) == 1, "top2 should have 1 entry"
    logger.info("  Test 5 (single horse): PASS")

    # Test 6: Zero-score horse filtered out
    horses_with_zero = [
        {"program_num": "1", "score": 0, "confidence": "LOW", "track_code": "CD"},
        {"program_num": "2", "score": 75, "confidence": "HIGH", "track_code": "CD",
         "calibrated_prob": 0.40, "morning_line": "2/1"},
    ]
    r = top2_picks(horses_with_zero)
    assert r["win"]["program_num"] == "2", "zero-score should be filtered"
    logger.info("  Test 6 (zero-score filtering): PASS")

    logger.info("  All 6 smoke tests passed")


def main():
    logger.info("=" * 60)
    logger.info("PHASE 2A MIGRATION: TOP-2 PICKER WITH BC GATING")
    logger.info("=" * 60)

    patch_handicapper()
    patch_builder_caller()
    patch_history_logging()
    smoke_test()

    logger.info("=" * 60)
    logger.info("PHASE 2A COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("What changed:")
    logger.info("  - core/handicapper.py: added top2_picks function")
    logger.info("  - dashboard/builder.py: now calls top2_picks (not role_ranked_picks)")
    logger.info("  - History logging: top-2 with WIN/BACKUP roles (not WIN/PLACE/SHOW)")
    logger.info("  - Every pick is tagged with Bolton-Chapman qualification status")
    logger.info("")
    logger.info("What did NOT change:")
    logger.info("  - place_score, show_score, role_ranked_picks still exist (unused)")
    logger.info("  - Dashboard PLACE/SHOW panels still render (will show BACKUP horse")
    logger.info("    in PLACE slot, empty SHOW slot — visual cleanup in Phase 2B)")
    logger.info("")
    logger.info("Restart racing-agent:")
    logger.info("  cd ~/Documents/racing-agent && nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")


if __name__ == "__main__":
    main()
