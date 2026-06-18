"""
Handicapping Engine — Phase 3
================================
Scores each horse using multiple factors including:
- Speed figure estimate (from morning line odds)
- Jockey win % (from our DB + elite list)
- Trainer win % (from our DB + elite list)
- Class level
- Pace scenario adjustment
- Form (last 3 finishes, days since last race)
- Class drop/rise
- Trainer hot/cold streak
"""

import logging
from core.speed_figures import odds_to_speed_figure, parse_odds, get_class_base
from data.speed_calc import compute_speed_figure as calc_speed_fig
from core.pace import analyze_pace_scenario, pace_scenario_score_adjustment
from core.form import get_full_form_analysis, get_jockey_stats_from_db, get_trainer_stats_from_db
from config.settings import (
    SPEED_FIGURE_WEIGHT, JOCKEY_WEIGHT, TRAINER_WEIGHT,
    CLASS_WEIGHT, PACE_WEIGHT
)
from config.meet_leaders import (
    ORTIZ_CD_TRACK, ORTIZ_CD_MULTIPLIER, ORTIZ_CD_VARIANTS,
    MEET_LEADERS, MEET_LEADER_MULTIPLIER,
    WEAK_SIGNAL_TRACKS,
)

logger = logging.getLogger("racing_agent")

DEFAULT_JOCKEY_WIN_PCT  = 0.12
DEFAULT_TRAINER_WIN_PCT = 0.15

# Updated April 2026 — based on 2025 full season + 2026 spring meet results
ELITE_JOCKEYS = {
    # Tier 1 — National Elite (27%+ win rate)
    "irad ortiz":           0.28, "irad ortiz jr":        0.28,
    "irad ortiz, jr":       0.28, "irad ortiz jr.":       0.28,
    "flavien prat":         0.22, "jose ortiz":           0.23,
    "jose l. ortiz":        0.23, "jose l ortiz":         0.23,
    "luis saez":            0.22,

    # Tier 2 — National Stars (18-22%)
    "paco lopez":           0.19, "joel rosario":         0.19,
    "tyler gaffalione":     0.20, "mychel sanchez":       0.18,
    "mychel j. sanchez":    0.18, "brian hernandez":      0.19,
    "brian hernandez jr":   0.19, "brian j. hernandez":   0.19,
    "florent geroux":       0.19, "john velazquez":       0.19,
    "javier castellano":    0.20, "junior alvarado":      0.18,
    "kendrick carmouche":   0.17, "manny franco":         0.19,
    "manuel franco":        0.19, "dylan davis":          0.16,
    "dylan davis jr":       0.16, "ricardo santana":      0.19,
    "ricardo santana jr":   0.19, "luis m. ocasio":       0.16,
    "luis m ocasio":        0.16,

    # Tier 3 — Track Specialists (14-17%)
    "ruben silvera":        0.16, "agustin gomez":        0.15,
    "luan machado":         0.16, "jaime rodriguez":      0.15,
    "sahin civaci":         0.15, "evin roman":           0.14,
    "evin a. roman":        0.14, "summer pauly":         0.14,
    "juan hernandez":       0.17, "juan j. hernandez":    0.17,
    "tiago pereira":        0.16, "tiago josue pereira":  0.16,
    "emisael jaramillo":    0.16, "jose lezcano":         0.15,
    "santiago gonzalez":    0.14,
    "mitchell murrill":     0.14, "samy camacho":         0.15,
    "jairon velazquez":     0.14, "jareth loveberry":     0.15,
    "adam beschizza":       0.14, "oscar villarreal":     0.14,
    "leandro goncalves":    0.15, "leandro d. goncalves": 0.15,
    "edgar paucar":         0.14, "edgard zayas":         0.15,
    "edgard j. zayas":      0.15, "jockey kyle frey":     0.15,
    "kyle frey":            0.15, "joe bravo":            0.14,
    "hector berrios":       0.14, "jorge ruiz":           0.14,
    "edgar perez":          0.14, "david boraco":         0.14,
    "mirco demuro":         0.17, "welfin orantes":       0.13,
    "antonio fresu":        0.15, "armando ayuso":        0.14,
    "kazushi kimura":       0.15,
}

