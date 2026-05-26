"""Isotonic regression calibrator for win probabilities.

Pure Python implementation using the Pool-Adjacent-Violators (PAV) algorithm.
Maps raw model probabilities to calibrated probabilities based on observed
historical win rates.

Usage:
    # Fit on historical data
    cal = IsotonicCalibrator()
    cal.fit(raw_probs=[0.05, 0.12, 0.18, ...], outcomes=[0, 0, 1, ...])
    cal.save("models/calibrator.json")

    # Apply forward
    cal = IsotonicCalibrator.load("models/calibrator.json")
    calibrated = cal.transform(0.27)   # → e.g. 0.31
"""

import json
import os
from pathlib import Path
from typing import List


class IsotonicCalibrator:
    """Pool-Adjacent-Violators isotonic regression for probability calibration."""

    def __init__(self):
        # After fitting, these store the step function:
        # _x_breakpoints[i] is a raw probability threshold
        # _y_values[i] is the calibrated probability for raw probs in [_x_breakpoints[i], _x_breakpoints[i+1])
        self._x_breakpoints: List[float] = []
        self._y_values: List[float] = []

    def fit(self, raw_probs: List[float], outcomes: List[int]) -> None:
        """Fit calibrator using Pool-Adjacent-Violators.

        Args:
            raw_probs: Model's predicted probabilities (0-1 each)
            outcomes: 1 if event happened, 0 otherwise. Same length as raw_probs.
        """
        if len(raw_probs) != len(outcomes):
            raise ValueError("raw_probs and outcomes must be same length")
        if not raw_probs:
            raise ValueError("Empty input")

        # Sort by raw_prob ascending
        paired = sorted(zip(raw_probs, outcomes), key=lambda p: p[0])

        # Each "block" tracks: sum_of_y, count, raw_prob (last in block)
        # Start: every point is its own block
        blocks = []
        for x, y in paired:
            blocks.append({"sum_y": float(y), "count": 1, "x_max": x, "x_min": x})

        # PAV: while any adjacent pair violates monotonicity, merge them
        i = 0
        while i < len(blocks) - 1:
            mean_curr = blocks[i]["sum_y"] / blocks[i]["count"]
            mean_next = blocks[i + 1]["sum_y"] / blocks[i + 1]["count"]
            if mean_curr > mean_next:
                # Merge i+1 into i, then back up to recheck previous pair
                blocks[i]["sum_y"] += blocks[i + 1]["sum_y"]
                blocks[i]["count"] += blocks[i + 1]["count"]
                blocks[i]["x_max"] = blocks[i + 1]["x_max"]
                blocks.pop(i + 1)
                if i > 0:
                    i -= 1
            else:
                i += 1

        # Build step function: x_breakpoints[i] is upper edge of block i, y_values[i] is its mean
        self._x_breakpoints = [b["x_max"] for b in blocks]
        self._y_values = [b["sum_y"] / b["count"] for b in blocks]

    def transform(self, raw_prob: float) -> float:
        """Convert raw probability to calibrated probability."""
        if not self._x_breakpoints:
            raise RuntimeError("Calibrator not fitted")
        for i, x_max in enumerate(self._x_breakpoints):
            if raw_prob <= x_max:
                return self._y_values[i]
        # Above all breakpoints — return max calibrated value
        return self._y_values[-1]

    def transform_batch(self, raw_probs: List[float]) -> List[float]:
        return [self.transform(p) for p in raw_probs]

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "x_breakpoints": self._x_breakpoints,
                "y_values": self._y_values,
            }, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "IsotonicCalibrator":
        with open(path, "r") as f:
            data = json.load(f)
        c = cls()
        c._x_breakpoints = data["x_breakpoints"]
        c._y_values = data["y_values"]
        return c

    def fitted(self) -> bool:
        return bool(self._x_breakpoints)
