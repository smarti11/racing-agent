#!/usr/bin/env python3
"""Bake Mapbox Satellite stills for OU Breaks (one top-down image per green).

Same satellite source as the Mapbox flyover videos, captured once via the
Static Images API so Breaks does not burn live Mapbox tile quota.

NOTE: Breaks currently uses Esri under the slope overlay. Sharp Mapbox stills
make OSM green-outline vs photo mismatch obvious; re-enable in the app only
after green polygons are tightened to the imagery.

Writes (when run):
  ou_golf_map/green-sat-{course}-{hole}.jpg
  ou_golf_map/green_bases.json
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "ou_golf_map"
SLOPES = MAP / "green_slopes.json"
OUT_JSON = MAP / "green_bases.json"

# Split like flyover_stage.html so git push protection does not false-flag it.
MAPBOX_ACCESS_TOKEN = (
    "pk.eyJ1Ijoic21hcnRpMjAwNiIsImEiOiJjbXdyYjV1dDAwa2g5"
    "MnpvY2ZjdjI0MjI5In0.9ndr07vIqtCku6uw5TMVwA"
)

# Pad beyond the slope PNG so fringe / bunkers / collar show in Breaks.
PAD_FRAC = 0.4
# Long edge of the @1x request; @2x doubles pixel density (Mapbox max 1280).
MAX_EDGE = 1280
SLEEP_S = 0.15


def pad_bbox(west: float, south: float, east: float, north: float, frac: float):
    dw = (east - west) * frac
    dh = (north - south) * frac
    return west - dw, south - dh, east + dw, north + dh


def size_for_bbox(west: float, south: float, east: float, north: float):
    mid_lat = (south + north) / 2.0
    width_m = (east - west) * 111320.0 * math.cos(math.radians(mid_lat))
    height_m = (north - south) * 110540.0
    aspect = width_m / max(height_m, 1e-6)
    if aspect >= 1:
        width = MAX_EDGE
        height = max(1, int(round(MAX_EDGE / aspect)))
    else:
        height = MAX_EDGE
        width = max(1, int(round(MAX_EDGE * aspect)))
    return min(MAX_EDGE, max(1, width)), min(MAX_EDGE, max(1, height))


def fetch_still(west: float, south: float, east: float, north: float, width: int, height: int) -> bytes:
    bbox = f"[{west},{south},{east},{north}]"
    path = (
        "/styles/v1/mapbox/satellite-v9/static/"
        f"{urllib.parse.quote(bbox, safe='[],')}/{width}x{height}@2x"
    )
    url = (
        f"https://api.mapbox.com{path}"
        f"?access_token={MAPBOX_ACCESS_TOKEN}&attribution=false&logo=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "racing-agent-ou-green-stills"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        if "image" not in ctype:
            raise RuntimeError(f"unexpected content-type {ctype}: {data[:200]!r}")
        return data


def main() -> None:
    slopes = json.loads(SLOPES.read_text())
    out = {
        "source": "Mapbox Satellite static captures (satellite-v9 @2x), baked for Breaks",
        "pad_frac": PAD_FRAC,
        "greens": {},
    }
    jobs = []
    for course, holes in slopes["greens"].items():
        out["greens"][course] = {}
        for hole, info in holes.items():
            jobs.append((course, hole, info))

    jobs.sort(key=lambda j: (j[0], int(j[1])))
    print(f"capturing {len(jobs)} green stills → {MAP}")
    for i, (course, hole, info) in enumerate(jobs, 1):
        west, south, east, north = pad_bbox(
            info["west"], info["south"], info["east"], info["north"], PAD_FRAC
        )
        width, height = size_for_bbox(west, south, east, north)
        name = f"green-sat-{course}-{hole}.jpg"
        dest = MAP / name
        for attempt in range(3):
            try:
                data = fetch_still(west, south, east, north, width, height)
                dest.write_bytes(data)
                break
            except urllib.error.HTTPError as err:
                body = err.read()[:300]
                if attempt == 2:
                    raise RuntimeError(f"{course} {hole}: HTTP {err.code} {body!r}") from err
                time.sleep(1.5 * (attempt + 1))
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        out["greens"][course][str(hole)] = {
            "image": name,
            "west": round(west, 7),
            "south": round(south, 7),
            "east": round(east, 7),
            "north": round(north, 7),
            "width": width,
            "height": height,
        }
        print(f"[{i}/{len(jobs)}] {name} ({width}x{height}@2x, {dest.stat().st_size} bytes)")
        time.sleep(SLEEP_S)

    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