# Updated April 2026 — based on 2025 full season + 2026 spring meet results
ELITE_TRAINERS = {
    # Tier 1 — National Elite (25%+ win rate)
    "chad brown":           0.31, "chad c. brown":        0.31,
    "chad c brown":         0.31, "bob baffert":          0.29,
    "brad cox":             0.26, "todd pletcher":        0.26,
    "todd a. pletcher":     0.26, "todd a pletcher":      0.26,
    "wesley ward":          0.25,

    # Tier 2 — National Stars (20-25%)
    "mark casse":           0.23, "bill mott":            0.22,
    "william mott":         0.22, "saffie joseph":        0.22,
    "saffie a. joseph":     0.22, "saffie a. joseph jr":  0.22,
    "saffie joseph jr":     0.22, "javier negrete":       0.20,
    "mike maker":           0.21, "brendan walsh":        0.20,
    "graham motion":        0.19, "shug mcgaughey":       0.20,
    "steve asmussen":       0.19, "steven m. asmussen":   0.19,
    "steven asmussen":      0.19, "kenny mcpeek":         0.21,
    "kenneth mcpeek":       0.21, "dale romans":          0.19,
    "doug o'neill":         0.19, "philip d'amato":       0.20,
    "philip d amato":       0.20, "richard mandella":     0.21,
    "richard e. mandella":  0.21, "victor barboza":       0.20,
    "victor barboza jr":    0.20, "antonio sano":         0.19,
    "linda rice":           0.17,

    # Tier 3 — Track Specialists (14-19%)
    "michael mccarthy":     0.19, "michael w. mccarthy":  0.19,
    "richard baltas":       0.18, "john shirreffs":       0.17,
    "larry jones":          0.17, "rudy rodriguez":       0.16,
    "rey hernandez":        0.15, "thomas morley":        0.14,
    "israel acevedo":       0.14, "sergio donjuan":       0.15,
    "amelia green":         0.14, "michel douaihy":       0.14,
    "james ferraro":        0.15, "chad summers":         0.15,
    "daniel velazquez":     0.15, "ben colebrook":        0.16,
    "tim yakteen":          0.18,
    "jeff mullins":         0.18, "steve knapp":          0.15,
    "steve r. knapp":       0.15, "genaro vallejo":       0.14,
    "heather smullen":      0.15, "gustavo delgado":      0.15,
    "fernando abreu":       0.16, "ruben gomez":          0.14,
    "tim pletcher":         0.18, "mark glatt":           0.17,
    "peter eurton":         0.17, "craig lewis":          0.15,
    "andy mathis":          0.15, "edward freeman":       0.14,
    "juan hernandez":       0.16, "rudy rodriguez":       0.15,
    "timothy hills":        0.15, "leon mckannas":        0.14,
    "garrett arscott":      0.14, "victor barboza, jr.":  0.20,
    "michael trombetta":    0.17, "scott lake":           0.16,
    "kathleen demasi":      0.15, "rob bailes":           0.15,
    "uriah st. lewis":      0.14, "mary pattershall":     0.14,
    "martin thompson":      0.15, "dick cappellucci":     0.15,
    "justin evans":         0.15, "simon buechler":       0.14,
    "robertino diodoro":    0.16, "jose gonzalez":        0.14,
    "lyle johnston":        0.15, "scott young":          0.15,
    "mark buehrer":         0.14, "juan padilla":         0.14,
}


def get_jockey_win_pct(jockey_name: str) -> float:
    if not jockey_name:
        return DEFAULT_JOCKEY_WIN_PCT
    # Try our DB first
    db_stats = get_jockey_stats_from_db(jockey_name)
    if db_stats.get("win_pct") is not None and db_stats.get("starts", 0) >= 5:
        return db_stats["win_pct"] / 100
    # Fall back to elite list
    name_lower = jockey_name.lower().strip()
    for known, pct in ELITE_JOCKEYS.items():
        if known in name_lower or name_lower in known:
            return pct
    return DEFAULT_JOCKEY_WIN_PCT


def get_trainer_win_pct(trainer_name: str) -> float:
    if not trainer_name:
        return DEFAULT_TRAINER_WIN_PCT
    db_stats = get_trainer_stats_from_db(trainer_name)
    if db_stats.get("win_pct") is not None and db_stats.get("starts", 0) >= 5:
        return db_stats["win_pct"] / 100
    name_lower = trainer_name.lower().strip()
    for known, pct in ELITE_TRAINERS.items():
        if known in name_lower or name_lower in known:
            return pct
    return DEFAULT_TRAINER_WIN_PCT


