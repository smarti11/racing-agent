"""Market-model blending configuration (Benter Stage 2)."""

# Weight on calibrated model probability in logit blend (0–1).
# Higher = trust fundamentals more; lower = trust the market more.
MARKET_BLEND_ALPHA = 0.65

# Pari-mutuel win-pool takeout for edge / Kelly math.
TAKEOUT = 0.18

# Minimum post-takeout edge (fraction) to flag a value bet.
MIN_EDGE = 0.05

# Quarter-Kelly divisor (matches core/kelly.py).
KELLY_DIVISOR = 4

# Skip value bets below this decimal odds (short-priced noise).
VALUE_BET_MIN_DECIMAL = 4.0  # ~3/1
