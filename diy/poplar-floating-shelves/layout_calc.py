#!/usr/bin/env python3
"""Layout calculator and build checklist for poplar floating shelves over a toilet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class ShelfSpec:
    length_in: float = 20.0
    depth_in: float = 6.0
    thickness_in: float = 1.5
    clear_gap_in: float = 12.0
    lower_clearance_in: float = 26.0  # tank lid to lower shelf bottom


def layout(spec: ShelfSpec, tank_width_in: float) -> dict[str, float]:
    half = spec.length_in / 2.0
    lower_bottom = spec.lower_clearance_in
    lower_top = lower_bottom + spec.thickness_in
    upper_bottom = lower_top + spec.clear_gap_in
    upper_top = upper_bottom + spec.thickness_in
    return {
        "tank_width_in": tank_width_in,
        "shelf_overhang_vs_tank_each_side_in": (spec.length_in - tank_width_in) / 2.0,
        "left_of_center_in": half,
        "right_of_center_in": half,
        "lower_bottom_above_lid_in": lower_bottom,
        "lower_top_above_lid_in": lower_top,
        "upper_bottom_above_lid_in": upper_bottom,
        "upper_top_above_lid_in": upper_top,
        "center_to_center_vertical_in": upper_bottom + spec.thickness_in / 2.0
        - (lower_bottom + spec.thickness_in / 2.0),
    }


CHECKLIST = [
    ("measure-mark", "Tank centerline, elevations, ±10 in ends, and studs marked"),
    ("mill-shelves", "Two 20×6×1.5 poplar blanks milled; bracket holes dry-fit"),
    ("finish", "Sand 120/180/220; 2–3 coats bathroom topcoat; fully cured"),
    ("install", "Brackets level in studs; shelves centered; 12 in clear gap"),
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tank-width", type=float, default=19.0, help="Toilet tank lid width in inches")
    p.add_argument("--length", type=float, default=20.0)
    p.add_argument("--depth", type=float, default=6.0)
    p.add_argument("--thickness", type=float, default=1.5)
    p.add_argument("--gap", type=float, default=12.0, help="Clear vertical gap between shelves")
    p.add_argument("--lower-clearance", type=float, default=26.0, help="Lid to lower shelf bottom")
    p.add_argument("--checklist", action="store_true", help="Print build checklist")
    args = p.parse_args()

    spec = ShelfSpec(
        length_in=args.length,
        depth_in=args.depth,
        thickness_in=args.thickness,
        clear_gap_in=args.gap,
        lower_clearance_in=args.lower_clearance,
    )
    data = layout(spec, args.tank_width)

    print("Poplar floating shelf layout")
    print(f"  Shelf: {spec.length_in:g} × {spec.depth_in:g} × {spec.thickness_in:g} in (×2)")
    print(f"  Tank width: {data['tank_width_in']:.2f} in")
    print(f"  Overhang vs tank (each side): {data['shelf_overhang_vs_tank_each_side_in']:+.2f} in")
    print(f"  Mark left/right ends: ±{data['left_of_center_in']:.2f} in from centerline")
    print(f"  Lower shelf bottom / top above lid: {data['lower_bottom_above_lid_in']:.2f} / {data['lower_top_above_lid_in']:.2f} in")
    print(f"  Upper shelf bottom / top above lid: {data['upper_bottom_above_lid_in']:.2f} / {data['upper_top_above_lid_in']:.2f} in")
    print(f"  Vertical center-to-center: {data['center_to_center_vertical_in']:.2f} in")

    if data["shelf_overhang_vs_tank_each_side_in"] < 0:
        print("  WARNING: shelf shorter than tank — still center on tank, or increase length.")

    if args.checklist:
        print("\nBuild checklist:")
        for key, text in CHECKLIST:
            print(f"  [ ] {key}: {text}")


if __name__ == "__main__":
    main()