def _matches_jockey_variants(jockey_name: str, variants: list) -> bool:
    """Substring match both ways — catches 'Irad Ortiz' in 'Irad Ortiz, Jr.' and vice versa."""
    name = jockey_name.lower().strip()
    return any(v in name or name in v for v in variants)


def _apply_jockey_boosts(horse: dict, track_code: str) -> None:
    """
    Apply CD Ortiz boost (×1.30) and/or meet-leader boost (×1.20) to horse["score"].
    Both multipliers compound when the same horse qualifies for both.
    Emits a DEBUG log line each time a multiplier fires.
    """
    jockey     = horse.get("jockey", "")
    horse_name = horse.get("horse_name", "")
    base_score = horse["score"]

    ortiz_fired  = False
    leader_fired = False

    if track_code == ORTIZ_CD_TRACK and _matches_jockey_variants(jockey, ORTIZ_CD_VARIANTS):
        horse["score"] = round(horse["score"] * ORTIZ_CD_MULTIPLIER, 1)
        ortiz_fired = True

    meet_variants = MEET_LEADERS.get(track_code, [])
    if meet_variants and _matches_jockey_variants(jockey, meet_variants):
        horse["score"] = round(horse["score"] * MEET_LEADER_MULTIPLIER, 1)
        leader_fired = True

    horse["score"] = min(100.0, horse["score"])

    if ortiz_fired or leader_fired:
        applied = []
        if ortiz_fired:
            applied.append(f"OrtizCD×1.30")
        if leader_fired:
            applied.append(f"MeetLeader×1.20")
        compound_note = " [COMPOUNDED]" if (ortiz_fired and leader_fired) else ""
        logger.debug(
            "[JOCKEY BOOST]%s horse=%r jockey=%r track=%s "
            "base=%.1f multiplier=%s final=%.1f",
            compound_note, horse_name, jockey, track_code,
            base_score, "+".join(applied), horse["score"],
        )


def form_score_adjustment(form_data: dict) -> float:
    """
    Score adjustment based on form factors.
    Returns -15 to +15 adjustment.
    """
    adj = 0.0

    # Last 3 finishes
    form = form_data.get("form", "---")
    if form != "---":
        parts = form.split("-")
        for i, finish in enumerate(parts[:3]):
            weight = 1.0 - (i * 0.25)  # most recent counts more
            try:
                f = int(finish.replace("+", ""))
                if f == 1:
                    adj += 4 * weight
                elif f == 2:
                    adj += 2 * weight
                elif f == 3:
                    adj += 1 * weight
                elif f >= 5:
                    adj -= 2 * weight
            except Exception:
                pass

    # Class change
    class_change = form_data.get("class_change", "UNKNOWN")
    if class_change == "DROP":
        adj += 4   # Dropping in class is a positive
    elif class_change == "RISE":
        adj -= 3   # Rising in class is harder

    # Layoff
    layoff = form_data.get("layoff_flag", "UNKNOWN")
    if layoff == "FRESH":
        adj += 1   # Sharp and ready
    elif layoff == "LAYOFF":
        adj -= 2   # 31-60 days
    elif layoff == "LONG_LAYOFF":
        adj -= 4   # 60+ days, rust factor

    # Trainer hot/cold
    trainer_hot = form_data.get("trainer_hot", "UNKNOWN")
    if trainer_hot == "HOT":
        adj += 3
    elif trainer_hot == "COLD":
        adj -= 2

    return round(max(-15, min(15, adj)), 1)


