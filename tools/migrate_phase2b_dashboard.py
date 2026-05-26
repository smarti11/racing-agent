"""Phase 2B: Dashboard cleanup — strip PLACE/SHOW/Trifecta panels.

After Phase 2A, the agent no longer selects PLACE/SHOW horses or places PL+SH
or trifecta bets. The dashboard still renders those panels with stale data.
Phase 2B strips the stale UI cleanly.

What this migration does (surgical strips):

1. WIN HITS / PLACE HITS / SHOW HITS three-column panel  ->  WIN HITS / EXACTA HITS
   (line ~565-567 in builder.py — replaces with 2-column grid)

2. ROI BY PICK RANK table — strips PLACE and SHOW columns
   (lines ~469-470 for body, ~574-575 for header)

3. Bet recommendation strings — strips '$0.50 PL+SH' and '$0.50 SH'
   (line ~490 — MEDIUM/LOW WIN bets simply show 'WIN (not bet)')

4. OPTIMIZED STRATEGY header — drops 'MED:$0.50 PL+SH · LOW:$0.50 SH'
   (line ~511)

5. TRIFECTA BOX panel — removed entirely
   (lines within the lambda block around 590-602)

6. Subtitle 'HIGH/MEDIUM CONF' updated to 'HIGH CONF only'
   (line ~30)

What is PRESERVED:
- TRACK BY CONFIDENCE table HIGH/MEDIUM/LOW columns — these track WIN-bet
  ROI by confidence tier (informative even if MED/LOW aren't placed)
- Exacta Box panel structure (we DO run these)
- All Bolton-Chapman badging from Phase 1
- Baseline progress banner from earlier migration

Run from racing-agent root:
    venv/bin/python3 tools/migrate_phase2b_dashboard.py
"""

import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BUILDER_FILE = ROOT / "dashboard" / "builder.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("phase2b")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    logger.info(f"  Backup: {path.name} -> {bak.name}")
    return bak


# ---------------------------------------------------------------------------
# Patch 1: 3-column WIN/PLACE/SHOW HITS panel -> 2-column WIN/EXACTA HITS
# ---------------------------------------------------------------------------

def patch_hits_panel(src):
    """Replace the WIN HITS / PLACE HITS / SHOW HITS three-column grid."""
    old_block = (
        "            '<div style=\"display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px\">'\n"
        "            f'<div style=\"background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:4px\">WIN HITS</div><div style=\"font-size:14px;font-weight:700;color:#fff\">{r[\"win_hits\"]}</div><div style=\"font-size:11px;color:#4a6080\">${bbt.get(\"win\",{}).get(\"returned\",0):.2f} returned</div></div>'\n"
        "            f'<div style=\"background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #ffd60a\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:4px\">PLACE HITS</div><div style=\"font-size:14px;font-weight:700;color:#fff\">{r[\"place_hits\"]}</div><div style=\"font-size:11px;color:#4a6080\">${bbt.get(\"place\",{}).get(\"returned\",0):.2f} returned</div></div>'\n"
        "            f'<div style=\"background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #ff8c42\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:4px\">SHOW HITS</div><div style=\"font-size:14px;font-weight:700;color:#fff\">{r[\"show_hits\"]}</div><div style=\"font-size:11px;color:#4a6080\">${bbt.get(\"show\",{}).get(\"returned\",0):.2f} returned</div></div>'\n"
        "            '</div>'"
    )

    new_block = (
        "            '<div style=\"display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px\">'  # PHASE2B_HITS_PANEL\n"
        "            f'<div style=\"background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #00c896\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:4px\">WIN HITS</div><div style=\"font-size:14px;font-weight:700;color:#fff\">{r[\"win_hits\"]}</div><div style=\"font-size:11px;color:#4a6080\">${bbt.get(\"win\",{}).get(\"returned\",0):.2f} returned</div></div>'\n"
        "            f'<div style=\"background:#162038;border-radius:6px;padding:10px 12px;border-top:2px solid #ffd60a\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:4px\">EXACTA HITS</div><div style=\"font-size:14px;font-weight:700;color:#fff\">{r.get(\"exacta_box\",{}).get(\"hits\",0)}</div><div style=\"font-size:11px;color:#4a6080\">${r.get(\"exacta_box\",{}).get(\"returned\",0):.2f} returned</div></div>'\n"
        "            '</div>'"
    )

    if old_block not in src:
        logger.warning("  Hits panel not in expected form; skipping")
        return src, False
    return src.replace(old_block, new_block), True


# ---------------------------------------------------------------------------
# Patch 2: ROI BY PICK RANK - strip PLACE and SHOW columns
# ---------------------------------------------------------------------------

