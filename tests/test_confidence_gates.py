"""Unit tests for Jul 2026 handicapping performance gates."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.confidence import (
    calibrate_confidence,
    relative_model_edge,
    MAX_ANTI_MARKET_REL_EDGE,
    MIN_PROB_FOR_HIGH,
    MIN_PROB_FOR_MEDIUM,
)
from core.market import blend_scores_with_market
from core.handicapper import _morning_line_rank, get_top_pick


def test_relative_edge():
    assert abs(relative_model_edge(0.30, 0.20) - 0.50) < 1e-9
    assert relative_model_edge(0.30, None) is None
    assert relative_model_edge(0.30, 0.0) is None


def test_anti_market_demotes_to_low():
    # Large gap would be HIGH, but 100% relative edge vs ML and not favorite → LOW
    conf = calibrate_confidence(
        20.0, 8.0, "CD",
        win_prob=0.40,
        market_prob=0.20,  # 100% relative edge
        ml_rank=5,
        pace_role="P",
    )
    assert conf == "LOW"


def test_anti_market_allowed_for_ml_favorite():
    conf = calibrate_confidence(
        20.0, 2.5, "CD",
        win_prob=0.45,
        market_prob=0.28,  # ~61% relative edge
        ml_rank=1,
        pace_role="EP",
    )
    assert conf == "HIGH"


def test_closer_veto():
    conf = calibrate_confidence(
        20.0, 3.0, "CD",
        win_prob=0.35,
        market_prob=0.32,
        ml_rank=1,
        pace_role="C",
        pace_scenario_name="HONEST",
    )
    assert conf == "LOW"


def test_closer_contested_exception_caps_medium():
    conf = calibrate_confidence(
        20.0, 3.0, "CD",
        win_prob=0.30,
        market_prob=0.28,
        ml_rank=1,
        pace_role="C",
        pace_scenario_name="CONTESTED",
    )
    assert conf == "MEDIUM"


def test_low_prob_soft_cap():
    conf = calibrate_confidence(
        20.0, 3.0, "CD",
        win_prob=0.12,
        market_prob=0.11,
        ml_rank=1,
        pace_role="E",
    )
    assert conf == "LOW"

    conf_med = calibrate_confidence(
        20.0, 3.0, "CD",
        win_prob=0.22,
        market_prob=0.20,
        ml_rank=1,
        pace_role="E",
    )
    assert conf_med == "MEDIUM"
    assert MIN_PROB_FOR_MEDIUM <= 0.22 < MIN_PROB_FOR_HIGH


def test_high_requires_ml_top2():
    conf = calibrate_confidence(
        20.0, 6.0, "CD",
        win_prob=0.30,
        market_prob=0.28,  # small edge
        ml_rank=4,
        pace_role="P",
    )
    assert conf == "MEDIUM"


def test_weak_track_never_high():
    conf = calibrate_confidence(20.0, 2.0, "DMR")
    assert conf != "HIGH"


def test_blend_scores_with_market():
    horses = [
        {"program_num": "1", "score": 70.0, "market_prob": 0.10},
        {"program_num": "2", "score": 68.0, "market_prob": 0.40},
    ]
    blend_scores_with_market(horses, weight=0.15)
    # Horse 2 should move ahead after market pull
    assert horses[0]["program_num"] == "2"
    assert horses[0]["rank"] == 1


def test_morning_line_rank_and_top_pick_gates():
    field = [
        {
            "program_num": "3", "score": 80, "morning_line": "8/1",
            "track_code": "CD", "pace_role": "C", "win_prob": 0.35,
            "market_prob": 0.12, "pace_scenario": {"scenario": "HONEST"},
        },
        {
            "program_num": "1", "score": 70, "morning_line": "2/1",
            "track_code": "CD", "pace_role": "E", "win_prob": 0.30,
            "market_prob": 0.35,
        },
    ]
    assert _morning_line_rank(field[0], field) == 2
    assert _morning_line_rank(field[1], field) == 1
    top = get_top_pick(field)
    assert top["confidence"] == "LOW"  # closer + anti-market


def test_edge_threshold_constant():
    assert MAX_ANTI_MARKET_REL_EDGE == 0.50


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)} passed")