def score_horse(entry: dict, conditions: str, field_size: int,
                pace_scenario: dict = None, form_data: dict = None) -> dict:
    """Score a single horse on 0-100 scale."""

    prog    = entry.get("program_num", "?")
    horse   = entry.get("horse_name", "")
    ml      = entry.get("morning_line", "") or ""
    post    = int(entry.get("post_position") or entry.get("program_num") or prog or 1)

    # Fix jockey/trainer if merged
    jockey  = entry.get("jockey", "") or ""
    trainer = entry.get("trainer", "") or ""
    if "Trainer:" in jockey:
        parts = jockey.split("Trainer:")
        jockey  = parts[0].strip()
        trainer = parts[1].strip() if len(parts) > 1 else trainer

    # 1. Speed figure — try real chart-based figure first, fall back to ML
    real_fig = None
    try:
        from db.database import get_horse_speed_figure
        real_fig = get_horse_speed_figure(horse)
    except Exception:
        pass
    if real_fig is not None:
        speed_fig = real_fig
        speed_source = "CHART"
    else:
        speed_fig = odds_to_speed_figure(ml, conditions or "")
        speed_source = "ML"
    speed_norm = min(1.0, speed_fig / 110.0)

    # 2. Jockey
    jock_pct   = get_jockey_win_pct(jockey)
    jock_norm  = min(1.0, jock_pct / 0.35)

    # 3. Trainer
    train_pct  = get_trainer_win_pct(trainer)
    train_norm = min(1.0, train_pct / 0.35)

    # 4. Class
    class_base = get_class_base(conditions or "")
    class_norm = min(1.0, class_base / 110.0)

    # 5. Pace — use scenario if available, else fall back to post position
    if pace_scenario and pace_scenario.get("pace_styles"):
        pace_style = pace_scenario["pace_styles"].get(str(prog), "P")
        p_score = {"E": 0.75, "EP": 0.70, "P": 0.65, "S": 0.55, "C": 0.45, "U": 0.55}.get(pace_style, 0.55)
    else:
        from core.speed_figures import parse_odds as _po
        p_score = 0.55

    # Weighted base score
    raw_score = (
        speed_norm  * SPEED_FIGURE_WEIGHT +
        jock_norm   * JOCKEY_WEIGHT       +
        train_norm  * TRAINER_WEIGHT      +
        class_norm  * CLASS_WEIGHT        +
        p_score     * PACE_WEIGHT
    )
    base_score = raw_score * 100

    # Jockey-Trainer combo bonus
    jt_combo = None
    try:
        from db.database import get_jt_combo_stats
        jt_combo = get_jt_combo_stats(jockey, trainer)
        if jt_combo and jt_combo["starts"] >= 5 and jt_combo["win_pct"] >= 25:
            base_score += 3  # Strong J/T combo bonus
        elif jt_combo and jt_combo["starts"] >= 3 and jt_combo["win_pct"] >= 20:
            base_score += 1  # Moderate J/T combo bonus
    except Exception:
        pass

    # Pace scenario adjustment
    pace_adj = 0.0
    if pace_scenario:
        pace_adj = pace_scenario_score_adjustment(str(prog), pace_scenario)

    # Form adjustment
    form_adj = 0.0
    if form_data:
        form_adj = form_score_adjustment(form_data)

    # Final score
    final_score = round(base_score + pace_adj + form_adj, 1)
    final_score = max(0, min(100, final_score))

    # Value rating
    ml_decimal = parse_odds(ml)
    if ml_decimal is not None:
        implied_prob = 1 / (ml_decimal + 1)
        score_prob   = raw_score
        value = round((score_prob - implied_prob) * 100, 1)
    else:
        value = 0.0

    # Get form string for display
    form_str    = form_data.get("form", "---") if form_data else "---"
    days_since  = form_data.get("days_since") if form_data else None
    layoff_flag = form_data.get("layoff_flag", "") if form_data else ""
    class_change = form_data.get("class_change", "") if form_data else ""
    trainer_hot  = form_data.get("trainer_hot", "") if form_data else ""
    j_win_pct    = form_data.get("j_win_pct") if form_data else None
    t_win_pct    = form_data.get("t_win_pct") if form_data else None

    pace_style_display = ""
    if pace_scenario and pace_scenario.get("pace_styles"):
        pace_style_display = pace_scenario["pace_styles"].get(str(prog), "P")

    return {
        "program_num":    prog,
        "horse_name":     horse,
        "jockey":         jockey,
        "trainer":        trainer,
        "morning_line":   ml,
        "score":          final_score,
        "speed_fig":      round(speed_fig, 1),
        "jock_pct":       round(jock_pct * 100, 1),
        "train_pct":      round(train_pct * 100, 1),
        "j_win_pct_db":   j_win_pct,
        "t_win_pct_db":   t_win_pct,
        "pace_role":      pace_style_display or "P",
        "pace_adj":       pace_adj,
        "form_adj":       form_adj,
        "form":           form_str,
        "days_since":     days_since,
        "layoff_flag":    layoff_flag,
        "class_change":   class_change,
        "trainer_hot":    trainer_hot,
        "value":          value,
    }