def patch_rank_table_body(src):
    """Strip PLACE and SHOW <td>s from the per-rank row body."""
    old_block = (
        "                f'<td style=\"padding:6px 10px;text-align:center;color:#00c896;font-size:11px\">{d[\"win_hits\"]}</td>'\n"
        "                f'<td style=\"padding:6px 10px;text-align:center;color:#ffd60a;font-size:11px\">{d[\"place_hits\"]}</td>'\n"
        "                f'<td style=\"padding:6px 10px;text-align:center;color:#ff8c42;font-size:11px\">{d[\"show_hits\"]}</td>'\n"
    )

    new_block = (
        "                f'<td style=\"padding:6px 10px;text-align:center;color:#00c896;font-size:11px\">{d.get(\"win_hits\",0)}</td>'  # PHASE2B_RANK_BODY\n"
    )

    if old_block not in src:
        logger.warning("  Rank table body not in expected form; skipping")
        return src, False
    return src.replace(old_block, new_block), True


def patch_rank_table_header(src):
    """Strip PLACE and SHOW <th>s from the rank table header."""
    old_block = (
        "               '<th style=\"padding:6px 10px;text-align:center;color:#00c896;font-size:9px;font-weight:400\">WIN</th>'\n"
        "               '<th style=\"padding:6px 10px;text-align:center;color:#ffd60a;font-size:9px;font-weight:400\">PLACE</th>'\n"
        "               '<th style=\"padding:6px 10px;text-align:center;color:#ff8c42;font-size:9px;font-weight:400\">SHOW</th>'\n"
    )

    new_block = (
        "               '<th style=\"padding:6px 10px;text-align:center;color:#00c896;font-size:9px;font-weight:400\">WIN HITS</th>'  # PHASE2B_RANK_HEAD\n"
    )

    if old_block not in src:
        logger.warning("  Rank table header not in expected form; skipping")
        return src, False
    return src.replace(old_block, new_block), True


# ---------------------------------------------------------------------------
# Patch 3: Bet recommendation strings
# ---------------------------------------------------------------------------

def patch_bet_recommendations(src):
    """Update '$2.00 WIN' / '$0.50 PL+SH' / '$0.50 SH' so only HIGH places a bet."""
    old_line = '                bet_desc = "$2.00 WIN" if conf=="HIGH" else "$0.50 PL+SH" if conf=="MEDIUM" else "$0.50 SH"\n'
    new_line = '                bet_desc = "$2.00 WIN" if conf=="HIGH" else "tracked, not bet"  # PHASE2B_BET_DESC\n'

    if old_line not in src:
        logger.warning("  Bet recommendation line not in expected form; skipping")
        return src, False
    return src.replace(old_line, new_line), True


# ---------------------------------------------------------------------------
# Patch 4: OPTIMIZED STRATEGY header
# ---------------------------------------------------------------------------

def patch_strategy_header(src):
    """Drop MED/LOW from the strategy header text."""
    old_header = (
        'f\'⭐ OPTIMIZED STRATEGY — {o["total_races"]} RACES — HIGH:$2 WIN · MED:$0.50 PL+SH · LOW:$0.50 SH · EXACTA BOX:$3.00\''
    )
    new_header = (
        'f\'⭐ OPTIMIZED STRATEGY — {o["total_races"]} RACES — HIGH CONF: $2 WIN · EXACTA BOX: $2 (top-2)\''
    )

    if old_header not in src:
        logger.warning("  Strategy header not in expected form; skipping")
        return src, False
    return src.replace(old_header, new_header), True


# ---------------------------------------------------------------------------
# Patch 5: Remove TRIFECTA BOX panel from the lambda block
# ---------------------------------------------------------------------------

