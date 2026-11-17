#!/usr/bin/env python3
"""Build a slope picture for every OU green from the free USGS 3DEP elevation.

Oakland County was scanned by lidar in 2016 (quality level 2). The 3DEP
service serves that scan as a 1-meter elevation grid. A green's general fall
shows up in that grid. A break of only an inch or two can be finer than the
scan, so the pictures are smoothed over a few meters and labeled as the
general slope, not a surveyed green book.

Writes ou_golf_map/green_slopes.json and one PNG per green, sitting next to
index.html so a Cloudflare upload does not need a folder.
"""

import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "ou_golf_map"
OUT_JSON = MAP / "green_slopes.json"
SERVICE = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
UA = "ou-golf-map (smarti2006@gmail.com)"
METERS = 1.0
PAD_M = 8.0
SMOOTH_M = 3.0
PX_PER_M = 6
ARROW_EVERY_M = 5.0
M_TO_FT = 3.280839895


def mercator(lon, lat):
    x = lon * 20037508.342789244 / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * 20037508.342789244 / math.pi
    return x, y


def unmercator(x, y):
    lon = x * 180.0 / 20037508.342789244
    lat = math.atan(math.sinh(y * math.pi / 20037508.342789244)) * 180.0 / math.pi
    return lon, lat


def ring_center(ring):
    n = len(ring) - 1
    lat = sum(p[1] for p in ring[:n]) / n
    lon = sum(p[0] for p in ring[:n]) / n
    return lat, lon


def meters_between(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def match_greens(holes, greens):
    """Same nearest-green pairing the map uses for front and back yardages."""
    rings = []
    for feature in greens["features"]:
        geom = feature["geometry"]
        coords = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        if len(coords) < 4:
            continue
        lat, lon = ring_center(coords)
        rings.append({"ring": coords, "lat": lat, "lon": lon})
    pins = []
    for feature in holes["features"]:
        props = feature["properties"]
        end = feature["geometry"]["coordinates"][-1]
        start = feature["geometry"]["coordinates"][0]
        pins.append({
            "course": props["course"],
            "hole": props["hole"],
            "lat": end[1],
            "lon": end[0],
            "teeLat": start[1],
            "teeLon": start[0],
        })
    pairs = []
    for pin in pins:
        for ring in rings:
            yards = meters_between(pin["lat"], pin["lon"], ring["lat"], ring["lon"]) * 1.0936132983377078
            pairs.append((yards, pin, ring))
    pairs.sort(key=lambda item: item[0])
    used_pins = set()
    used_rings = set()
    matched = []
    for yards, pin, ring in pairs:
        key = (pin["course"], pin["hole"])
        if yards > 80 or key in used_pins or id(ring) in used_rings:
            continue
        used_pins.add(key)
        used_rings.add(id(ring))
        matched.append((pin, ring))
    return matched


def fetch_grid(minx, miny, maxx, maxy, cols, rows):
    cache = Path("/tmp/ou-green-elev")
    cache.mkdir(exist_ok=True)
    key = cache / f"{minx:.1f}_{miny:.1f}_{maxx:.1f}_{maxy:.1f}_{cols}x{rows}.npy"
    if key.exists():
        grid = np.load(key)
        if grid.shape == (rows, cols):
            return grid
    query = urllib.parse.urlencode({
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": f"{cols},{rows}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    })
    req = urllib.request.Request(SERVICE + "?" + query, headers={"User-Agent": UA})
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            image = Image.open(__import__("io").BytesIO(data))
            grid = np.array(image, dtype="float32")
            if grid.shape != (rows, cols):
                raise RuntimeError(f"expected {rows}x{cols}, got {grid.shape}")
            np.save(key, grid)
            return grid
        except Exception as err:
            last_error = err
            import time
            time.sleep(2 * (attempt + 1))
    raise last_error


def polygon_mask(ring, minx, maxy, cols, rows):
    pixels = []
    for lon, lat in ring:
        x, y = mercator(lon, lat)
        col = (x - minx) / METERS
        row = (maxy - y) / METERS
        pixels.append((col, row))
    mask_image = Image.new("L", (cols, rows), 0)
    ImageDraw.Draw(mask_image).polygon(pixels, fill=1)
    return np.array(mask_image) > 0


def smooth(values, mask, sigma):
    radius = max(1, int(math.ceil(sigma * 3)))
    axis = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (axis / sigma) ** 2)
    kernel /= kernel.sum()
    filled = values.copy()
    if mask.any():
        filled[~mask] = float(values[mask].mean())
    padded = np.pad(filled, radius, mode="edge")
    out = np.empty_like(filled)
    weight = kernel[:, None] * kernel[None, :]
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            window = padded[row:row + 2 * radius + 1, col:col + 2 * radius + 1]
            out[row, col] = float(np.sum(window * weight))
    return out


def slope_and_aspect(elev):
    dzdx = np.zeros_like(elev)
    dzdy = np.zeros_like(elev)
    dzdx[:, 1:-1] = (elev[:, 2:] - elev[:, :-2]) / (2 * METERS)
    dzdy[1:-1, :] = (elev[:-2, :] - elev[2:, :]) / (2 * METERS)
    slope = np.hypot(dzdx, dzdy)
    down_deg = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0
    return slope, down_deg, dzdx, dzdy


def draw_arrow(draw, x, y, bearing, length):
    rad = math.radians(bearing)
    dx = math.sin(rad) * length
    dy = -math.cos(rad) * length
    x2 = x + dx
    y2 = y + dy
    head = length * 0.42
    left = math.radians(bearing + 152)
    right = math.radians(bearing - 152)
    p1 = (x2 + math.sin(left) * head, y2 - math.cos(left) * head)
    p2 = (x2 + math.sin(right) * head, y2 - math.cos(right) * head)
    for color, stroke in (((0, 0, 0, 190), 5), ((255, 248, 230, 235), 3)):
        draw.line((x, y, x2, y2), fill=color, width=stroke)
        draw.line((x2, y2, p1[0], p1[1]), fill=color, width=stroke)
        draw.line((x2, y2, p2[0], p2[1]), fill=color, width=stroke)


