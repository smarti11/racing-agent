#!/usr/bin/env python3
"""Layout calculator for corner poplar shelves (left wall + back wall mount)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class ShelfSpec:
    length_in: float = 20.0  # along rear wall from left corner
    depth_in: float = 6.0  # out from rear wall / along left wall
    thickness_in: float = 1.5
    clear_gap_in: float = 12.0
    lower_clearance_in: float = 26.0  # tank lid to lower shelf bottom


def layout(spec: ShelfSpec, tank_width_in: float, tank_left_from_corner_in: float) -> dict[str, float]:
    lower_bottom = spec.lower_clearance_in
    lower_top = lower_bottom + spec.thickness_in
    upper_bottom = lower_top + spec.clear_gap_in
    upper_top = upper_bottom + spec.thickness_in
    shelf_right = spec.length_in
    tank_right = tank_left_from_corner_in + tank_width_in
    return {
        "tank_width_in": tank_width_in,
        "tank_left_from_corner_in": tank_left_from_corner_in,
        "tank_right_from_corner_in": tank_right,
        "shelf_left_from_corner_in": 0.0,
        "shelf_right_from_corner_in": shelf_right,
        "shelf_depth_in": spec.depth_in,
        "overlap_tank_in": max(0.0, min(shelf_right, tank_right) - max(0.0, tank_left_from_corner_in)),
        "lower_bottom_above_lid_in": lower_bottom,
        "lower_top_above_lid_in": lower_top,
        "upper_bottom_above_lid_in": upper_bottom,
        "upper_top_above_lid_in": upper_top,
        "center_to_center_vertical_in": (upper_bottom + spec.thickness_in / 2.0)
        - (lower_bottom + spec.thickness_in / 2.0),
    }


CHECKLIST = [
    ("measure-mark", "Corner, elevations, 20×6 footprint, studs on left + back walls"),
    ("mill-shelves", "Two 20×6×1.5 shelves + back/left cleats; square left end and back edge"),
    ("finish", "Sand 120/180/220; bathroom topcoat; cleats finished or wall-matched"),
    ("install", "Coplanar cleats on both walls; shelves tight to left + back; 12 in gap"),
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tank-width", type=float, default=19.0, help="Toilet tank lid width in inches")
    p.add_argument(
        "--tank-left",
        type=float,
        default=2.0,
        help="Distance from left wall corner to left edge of tank lid (inches)",
    )
    p.add_argument("--length", type=float, default=20.0, help="Shelf length along rear wall")
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
    data = layout(spec, args.tank_width, args.tank_left)

    print("Poplar corner shelf layout (left wall + back wall)")
    print(f"  Shelf: {spec.length_in:g} × {spec.depth_in:g} × {spec.thickness_in:g} in (×2)")
    print(f"  Attach: LEFT END → left wall, BACK EDGE → rear wall")
    print(f"  Footprint from corner: 0.00 to {data['shelf_right_from_corner_in']:.2f} in along rear wall")
    print(f"  Depth from rear wall: {data['shelf_depth_in']:.2f} in")
    print(
        f"  Tank span from corner: {data['tank_left_from_corner_in']:.2f}–"
        f"{data['tank_right_from_corner_in']:.2f} in (width {data['tank_width_in']:.2f})"
    )
    print(f"  Horizontal overlap with tank: {data['overlap_tank_in']:.2f} in")
    print(
        f"  Lower shelf bottom / top above lid: "
        f"{data['lower_bottom_above_lid_in']:.2f} / {data['lower_top_above_lid_in']:.2f} in"
    )
    print(
        f"  Upper shelf bottom / top above lid: "
        f"{data['upper_bottom_above_lid_in']:.2f} / {data['upper_top_above_lid_in']:.2f} in"
    )
    print(f"  Vertical center-to-center: {data['center_to_center_vertical_in']:.2f} in")

    if data["overlap_tank_in"] < data["tank_width_in"] * 0.5:
        print("  NOTE: Shelf covers less than half the tank width — lengthen if you want more span over the toilet.")

    if args.checklist:
        print("\nBuild checklist:")
        for key, text in CHECKLIST:
            print(f"  [ ] {key}: {text}")


if __name__ == "__main__":
    main()