def handicap_race(entries: list, conditions: str = "", track_code: str = "",
                  distance_str: str = "") -> list:
    """Score all horses and return ranked list."""
    active     = [e for e in entries if not e.get("scratched")]
    field_size = len(active)
    if field_size == 0:
        return []

    # Analyze pace scenario for entire field
    pace_scenario = analyze_pace_scenario(active, distance_str, track_code)

    scores = []
    for entry in active:
        try:
            # Get form data
            horse = entry.get("horse_name", "")
            form_data = get_full_form_analysis(dict(entry), conditions)

            result = score_horse(
                dict(entry), conditions, field_size,
                pace_scenario=pace_scenario,
                form_data=form_data
            )
            result["pace_scenario"] = pace_scenario
            result["track_code"] = track_code
            scores.append(result)
        except Exception as ex:
            logger.warning(f"Scoring error for {entry.get('horse_name')}: {ex}")

    # Apply jockey score boosts before ranking so boosted scores drive sort order
    # TEMPORARILY DISABLED 2026-05-02 — caused agent to loop on large cards
    # for horse in scores:
    #     _apply_jockey_boosts(horse, track_code)

    scores.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(scores):
        s["rank"] = i + 1

    return scores


def get_top_pick(scored_horses: list) -> dict:
    if not scored_horses:
        return None
    top = scored_horses[0]
    if len(scored_horses) > 1:
        gap = top["score"] - scored_horses[1]["score"]
        confidence = "HIGH" if gap >= 8 else "MEDIUM" if gap >= 4 else "LOW"
    else:
        confidence = "HIGH"
    return {**top, "confidence": confidence}


def get_value_picks(scored_horses: list, min_odds: float = 3.0) -> list:
    value_picks = []
    for horse in scored_horses:
        ml = parse_odds(horse.get("morning_line", ""))
        if ml and ml >= min_odds and horse.get("value", 0) > 2.0:
            value_picks.append(horse)
    return value_picks


# ── Role-Based Ranking ─────────────────────────────────────────────────────

def place_score(horse: dict, win_pick_prog: str) -> float:
    """
    Score a horse for PLACE (2nd place) probability.
    Favors pressers/stalkers that run competitively but get beat.
    Penalizes the WIN pick (already assigned) and extreme longshots.
    """
    if str(horse.get("program_num","")) == str(win_pick_prog):
        return -999  # Already assigned as WIN pick

    base  = horse.get("score", 50)
    role  = horse.get("pace_role", "P")
    ml    = parse_odds(horse.get("morning_line",""))
    value = horse.get("value", 0)

    # Pace role adjustments for PLACE
    # Pressers and stalkers run 2nd most often
    role_adj = {"E": -3, "EP": +2, "P": +5, "S": +8, "C": +3, "U": 0}.get(role, 0)

    # Odds adjustment — mid-range odds (2/1 to 8/1) place most
    odds_adj = 0
    if ml is not None:
        if 1.5 <= ml <= 8.0:
            odds_adj = +4
        elif ml > 15.0:
            odds_adj = -5  # Longshots rarely place

    # Form adjustment — horses with recent 2nd place finishes
    form = horse.get("form", "---")
    form_adj = 0
    if form != "---":
        parts = form.split("-")
        if len(parts) > 0 and parts[0] == "2":
            form_adj = +3
        if len(parts) > 1 and parts[1] == "2":
            form_adj = +2

    return base + role_adj + odds_adj + form_adj


def show_score(horse: dict, win_prog: str, place_prog: str) -> float:
    """
    Score a horse for SHOW (3rd place) probability.
    Favors closers, class droppers, consistent horses.
    Penalizes already-assigned WIN and PLACE picks.
    """
    prog = str(horse.get("program_num",""))
    if prog in {str(win_prog), str(place_prog)}:
        return -999  # Already assigned

    base  = horse.get("score", 50)
    role  = horse.get("pace_role", "P")
    ml    = parse_odds(horse.get("morning_line",""))
    class_change = horse.get("class_change", "")

    # Closers pick up show checks frequently
    role_adj = {"E": -5, "EP": 0, "P": +2, "S": +5, "C": +8, "U": 0}.get(role, 0)

    # Class droppers show more often
    class_adj = +4 if class_change == "DROP" else 0

    # Wider odds range for show — up to 15/1
    odds_adj = 0
    if ml is not None:
        if 2.0 <= ml <= 15.0:
            odds_adj = +3
        elif ml > 20.0:
            odds_adj = -4

    # Form — any recent top-3 finish
    form = horse.get("form", "---")
    form_adj = 0
    if form != "---":
        parts = form.split("-")
        for f in parts[:2]:
            try:
                if int(f.replace("+","")) <= 3:
                    form_adj += 2
                    break
            except Exception:
                pass

    return base + role_adj + class_adj + odds_adj + form_adj