def render(slope, mask, down_deg):
    rows, cols = slope.shape
    height = rows * PX_PER_M
    width = cols * PX_PER_M
    slope_pct = slope * 100.0
    slope_image = Image.fromarray(slope_pct.astype(np.float32), mode="F").resize(
        (width, height), Image.Resampling.BILINEAR
    )
    mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L").resize(
        (width, height), Image.Resampling.BILINEAR
    )
    big_slope = np.array(slope_image, dtype="float32")
    big_mask = np.array(mask_image) > 128
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    inside = big_mask
    # Vectorized color for the cells that are on the green.
    t = np.clip(big_slope / 4.0, 0, 1)
    low = t < 0.45
    u_low = np.where(low, t / 0.45, 0)
    u_high = np.where(low, 0, (t - 0.45) / 0.55)
    r = np.where(low, 70 + (232 - 70) * u_low, 232 + (196 - 232) * u_high)
    g = np.where(low, 150 + (196 - 150) * u_low, 196 + (48 - 196) * u_high)
    b = np.where(low, 90 + (64 - 90) * u_low, 64 + (36 - 64) * u_high)
    a = np.where(low, 55 + 70 * u_low, 125 + 50 * u_high)
    rgba[inside, 0] = r[inside].astype(np.uint8)
    rgba[inside, 1] = g[inside].astype(np.uint8)
    rgba[inside, 2] = b[inside].astype(np.uint8)
    rgba[inside, 3] = a[inside].astype(np.uint8)
    image = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(image)
    step = int(ARROW_EVERY_M)
    candidates = []
    for row in range(step // 2, rows - 1, step):
        for col in range(step // 2, cols - 1, step):
            if not mask[row, col]:
                continue
            candidates.append((slope_pct[row, col], row, col))
    strong = [item for item in candidates if item[0] >= 0.6]
    chosen = strong or [item for item in candidates if item[0] >= 0.3]
    length = 3.1 * PX_PER_M
    for pct, row, col in chosen:
        x = (col + 0.5) * PX_PER_M
        y = (row + 0.5) * PX_PER_M
        draw_arrow(draw, x, y, float(down_deg[row, col]), length)
    return image


def summarize(elev, mask, dzdx, dzdy):
    inside = elev[mask]
    fall_ft = float((inside.max() - inside.min()) * M_TO_FT)
    mean_dx = float(dzdx[mask].mean())
    mean_dy = float(dzdy[mask].mean())
    slope_pct = math.hypot(mean_dx, mean_dy) * 100.0
    down = (math.degrees(math.atan2(-mean_dx, -mean_dy)) + 360.0) % 360.0
    return {
        "fallFt": round(fall_ft, 1),
        "slopePct": round(slope_pct, 1),
        "downDeg": round(down),
    }


def main():
    holes = json.loads((MAP / "holes.geojson").read_text())
    greens = json.loads((MAP / "greens.geojson").read_text())
    matched = match_greens(holes, greens)
    print(f"matched {len(matched)} greens")
    book = {
        "source": (
            "USGS 3DEP 1-meter elevation from the 2016 Oakland County lidar. "
            "Arrows point the way a ball rolls. The color is the slope. "
            "A small break can be finer than this scan."
        ),
        "greens": {"katke": {}, "sharf": {}},
    }
    for pin, ring in sorted(matched, key=lambda item: (item[0]["course"], item[0]["hole"])):
        xs, ys = [], []
        for lon, lat in ring["ring"]:
            x, y = mercator(lon, lat)
            xs.append(x)
            ys.append(y)
        minx = math.floor((min(xs) - PAD_M) / METERS) * METERS
        maxx = math.ceil((max(xs) + PAD_M) / METERS) * METERS
        miny = math.floor((min(ys) - PAD_M) / METERS) * METERS
        maxy = math.ceil((max(ys) + PAD_M) / METERS) * METERS
        cols = int(round((maxx - minx) / METERS))
        rows = int(round((maxy - miny) / METERS))
        grid = fetch_grid(minx, miny, maxx, maxy, cols, rows)
        mask = polygon_mask(ring["ring"], minx, maxy, cols, rows)
        if int(mask.sum()) < 8:
            print(f"skip {pin['course']} {pin['hole']}: green too small in the grid")
            continue
        smoothed = smooth(grid, mask, SMOOTH_M)
        slope, down_deg, dzdx, dzdy = slope_and_aspect(smoothed)
        summary = summarize(smoothed, mask, dzdx, dzdy)
        image = render(slope, mask, down_deg)
        name = f"slope-{pin['course']}-{pin['hole']}.png"
        image.save(MAP / name)
        west, south = unmercator(minx, miny)
        east, north = unmercator(maxx, maxy)
        book["greens"][pin["course"]][str(pin["hole"])] = {
            "image": name,
            "west": round(west, 7),
            "south": round(south, 7),
            "east": round(east, 7),
            "north": round(north, 7),
            **summary,
        }
        print(
            f"{pin['course']:5} {pin['hole']:2}  "
            f"fall {summary['fallFt']:4.1f} ft  "
            f"slope {summary['slopePct']:4.1f}%  "
            f"down {summary['downDeg']:3}°  "
            f"cells {int(mask.sum())}"
        )
    OUT_JSON.write_text(json.dumps(book, indent=2) + "\n")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
