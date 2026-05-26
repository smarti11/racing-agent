"""Kelly criterion bet sizing for racing agent.

Based on Kelly (1956) "A New Interpretation of Information Rate."

CONSERVATIVE IMPLEMENTATION:
- Quarter Kelly (f*/4) to reduce variance during baseline building
- Hard minimum: $2 (track minimum)
- Hard maximum: $20 (caps catastrophic single-race loss)
- Requires positive edge after pari-mutuel takeout
- Returns 0 (don't bet) when edge is negative

EDGE CALCULATION:
  edge = win_prob * decimal_odds - 1
  where decimal_odds = (1 - takeout) * (num/denom + 1)

  Example: 5/1 odds, 18% takeout, 25% win prob:
    decimal_net = (1 - 0.18) * (5 + 1) = 4.92
    edge = 0.25 * 4.92 - 1 = 0.23  (23% positive edge → bet)

KELLY FRACTION:
  b = decimal_net - 1  (net profit per $1 risked)
  f* = (b * p - q) / b
  f_kelly = f* / 4    (quarter Kelly)
  bet = bankroll * f_kelly

HONEST LIMITATIONS:
- win_prob is softmax output, not a calibrated probability
  Until isotonic calibrator has enough data, treat edge as directional
  signal only, not precise sizing
- Morning line is pre-race estimate; actual tote odds may differ
- Pari-mutuel takeout varies by track and pool (15-22%)
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# Configuration — tune these without touching the math
# ============================================================

TAKEOUT = 0.18          # Pari-mutuel takeout rate (18% typical win pool)
KELLY_DIVISOR = 4       # Quarter Kelly — conservative baseline building
BANKROLL = 500.00       # Paper trading bankroll
MIN_BET = 2.00          # Track minimum
MAX_BET = 20.00         # Hard cap per race
MIN_EDGE = 0.05         # Minimum 5% edge required before betting
MIN_WIN_PROB = 0.10     # Bolton-Chapman pmin floor


def parse_odds_to_decimal(odds_str: str) -> Optional[float]:
    """Convert odds string to decimal (total return per $1 bet).

    Examples:
        '5/1'  -> 6.0   (win $5 + $1 stake = $6 total)
        '5-1'  -> 6.0
        '9/2'  -> 5.5
        '2/5'  -> 1.4
        '1/2'  -> 1.5
        'evs'  -> 2.0
        '6'    -> 7.0   (6/1)
    """
    if not odds_str:
        return None
    s = str(odds_str).strip().lower()

    # Even money
    if s in ('evs', 'even', 'e/v', '1/1'):
        return 2.0

    # Fraction: 5/2, 9/2, 2/5 etc.
    m = re.match(r'^(\d+\.?\d*)\s*[/\-]\s*(\d+\.?\d*)$', s)
    if m:
        num = float(m.group(1))
        denom = float(m.group(2))
        if denom == 0:
            return None
        return (num / denom) + 1.0

    # Plain number: treat as X/1
    try:
        x = float(s)
        if x <= 0:
            return None
        return x + 1.0
    except ValueError:
        return None


def implied_prob_from_odds(odds_str: str) -> Optional[float]:
    """Market implied win probability from morning line odds.

    Accounts for the fact that morning line is set without takeout
    (it's a price guide, not a pool). We apply takeout adjustment
    to get a fair-value implied probability.
    """
    decimal = parse_odds_to_decimal(odds_str)
    if decimal is None or decimal <= 0:
        return None
    # Raw implied prob
    raw = 1.0 / decimal
    # Adjust for takeout: market overround means implied probs sum > 1
    # We deflate by (1 - takeout) to get fair-value estimate
    return raw / (1.0 - TAKEOUT)


def compute_edge(win_prob: float, odds_str: str,
                 takeout: float = TAKEOUT) -> Optional[float]:
    """Compute expected edge after takeout.

    Returns edge as a fraction (0.23 = 23% edge).
    Negative means house has the edge — don't bet.

    Formula:
        b_net = (decimal - 1) * (1 - takeout)
        edge  = win_prob * (b_net + 1) - 1
              = win_prob * decimal * (1-takeout) - 1
    """
    decimal = parse_odds_to_decimal(odds_str)
    if decimal is None or win_prob is None:
        return None
    if win_prob <= 0 or win_prob >= 1:
        return None
    edge = win_prob * decimal * (1.0 - takeout) - 1.0
    return edge


def kelly_fraction(win_prob: float, odds_str: str,
                   takeout: float = TAKEOUT,
                   divisor: int = KELLY_DIVISOR) -> float:
    """Compute Kelly fraction (portion of bankroll to bet).

    Returns 0.0 if edge is negative or inputs are invalid.
    """
    decimal = parse_odds_to_decimal(odds_str)
    if decimal is None or win_prob is None:
        return 0.0
    if win_prob < MIN_WIN_PROB:
        return 0.0

    b_net = (decimal - 1.0) * (1.0 - takeout)
    if b_net <= 0:
        return 0.0

    q = 1.0 - win_prob
    f_star = (b_net * win_prob - q) / b_net

    if f_star <= 0:
        return 0.0

    return f_star / divisor


def kelly_bet(win_prob: float,
              odds_str: str,
              bankroll: float = BANKROLL,
              takeout: float = TAKEOUT,
              divisor: int = KELLY_DIVISOR,
              min_bet: float = MIN_BET,
              max_bet: float = MAX_BET,
              min_edge: float = MIN_EDGE) -> Tuple[float, float, float, bool]:
    """Compute Kelly-sized bet amount.

    Returns:
        (bet_amount, kelly_f, edge, should_bet)

    should_bet is False when:
        - Edge is negative (house advantage)
        - Edge is below min_edge threshold
        - win_prob below Bolton-Chapman pmin floor
        - Odds string unparseable
    """
    edge = compute_edge(win_prob, odds_str, takeout)
    f = kelly_fraction(win_prob, odds_str, takeout, divisor)

    if edge is None or edge < min_edge or f <= 0:
        return 0.0, 0.0, edge or 0.0, False

    raw_bet = bankroll * f
    bet = max(min_bet, min(max_bet, round(raw_bet, 2)))

    return bet, f, edge, True


def kelly_summary(win_prob: float, odds_str: str,
                  bankroll: float = BANKROLL) -> dict:
    """Return full Kelly analysis dict for display on dashboard."""
    decimal = parse_odds_to_decimal(odds_str)
    mkt_prob = implied_prob_from_odds(odds_str)
    edge = compute_edge(win_prob, odds_str)
    f = kelly_fraction(win_prob, odds_str)
    bet, _, _, should_bet = kelly_bet(win_prob, odds_str, bankroll)

    return {
        'win_prob':     win_prob,
        'odds_str':     odds_str,
        'decimal_odds': decimal,
        'mkt_prob':     mkt_prob,
        'edge':         edge,
        'kelly_f':      f,
        'kelly_f_full': f * KELLY_DIVISOR,  # full Kelly for reference
        'bet_amount':   bet,
        'should_bet':   should_bet,
        'bankroll':     bankroll,
        'divisor':      KELLY_DIVISOR,
    }


# ============================================================
# Exacta Box Kelly sizing
# ============================================================

# Empirical exacta box parameters (updated from agent history)
EXACTA_HIT_RATE    = 0.384   # 38.4% empirical hit rate (125 races)
EXACTA_AVG_PAYOUT  = 27.94   # Average $1 exacta box payout
EXACTA_COST        = 2.00    # $2 exacta box (2 combos × $1)
EXACTA_MIN_BET     = 2.00    # Minimum (1 box = 2 combos)
EXACTA_MAX_BET     = 20.00   # Hard cap


def kelly_exacta_box(rank1_prob: float,
                     rank2_prob: float,
                     avg_payout: float = EXACTA_AVG_PAYOUT,
                     hit_rate: float = EXACTA_HIT_RATE,
                     bankroll: float = BANKROLL,
                     divisor: int = KELLY_DIVISOR) -> dict:
    """Compute Kelly-sized exacta box bet.

    Uses empirical hit rate from agent history as the probability estimate.
    The theoretical exacta probability from individual win probs:
        p_exacta = p1*p2/(1-p1) + p2*p1/(1-p2)  [approximation]
    But we use the empirical rate as it's more reliable than the theory.

    Returns dict with bet_amount, kelly_f, edge, should_bet.
    """
    # Theoretical exacta probability (for reference)
    if rank1_prob and rank2_prob and rank1_prob < 1 and rank2_prob < 1:
        p_theoretical = (
            rank1_prob * rank2_prob / (1.0 - rank1_prob) +
            rank2_prob * rank1_prob / (1.0 - rank2_prob)
        )
    else:
        p_theoretical = None

    # Use empirical rate — more reliable than softmax-derived probs
    p = hit_rate
    b = avg_payout - 1.0  # net profit per $1 bet
    q = 1.0 - p

    if b <= 0:
        return {'bet_amount': 0, 'kelly_f': 0, 'edge': 0,
                'should_bet': False, 'p_theoretical': p_theoretical}

    f_star = (b * p - q) / b
    if f_star <= 0:
        return {'bet_amount': 0, 'kelly_f': 0,
                'edge': p * avg_payout - 1,
                'should_bet': False, 'p_theoretical': p_theoretical}

    f_kelly = f_star / divisor
    raw_bet = bankroll * f_kelly

    # Round to nearest $1 increment for exacta box
    bet = max(EXACTA_MIN_BET, min(EXACTA_MAX_BET, round(raw_bet)))
    edge = p * avg_payout - 1.0

    return {
        'bet_amount':    bet,
        'kelly_f':       f_kelly,
        'kelly_f_full':  f_star,
        'edge':          edge,
        'should_bet':    True,
        'p_empirical':   p,
        'p_theoretical': p_theoretical,
        'avg_payout':    avg_payout,
    }


# ============================================================
# Smoke test
# ============================================================

if __name__ == '__main__':
    print("Kelly Criterion Module — Smoke Test")
    print("=" * 50)

    cases = [
        # (description, win_prob, odds_str, expect_bet)
        ("5/1 horse, 25% win prob — strong overlay", 0.25, "5/1", True),
        ("5/2 horse, 28% win prob — slight edge",    0.28, "5/2", True),
        ("2/5 favorite, 85% win prob — overbetting", 0.85, "2/5", False),
        ("8/1 horse, 10% win prob — breakeven",      0.10, "8/1", False),
        ("6/1 horse, 20% win prob — positive edge",  0.20, "6/1", True),
        ("30/1 longshot, 5% win prob — no edge",     0.05, "30/1", False),
        ("Evens, 55% win prob — small edge",         0.55, "evs", True),
    ]

    for desc, wp, odds, expect in cases:
        s = kelly_summary(wp, odds)
        result = "✓" if s['should_bet'] == expect else "✗"
        print(f"\n{result} {desc}")
        print(f"  odds={odds} decimal={s['decimal_odds']:.2f} "
              f"win_prob={wp:.1%} mkt_prob={s['mkt_prob']:.1%}" 
              if s['mkt_prob'] else
              f"  odds={odds} decimal={s['decimal_odds']:.2f} "
              f"win_prob={wp:.1%} mkt_prob=n/a")
        print(f"  edge={s['edge']:.1%} kelly_f={s['kelly_f']:.3f} "
              f"bet=${s['bet_amount']:.2f} should_bet={s['should_bet']}")
