"""Convert handicapper scores to win probabilities using softmax.

Following Benter (1994), the goal is to produce a probability distribution
over horses that sums to 1.0 within each race. These probabilities can then
be compared against the public's implied probabilities (from odds) to find
positive-expectation bets.
"""

import math
from typing import List, Dict


def scores_to_probabilities(horses: List[Dict], temperature: float = 8.0) -> List[Dict]:
    """Add 'win_prob' field to each horse based on softmax of scores.

    Args:
        horses: List of dicts with at least 'score' field. Scratched horses
                should be filtered out before calling.
        temperature: Softmax temperature. Higher = flatter distribution.
                     Lower = sharper peak on top score.
                     Default 8.0 calibrated for typical 50-100 score range.

    Returns:
        Same list with 'win_prob' added to each dict. Probabilities sum to 1.0.
    """
    if not horses:
        return horses

    # Get scores, defaulting to 0 if missing
    scores = [h.get("score") or 0 for h in horses]

    # Subtract max for numerical stability (prevents exp() overflow on big scores)
    max_score = max(scores)
    shifted = [s - max_score for s in scores]

    # Softmax: e^(score/T) / sum(e^(score/T))
    exps = [math.exp(s / temperature) for s in shifted]
    total = sum(exps)

    if total == 0:
        # Degenerate case: assign uniform probability
        uniform = 1.0 / len(horses)
        for h in horses:
            h["win_prob"] = uniform
        return horses

    for h, e in zip(horses, exps):
        h["win_prob"] = e / total

    return horses


def market_probability_from_morning_line(ml_text: str) -> float:
    """Convert morning line text like '5/2' or '8-1' to implied probability.

    Returns 0.0 if parse fails.
    """
    if not ml_text:
        return 0.0
    text = str(ml_text).strip().replace("-", "/")
    try:
        if "/" in text:
            num, denom = text.split("/")
            num_f = float(num.strip())
            denom_f = float(denom.strip())
            if num_f + denom_f == 0:
                return 0.0
            # Implied prob = denom / (num + denom). E.g., 5/2 → 2/7 ≈ 28.6%
            return denom_f / (num_f + denom_f)
        # Decimal odds like "3.5"
        odds = float(text)
        if odds <= 0:
            return 0.0
        return 1.0 / (odds + 1.0)
    except (ValueError, ZeroDivisionError):
        return 0.0


def edge(model_prob: float, market_prob: float) -> float:
    """Compute edge as (model - market) / market.

    Positive edge = your model thinks the horse is more likely than the market.
    Edge of 0.20 means your model has the horse 20% more likely than market.
    """
    if market_prob <= 0:
        return 0.0
    return (model_prob - market_prob) / market_prob


def kelly_fraction(model_prob: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """Compute Kelly bet size as fraction of bankroll.

    Args:
        model_prob: Your estimated probability (0-1)
        decimal_odds: Decimal odds (e.g., 3.5 means $1 bet returns $3.50 + stake)
        fraction: Fractional Kelly multiplier (0.25 = quarter-Kelly).
                  Lower = safer, less variance, but slower growth.

    Returns:
        Fraction of bankroll to bet. Returns 0 if no positive edge.
    """
    if decimal_odds <= 1.0 or model_prob <= 0:
        return 0.0
    # b = decimal_odds - 1 (the profit on a $1 bet)
    b = decimal_odds - 1.0
    p = model_prob
    q = 1.0 - p
    # Full Kelly: f* = (bp - q) / b
    full_kelly = (b * p - q) / b
    if full_kelly <= 0:
        return 0.0
    return full_kelly * fraction
