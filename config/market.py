"""Market-model blending configuration (Benter Stage 2)."""

# Weight on calibrated model probability in logit blend (0–1).
# Higher = trust fundamentals more; lower = trust the market more.
# Used for the displayed/persisted final_prob (dashboard, agent_picks
# confidence) — this population (mostly rank-1-ish favorites) is what
# the isotonic calibrator is actually validated against.
MARKET_BLEND_ALPHA = 0.65

# Weight on calibrated model probability, used ONLY for edge/Kelly sizing on
# the value-bet / actionable-bet path (second blend in enrich_race_with_market).
# select_actionable_bets() keeps the single largest edge per race per day, which
# is a winner's-curse selection over model/market disagreement — this
# population runs far hotter than MARKET_BLEND_ALPHA assumes even when the
# model is well-calibrated in general. 0.10 was fit against graded actionable-
# bet history via tools/fit_actionable_alpha.py; re-run that script periodically
# as more actionable-bet history accumulates.
ACTIONABLE_BLEND_ALPHA = 0.10

# Pari-mutuel win-pool takeout for edge / Kelly math.
TAKEOUT = 0.18

# Minimum post-takeout edge (fraction) to flag a value bet.
MIN_EDGE = 0.05

# Quarter-Kelly divisor (matches core/kelly.py).
KELLY_DIVISOR = 4

# Skip value bets below this decimal odds (short-priced noise).
VALUE_BET_MIN_DECIMAL = 4.0  # ~3/1

# --- Actionable bet list (Benter-style, selective) ---
ACTIONABLE_MIN_EDGE = 0.15          # 15% post-takeout EV edge minimum
ACTIONABLE_MIN_DECIMAL = 6.0        # 5/1+ only ($2 WIN bleeds on shorter prices)
ACTIONABLE_MAX_PER_DAY = 15         # Cap total actionable bets per card
ACTIONABLE_ONE_PER_RACE = True
ACTIONABLE_MIN_REL_EDGE = 0.50      # (final - market) / market >= 50%
ACTIONABLE_SKIP_HIGH_CHALK = True   # Skip rank-1 HIGH at <= 5/1 (ITM watch only)
ACTIONABLE_HIGH_CHALK_MAX_DEC = 6.0 # 5/1 threshold
ACTIONABLE_PREFER_LIVE = True       # Sort live odds ahead of morning line

# Paper-tracker defaults (flat $2 WIN on every actionable row)
ACTIONABLE_PAPER_STAKE = 2.00
ACTIONABLE_PAPER_DAYS = 7           # Rolling window on dashboard
ACTIONABLE_PAPER_GOAL = 75          # Graded bets before filter review
