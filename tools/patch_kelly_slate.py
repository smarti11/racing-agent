"""Patch racing agent: bet slate Kelly sizing + Pick 3/4 wiring.

Three targeted fixes:
1. Remove AND 1=0 from bet slate query (re-enable history table)
2. Add Kelly-sized bet amounts to bet slate display
3. Wire recommend_sequences_for_date() into main agent cycle

Run from racing-agent root:
    venv/bin/python3 tools/patch_kelly_slate.py
"""

import ast
import logging
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_FILE = ROOT / "db" / "database.py"
BUILDER = ROOT / "dashboard" / "builder.py"
AGENT = ROOT / "racing_agent.py"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("patch_kelly")


def backup(path, suffix=""):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}{suffix}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")


# =========================================================================
# Fix 1: Remove AND 1=0 from bet slate query
# =========================================================================

def fix_bet_slate_query():
    logger.info("Fix 1: Re-enable history table in get_todays_bet_slate()")
    src = DB_FILE.read_text()

    if "HISTORY_REENABLED" in src:
        logger.info("  Already fixed; skipping")
        return

    backup(DB_FILE, suffix="_kelly")

    old = "                  AND 1=0  /* DISABLED: use agent_picks instead */"
    new = "                  AND 1=1  /* HISTORY_REENABLED */"

    if old not in src:
        logger.warning("  AND 1=0 pattern not found — may already be fixed")
        return

    src = src.replace(old, new, 1)
    ast.parse(src)
    DB_FILE.write_text(src)
    logger.info("  History table re-enabled in bet slate query")


# =========================================================================
# Fix 2: Add Kelly column to bet slate render
# =========================================================================

def fix_bet_slate_render():
    logger.info("Fix 2: Add Kelly bet sizing to bet slate render")
    src = BUILDER.read_text()

    if "KELLY_BET_COL" in src:
        logger.info("  Already patched; skipping")
        return

    backup(BUILDER, suffix="_kelly")

    # Add Kelly import at top of builder.py
    old_import = "from datetime import datetime"
    new_import = (
        "from datetime import datetime\n"
        "try:  # KELLY_BET_COL\n"
        "    from core.kelly import kelly_bet, compute_edge\n"
        "    KELLY_AVAILABLE = True\n"
        "except ImportError:\n"
        "    KELLY_AVAILABLE = False\n"
    )
    if old_import in src and "KELLY_BET_COL" not in src:
        src = src.replace(old_import, new_import, 1)
        logger.info("  Kelly import added")

    # Replace the BET column header with KELLY BET
    old_bet_header = "'<th style=\"padding:6px 8px;font-weight:600\">BET</th>'"
    new_bet_header = "'<th style=\"padding:6px 8px;font-weight:600\">KELLY BET</th>'"
    if old_bet_header in src:
        src = src.replace(old_bet_header, new_bet_header, 1)
        logger.info("  BET column header updated to KELLY BET")

    # Find the render loop where bet amount is computed and inject Kelly sizing
    old_bet_cell = (
        "'<td style=\"padding:6px 8px;text-align:center;color:#fff\">'  # BET\n"
        "            f'$2.00</td>'"
    )

    # Try to find where bet cell is rendered — look for $2.00 in the render
    if "'$2.00'" in src or '"$2.00"' in src:
        # Find the pattern and replace with Kelly sizing
        old_two = (
            "f'<td style=\"padding:6px 8px;text-align:center;"
            "color:#fff;font-weight:700\">$2.00</td>'"
        )
        new_two = (
            "# KELLY_BET_COL\n"
            "            if KELLY_AVAILABLE and s.get('win_prob') and s.get('morning_line'):\n"
            "                _kb, _kf, _ke, _do_bet = kelly_bet(\n"
            "                    s['win_prob'], s['morning_line']\n"
            "                )\n"
            "                if _do_bet:\n"
            "                    _bet_color = '#00c896'\n"
            "                    _bet_str = f'${_kb:.2f}'\n"
            "                else:\n"
            "                    _bet_color = '#ff4d6d'\n"
            "                    _bet_str = 'SKIP'\n"
            "            else:\n"
            "                _bet_color = '#4a6080'\n"
            "                _bet_str = '$2.00'\n"
            "            _bet_cell = (f'<td style=\"padding:6px 8px;text-align:center;'\n"
            "                         f'color:{_bet_color};font-weight:700\">{_bet_str}</td>')\n"
            "            f'{_bet_cell}'"
        )
        if old_two in src:
            src = src.replace(old_two, new_two, 1)
            logger.info("  Kelly bet cell injected into render loop")
        else:
            logger.warning("  $2.00 cell pattern not found — bet column not updated")
            logger.warning("  Manual review of render_bet_slate_html() needed")

    ast.parse(src)
    BUILDER.write_text(src)
    logger.info("  builder.py patched")


# =========================================================================
# Fix 3: Wire Pick 3/4 into main agent cycle (if not already)
# =========================================================================

def fix_pick34_wiring():
    logger.info("Fix 3: Verify Pick 3/4 wiring in racing_agent.py")
    src = AGENT.read_text()

    if "PICK34_WIRED" in src:
        logger.info("  Already wired; skipping")
        return

    backup(AGENT, suffix="_kelly")

    # Add Pick 3/4 call before build_dashboard()
    old = (
        "    from dashboard.builder import build_dashboard\n"
        "    build_dashboard()"
    )
    new = (
        "    # PICK34_WIRED: Generate Pick 3/4 sequence recommendations\n"
        "    try:\n"
        "        from core.pick4_picker import recommend_sequences_for_date\n"
        "        from datetime import date as _dt\n"
        "        _recs = recommend_sequences_for_date(\n"
        "            _dt.today().isoformat(), verbose=False\n"
        "        )\n"
        "        _n_rec = sum(1 for _r in _recs if _r.get('recommended'))\n"
        "        if _n_rec > 0:\n"
        "            logger.info(f'Pick 3/4: {_n_rec} recommended sequences')\n"
        "    except Exception as _e:\n"
        "        logger.warning(f'Pick 3/4 failed: {_e}')\n"
        "\n"
        "    from dashboard.builder import build_dashboard\n"
        "    build_dashboard()"
    )

    if old not in src:
        logger.warning("  build_dashboard() anchor not found — Pick 3/4 not wired")
        return

    src = src.replace(old, new, 1)
    ast.parse(src)
    AGENT.write_text(src)
    logger.info("  Pick 3/4 wired into generate_dashboard()")


# =========================================================================
# Main
# =========================================================================

def main():
    logger.info("=" * 60)
    logger.info("KELLY + BET SLATE + PICK34 PATCH")
    logger.info("=" * 60)

    fix_bet_slate_query()
    fix_bet_slate_render()
    fix_pick34_wiring()

    logger.info("")
    logger.info("=" * 60)
    logger.info("DONE")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next:")
    logger.info("  1. Copy kelly.py to ~/Documents/racing-agent/core/kelly.py")
    logger.info("  2. Restart agent:")
    logger.info("     pkill -f racing_agent.py && sleep 2 && \\")
    logger.info("     cd ~/Documents/racing-agent && \\")
    logger.info("     nohup venv/bin/python3 racing_agent.py > /dev/null 2>&1 &")


if __name__ == "__main__":
    main()
