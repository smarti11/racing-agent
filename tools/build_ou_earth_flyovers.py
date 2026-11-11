#!/usr/bin/env python3
"""Build a Google Earth tour file for every OU golf hole.

Each hole line in ou_golf_map/holes.geojson becomes a tour that flies from
the tee to the green. Open the .kmz in Google Earth Pro and double-click a hole.
"""

import json
import math
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "ou_golf_map"
EARTH_RADIUS_M = 6371000.0


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def destination(lon, lat, heading_deg, distance_m):
    heading = math.radians(heading_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(
        math.sin(p1) * math.cos(distance_m / EARTH_RADIUS_M)
        + math.cos(p1) * math.sin(distance_m / EARTH_RADIUS_M) * math.cos(heading)
    )
    l2 = l1 + math.atan2(
        math.sin(heading) * math.sin(distance_m / EARTH_RADIUS_M) * math.cos(p1),
        math.cos(distance_m / EARTH_RADIUS_M) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(l2), math.degrees(p2)


def centroid(ring):
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lon, lat


def nearest(point, centers):
    return min(haversine(point[0], point[1], c[0], c[1]) for c in centers)


def densify(coords, step_m):
    points = [(coords[0][0], coords[0][1])]
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        dist = haversine(lon1, lat1, lon2, lat2)
        pieces = max(1, int(round(dist / step_m)))
        for i in range(1, pieces + 1):
            t = i / pieces
            points.append((lon1 + (lon2 - lon1) * t, lat1 + (lat2 - lat1) * t))
    return points


def heading_at(points, index):
    nxt = min(len(points) - 1, index + 1)
    if nxt == index and index > 0:
        return bearing(points[index - 1][0], points[index - 1][1], points[index][0], points[index][1])
    return bearing(points[index][0], points[index][1], points[nxt][0], points[nxt][1])


def cameras_for(coords):
    """Start at eye level on the tee, hold, then climb to 10 m and fly the hole."""
    samples = densify(coords, 20)
    distances = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(samples, samples[1:]):
        distances.append(distances[-1] + haversine(lon1, lat1, lon2, lat2))
    total = distances[-1] or 1.0
    rise_m = min(70.0, total * 0.18)
    events = []
    for i, (lon, lat) in enumerate(samples):
        traveled = distances[i]
        if traveled <= rise_m:
            u = traveled / rise_m if rise_m else 1.0
            smooth = u * u * (3 - 2 * u)
            alt = 1.8 + (10.0 - 1.8) * smooth
            tilt = 85 - 10 * smooth
            speed = 6.0
        else:
            remaining = total - traveled
            alt = 10.0
            tilt = 62 if remaining < 35 else 75
            speed = 12.0
        if i == 0:
            duration = 2.0
        else:
            step = distances[i] - distances[i - 1]
            duration = min(2.2, max(0.35, step / speed))
        events.append({
            "kind": "camera",
            "lon": lon,
            "lat": lat,
            "alt": alt,
            "heading": heading_at(samples, i),
            "tilt": tilt,
            "duration": duration,
        })
        if i == 0:
            events.append({"kind": "wait", "duration": 1.2})
    return events


def flyto(camera):
    if camera["kind"] == "wait":
        return f"      <gx:Wait><gx:duration>{camera['duration']:.1f}</gx:duration></gx:Wait>"
    return f"""      <gx:FlyTo>
        <gx:duration>{camera['duration']:.2f}</gx:duration>
        <gx:flyToMode>smooth</gx:flyToMode>
        <gx:balloonVisibility>0</gx:balloonVisibility>
        <Camera>
          <longitude>{camera['lon']:.7f}</longitude>
          <latitude>{camera['lat']:.7f}</latitude>
          <altitude>{camera['alt']:.1f}</altitude>
          <heading>{camera['heading']:.2f}</heading>
          <tilt>{camera['tilt']:.1f}</tilt>
          <roll>0</roll>
          <altitudeMode>relativeToGround</altitudeMode>
        </Camera>
      </gx:FlyTo>"""


def tour(name, description, cameras):
    body = "\n".join(flyto(c) for c in cameras)
    body += "\n      <gx:Wait><gx:duration>1.5</gx:duration></gx:Wait>"
    return f"""    <gx:Tour>
      <name>{escape(name)}</name>
      <description>{escape(description)}</description>
      <gx:Playlist>
{body}
      </gx:Playlist>
    </gx:Tour>"""


def load_centers(filename):
    data = json.loads((MAP / filename).read_text())
    centers = []
    for feature in data["features"]:
        ring = feature["geometry"]["coordinates"][0]
        centers.append(centroid(ring))
    return centers


def main():
    holes = json.loads((MAP / "holes.geojson").read_text())["features"]
    tee_centers = load_centers("tees.geojson")
    green_centers = load_centers("greens.geojson")
    by_course = {"katke": [], "sharf": []}
    for feature in holes:
        props = feature["properties"]
        coords = [(c[0], c[1]) for c in feature["geometry"]["coordinates"]]
        start, end = coords[0], coords[-1]
        start_tee = nearest(start, tee_centers)
        start_green = nearest(start, green_centers)
        end_tee = nearest(end, tee_centers)
        end_green = nearest(end, green_centers)
        reversed_line = end_tee + 25 < start_tee and start_green + 25 < end_green
        if reversed_line:
            coords = list(reversed(coords))
        by_course[props["course"]].append({
            "hole": props["hole"],
            "par": props["par"],
            "yards": props["yards"],
            "name": props["courseName"],
            "coords": coords,
            "reversed": reversed_line,
            "start_tee": start_tee,
            "end_green": end_green,
        })

    parts = ["""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>OU Golf Flyovers</name>
    <description>Double-click a hole. The camera starts at eye level on the tee, rises to 10 meters, and flies to the green.</description>
    <open>1</open>"""]

    labels = (("katke", "Katke-Cousins"), ("sharf", "R&S Sharf"))
    for course, title in labels:
        rows = sorted(by_course[course], key=lambda row: row["hole"])
        parts.append(f"    <Folder><name>{escape(title)}</name><open>1</open>")
        all_cameras = []
        for row in rows:
            cameras = cameras_for(row["coords"])
            seconds = sum(c["duration"] for c in cameras) + 1.5
            print(
                f"{row['name']} {row['hole']:2d}  {seconds:4.0f}s  "
                f"tee {row['start_tee']:5.0f}m  green {row['end_green']:5.0f}m  "
                f"{'reversed' if row['reversed'] else 'as drawn'}"
            )
            if all_cameras:
                cameras = [dict(cameras[0], duration=3.0)] + cameras[1:]
            all_cameras.extend(cameras)
            parts.append(tour(
                f"Play Hole {row['hole']}",
                f"{row['name']} hole {row['hole']}, par {row['par']}, {row['yards']} yards. Starts at eye level on the tee, rises to 10 meters, then flies to the green.",
                cameras_for(row["coords"]),
            ))
        parts.append(tour(
            "Play all 18 holes",
            f"Flies {title} from hole 1 through hole 18.",
            all_cameras,
        ))
        parts.append("    </Folder>")
    parts.append("  </Document>\n</kml>\n")
    kml = "\n".join(parts)
    kml_path = MAP / "ou_golf_flyovers.kml"
    kmz_path = MAP / "ou_golf_flyovers.kmz"
    kml_path.write_text(kml)
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("doc.kml", kml)
    print(f"wrote {kml_path} ({kml_path.stat().st_size} bytes)")
    print(f"wrote {kmz_path} ({kmz_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
