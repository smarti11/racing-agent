#!/usr/bin/env python3
"""Fill Indianwood card.json elevFt from USGS 3DEP so plays-like works.

Plays-like adds 1 yard per 3 ft uphill tee→green and subtracts 1 yard per 3 ft
downhill. Sample green elevation at the pin end of each hole line, and tee
elevations at OSM tee polygons when present (farthest from green = Championship),
otherwise at the scorecard yardage back from the pin along the hole.
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "apps" / "indianwood-course"
CARD = MAP / "card.json"
# EPQS is the USGS point-query API over 3DEP (returns feet directly). The
# ImageServer/identify endpoint 502s under load; EPQS is more reliable here.
EPQS = "https://epqs.nationalmap.gov/v1/json"
IDENTIFY = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer/identify"
)
UA = "indianwood-map (smarti2006@gmail.com)"
TEE_ORDER = ["black", "gold", "white", "red"]
M_TO_FT = 3.280839895
YD_TO_M = 0.9144


def mercator(lon: float, lat: float) -> tuple[float, float]:
    x = lon * 20037508.342789244 / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * 20037508.342789244 / math.pi
    return x, y


def meters_between(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def path_length(coords) -> float:
    total = 0.0
    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        total += meters_between(a[1], a[0], b[1], b[0])
    return total


def point_back_from_end(coords, meters_back: float):
    """Walk from the green (last vertex) toward the tee by meters_back."""
    if meters_back <= 0 or len(coords) < 2:
        return coords[-1][0], coords[-1][1]
    remaining = meters_back
    for i in range(len(coords) - 1, 0, -1):
        a = coords[i - 1]  # toward tee
        b = coords[i]  # toward green
        seg = meters_between(a[1], a[0], b[1], b[0])
        if seg <= 0:
            continue
        if remaining <= seg:
            t = remaining / seg
            lon = b[0] + (a[0] - b[0]) * t
            lat = b[1] + (a[1] - b[1]) * t
            return lon, lat
        remaining -= seg
    return coords[0][0], coords[0][1]


def centroid(coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def ring_of(feature):
    geom = feature["geometry"]
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"][0][0]
    if geom["type"] == "Point":
        return [geom["coordinates"], geom["coordinates"]]
    return geom["coordinates"]


_cache: dict[tuple[float, float], float] = {}


def _epqs_ft(lon: float, lat: float) -> float:
    query = urllib.parse.urlencode(
        {
            "x": f"{lon:.8f}",
            "y": f"{lat:.8f}",
            "units": "Feet",
            "wkid": "4326",
            "includeDate": "false",
        }
    )
    req = urllib.request.Request(EPQS + "?" + query, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    value = data.get("value")
    if value is None or value in ("", "NoData"):
        raise ValueError(f"EPQS NoData at {lon},{lat}: {data}")
    return float(value)


def _identify_ft(lon: float, lat: float) -> float:
    x, y = mercator(lon, lat)
    query = urllib.parse.urlencode(
        {
            "geometry": json.dumps({"x": x, "y": y, "spatialReference": {"wkid": 3857}}),
            "geometryType": "esriGeometryPoint",
            "returnGeometry": "false",
            "returnCatalogItems": "false",
            "f": "json",
        }
    )
    req = urllib.request.Request(IDENTIFY + "?" + query, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    raw = data.get("value")
    if raw is None or raw in ("", "NoData"):
        raise ValueError(f"identify NoData at {lon},{lat}: {data}")
    return float(raw) * M_TO_FT


def elev_ft(lon: float, lat: float) -> float:
    """Prefer EPQS (reliable); only fall back to ImageServer/identify late."""
    key = (round(lon, 6), round(lat, 6))
    if key in _cache:
        return _cache[key]
    last = None
    # Attempts 0-5: EPQS only. Attempts 6-7: identify fallback.
    for attempt in range(8):
        try:
            if attempt < 6:
                value = _epqs_ft(lon, lat)
            else:
                value = _identify_ft(lon, lat)
            value = round(value, 1)
            _cache[key] = value
            time.sleep(0.2)  # be polite to USGS
            return value
        except Exception as err:
            last = err
            time.sleep(min(30.0, 1.5 * (2**attempt)))
    raise last


def _is_stub(elev: dict | None) -> bool:
    if not elev:
        return True
    vals = [elev.get(k) for k in (*TEE_ORDER, "green") if elev.get(k) is not None]
    return not vals or all(v == 1000 for v in vals)


def tee_polygons(tees, course, hole):
    out = []
    for feature in tees["features"]:
        props = feature["properties"]
        if props.get("course") != course or props.get("hole") != hole:
            continue
        ring = ring_of(feature)
        if len(ring) < 1:
            continue
        lon, lat = centroid(ring[:-1] if ring[0] == ring[-1] and len(ring) > 2 else ring)
        out.append((lon, lat))
    return out


def _write_card(card: dict) -> None:
    card["note"] = (
        "Handicap and Gold yardages from published Indianwood scorecards. "
        "Other tees are estimated from Gold until official multi-tee cards are loaded. "
        "Plays-like uses USGS 3DEP elevations (Oakland County 2016 lidar): "
        "+1 yd per 3 ft uphill tee→green, −1 yd per 3 ft downhill."
    )
    CARD.write_text(json.dumps(card, indent=2) + "\n")


def main():
    card = json.loads(CARD.read_text())
    holes = json.loads((MAP / "holes.geojson").read_text())
    tees = json.loads((MAP / "tees.geojson").read_text())
    hole_lines = {
        (f["properties"]["course"], f["properties"]["hole"]): f["geometry"]["coordinates"]
        for f in holes["features"]
    }

    filled = skipped = 0
    for course, data in card["courses"].items():
        for hole in data["holes"]:
            n = hole["hole"]
            if not _is_stub(hole.get("elevFt")):
                skipped += 1
                print(f"{course:3} {n:2}  skip (already filled)")
                continue
            coords = hole_lines[(course, n)]
            # Ensure line runs tee → green using length heuristic already baked
            # into holes.geojson; pin is last vertex.
            green_lon, green_lat = coords[-1][0], coords[-1][1]
            green_ft = elev_ft(green_lon, green_lat)

            polys = tee_polygons(tees, course, n)
            polys.sort(
                key=lambda p: meters_between(green_lat, green_lon, p[1], p[0]),
                reverse=True,
            )

            elev = {"green": green_ft}
            assigned = {}
            for i, tee_id in enumerate(TEE_ORDER):
                if i < len(polys):
                    lon, lat = polys[i]
                    assigned[tee_id] = elev_ft(lon, lat)
                else:
                    yards = hole["yards"].get(tee_id)
                    if yards is None:
                        continue
                    lon, lat = point_back_from_end(coords, float(yards) * YD_TO_M)
                    assigned[tee_id] = elev_ft(lon, lat)
                elev[tee_id] = assigned[tee_id]

            hole["elevFt"] = elev
            filled += 1
            deltas = {
                tee_id: round(green_ft - elev[tee_id])
                for tee_id in TEE_ORDER
                if tee_id in elev
            }
            print(
                f"{course:3} {n:2}  green {green_ft:6.1f} ft  "
                + "  ".join(f"{t} {elev[t]:6.1f} (Δ{deltas[t]:+d})" for t in TEE_ORDER if t in elev),
                flush=True,
            )
            # Persist after each hole so a mid-run USGS flake can resume.
            _write_card(card)

    print(f"wrote {CARD} (filled {filled}, skipped {skipped})")


if __name__ == "__main__":
    main()