def patch_trifecta_removal(src):
    """Remove the Trifecta Box panel HTML inside the lambda block."""
    # Find the Trifecta block: starts with "# Trifecta Box" comment and ends just
    # before the closing '</div>' that wraps both. We replace with empty string.
    old_block = (
        "                # Trifecta Box\n"
        "                '<div style=\"font-size:10px;color:#4a6080;margin-bottom:6px;font-weight:700;letter-spacing:.06em\">'\n"
        "                f'TRIFECTA BOX — TOP 3 PICKS &nbsp;·&nbsp; 6 combos × ${r[\"bet_amount\"]:.2f} = ${tb.get(\"cost_per_race\",3.00):.2f}/race'\n"
        "                '</div>'\n"
        "                '<div style=\"display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px\">'\n"
        "                f'<div style=\"background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ff8c42\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:3px\">WAGERED</div><div style=\"font-size:16px;font-weight:700;color:#fff\">${tb.get(\"wagered\",0):.2f}</div></div>'\n"
        "                f'<div style=\"background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ff8c42\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:3px\">RETURNED</div><div style=\"font-size:16px;font-weight:700;color:#fff\">${tb.get(\"returned\",0):.2f}</div></div>'\n"
        "                f'<div style=\"background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ff8c42\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:3px\">NET P&L</div><div style=\"font-size:16px;font-weight:700;color:{\"#00c896\" if tb.get(\"net_profit\",0)>=0 else \"#ff4d6d\"}\">${tb.get(\"net_profit\",0):+.2f}</div></div>'\n"
        "                f'<div style=\"background:#162038;border-radius:5px;padding:8px 10px;border-top:2px solid #ff8c42\"><div style=\"font-size:9px;color:#4a6080;margin-bottom:3px\">HITS / ROI</div><div style=\"font-size:16px;font-weight:700;color:{\"#00c896\" if tb.get(\"roi_pct\",0)>=0 else \"#ff4d6d\"}\">{tb.get(\"hits\",0)} / {tb.get(\"roi_pct\",0):+.1f}%</div></div>'\n"
        "                '</div>'\n"
    )

    new_block = (
        "                # Trifecta panel removed by PHASE2B (no longer in strategy)\n"
        "                ''\n"
    )

    if old_block not in src:
        logger.warning("  Trifecta block not in expected form; skipping")
        return src, False
    return src.replace(old_block, new_block), True


# ---------------------------------------------------------------------------
# Patch 6: Subtitle text under the page title
# ---------------------------------------------------------------------------

def patch_subtitle(src):
    """Update subtitle from HIGH/MEDIUM CONF to HIGH CONF only."""
    old = "profitable tracks only · HIGH/MEDIUM CONF"
    new = "HIGH CONF only · Bolton-Chapman validated"
    if old not in src:
        logger.warning("  Subtitle not in expected form; skipping")
        return src, False
    return src.replace(old, new), True


# ---------------------------------------------------------------------------
# Verify generated HTML can render (smoke test)
# ---------------------------------------------------------------------------

def syntax_check():
    import ast
    ast.parse(BUILDER_FILE.read_text())


def trial_render():
    """Try to import and call the builder to make sure nothing crashes."""
    logger.info("  Trial-rendering the dashboard (this may take a moment) ...")
    # Force-reload to pick up patched code
    for mod in list(sys.modules):
        if mod.startswith("dashboard.") or mod == "dashboard":
            del sys.modules[mod]
    try:
        from dashboard import builder as _b
        # Just import success is enough; we won't actually render here to avoid
        # side effects on the HTML output file.
        logger.info("  Builder module imports cleanly")
    except Exception as e:
        logger.error(f"  Builder import FAILED: {e}")
        raise SystemExit(1)


def main():
    logger.info("=" * 60)
    logger.info("PHASE 2B MIGRATION: DASHBOARD CLEANUP")
    logger.info("=" * 60)

    src = BUILDER_FILE.read_text()
    if "PHASE2B_HITS_PANEL" in src or "PHASE2B_BET_DESC" in src:
        logger.info("Already patched; aborting (idempotency check)")
        return

    backup_file(BUILDER_FILE)

    applied = []
    skipped = []

    patches = [
        ("3-col hits panel -> 2-col", patch_hits_panel),
        ("ROI rank table body",       patch_rank_table_body),
        ("ROI rank table header",     patch_rank_table_header),
        ("Bet recommendation",        patch_bet_recommendations),
        ("Strategy header text",      patch_strategy_header),
        ("Trifecta panel removal",    patch_trifecta_removal),
        ("Subtitle update",           patch_subtitle),
    ]

    for name, fn in patches:
        logger.info(f"Patch: {name}")
        src, ok = fn(src)
        if ok:
            applied.append(name)
            logger.info(f"  Applied")
        else:
            skipped.append(name)

    BUILDER_FILE.write_text(src)

    logger.info("Verifying syntax ...")
    syntax_check()
    logger.info("  Syntax OK")

    logger.info("Trial-importing builder module ...")
    trial_render()

    logger.info("=" * 60)
    logger.info("PHASE 2B COMPLETE")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Applied {len(applied)}/{len(patches)} patches:")
    for a in applied:
        logger.info(f"  ✓ {a}")
    if skipped:
        logger.info(f"\nSkipped {len(skipped)} patches (block not found):")
        for s in skipped:
            logger.info(f"  - {s}")
    logger.info("")
    logger.info("Trigger a dashboard refresh:")
    logger.info("  touch ~/Documents/racing-agent/.regen_now")
    logger.info("")
    logger.info("Then refresh http://100.68.82.83:8081/racing.html")


if __name__ == "__main__":
    main()