def role_ranked_picks(scored_horses: list) -> dict:
    """
    Assign horses to WIN, PLACE, SHOW roles optimally.

    Returns:
        {
          "win":   {horse dict with role="WIN",  confidence="HIGH/MEDIUM/LOW"},
          "place": {horse dict with role="PLACE"},
          "show":  {horse dict with role="SHOW"},
          "all":   [win, place, show]  ← for dashboard top 3 panel
        }
    """
    if not scored_horses:
        return {"win": None, "place": None, "show": None, "all": []}

    active = [h for h in scored_horses if h.get("score", 0) > 0]
    if not active:
        return {"win": None, "place": None, "show": None, "all": []}

    # ── Weak-signal track confidence floor ────────────────────────────────
    _tc = active[0].get("track_code", "")
    if _tc in WEAK_SIGNAL_TRACKS:
        _conf = active[0].get("confidence", "LOW")
        if _conf != "HIGH":
            logger.info(
                "[WEAK TRACK SKIP] track=%s horse=%r jockey=%r confidence=%s — "
                "skipping (only HIGH CONF bets placed at weak-signal tracks)",
                _tc, active[0].get("horse_name"), active[0].get("jockey"), _conf,
            )
            return {"win": None, "place": None, "show": None, "all": []}

    # ── Step 1: WIN — highest overall score ──────────────────────────────
    win_horse = active[0].copy()
    win_horse["role"] = "WIN"
    win_horse["bet_recommendation"] = "$2.00 WIN" if win_horse.get("confidence") == "HIGH" else \
                                       "$0.50 PL+SH" if win_horse.get("confidence") == "MEDIUM" else \
                                       "$0.50 SHOW"

    win_prog = str(win_horse.get("program_num",""))

    # ── Step 2: PLACE — best PLACE candidate excluding WIN pick ──────────
    place_candidates = [(place_score(h, win_prog), h) for h in active]
    place_candidates.sort(key=lambda x: x[0], reverse=True)
    place_horse = place_candidates[0][1].copy() if place_candidates else None
    place_prog  = str(place_horse.get("program_num","")) if place_horse else ""

    if place_horse:
        place_horse["role"]              = "PLACE"
        place_horse["bet_recommendation"] = "$0.50 PLACE"
        # Calculate place confidence based on score gap
        if len(place_candidates) > 1:
            gap = place_candidates[0][0] - place_candidates[1][0]
            place_horse["place_confidence"] = "HIGH" if gap >= 8 else "MEDIUM" if gap >= 4 else "LOW"
        else:
            place_horse["place_confidence"] = "HIGH"

    # ── Step 3: SHOW — best SHOW candidate excluding WIN and PLACE ───────
    show_candidates = [(show_score(h, win_prog, place_prog), h) for h in active]
    show_candidates.sort(key=lambda x: x[0], reverse=True)
    show_horse = show_candidates[0][1].copy() if show_candidates else None

    if show_horse:
        show_horse["role"]               = "SHOW"
        show_horse["bet_recommendation"] = "$0.50 SHOW"
        if len(show_candidates) > 1:
            gap = show_candidates[0][0] - show_candidates[1][0]
            show_horse["show_confidence"] = "HIGH" if gap >= 8 else "MEDIUM" if gap >= 4 else "LOW"
        else:
            show_horse["show_confidence"] = "HIGH"

    all_picks = [p for p in [win_horse, place_horse, show_horse] if p]

    # Assign ranks 1, 2, 3
    for i, p in enumerate(all_picks):
        p["rank"] = i + 1

    return {
        "win":   win_horse,
        "place": place_horse,
        "show":  show_horse,
        "all":   all_picks,
    }

# TOP2_PICKS_APPLIED


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

    win_horse    = _annotate(active[0], "WIN",    1)
    backup_horse = _annotate(active[1], "BACKUP", 2) if len(active) > 1 else None
    show_horse   = _annotate(active[2], "SHOW",   3) if len(active) > 2 else None

    picks = [win_horse]
    if backup_horse:
        picks.append(backup_horse)
    if show_horse:
        picks.append(show_horse)

    return {
        "win":   win_horse,
        "place": backup_horse,
        "show":  show_horse,
        "all":   picks,
        "top2":  picks[:2],
        "top3":  picks,
    }

