"""Bolton-Chapman (1986) academic validators for horse race wagering.

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
