"""On-demand English walking-tour pack generator."""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GEN_DIR = ROOT / "packs" / "generated"
MEDIA_GEN = ROOT / "media" / "generated"

USER_AGENT = "PassiTour/1.0 (on-demand walking tours; contact: passi-mvp)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def _http_json(url: str, data: bytes | None = None, timeout: int = 45) -> dict | list:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        method="POST" if data else "GET",
    )
    if data is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bbox_span_deg(bbox) -> float:
    """Approximate north-south + east-west span; smaller = more city-like."""
    try:
        south, north, west, east = (float(x) for x in bbox)
        return abs(north - south) + abs(east - west)
    except Exception:
        return 999.0


def _pick_geocode_result(results: list) -> dict | None:
    if not results:
        return None
    # Prefer well-known cities (Nominatim importance) while still rejecting
    # province-scale polygons. Compact bbox is a tie-breaker only.
    ranked = sorted(
        results,
        key=lambda r: (
            0 if r.get("type") in ("city", "town", "municipality", "village", "hamlet") else 1,
            0 if r.get("class") == "place" else 1,
            0 if _bbox_span_deg(r.get("boundingbox")) <= 1.6 else 1,
            -float(r.get("importance") or 0),
            _bbox_span_deg(r.get("boundingbox")),
        ),
    )
    return ranked[0]


def geocode(place: str) -> dict:
    # Try settlement-biased search first so "Siena" → city center, not province centroid.
    attempts = [
        {"q": place, "format": "json", "limit": 5, "featureType": "settlement", "accept-language": "en"},
        {"q": place, "format": "json", "limit": 5, "featureType": "city", "accept-language": "en"},
        {"q": place, "format": "json", "limit": 5, "accept-language": "en"},
    ]
    chosen = None
    for i, params in enumerate(attempts):
        time.sleep(1.05)  # Nominatim polite use
        q = urllib.parse.urlencode(params)
        try:
            results = _http_json(f"{NOMINATIM}?{q}", timeout=30)
        except Exception:
            continue
        pick = _pick_geocode_result(results or [])
        if not pick:
            continue
        # Reject province-scale hits when a tighter attempt may follow.
        if _bbox_span_deg(pick.get("boundingbox")) > 0.55 and i < len(attempts) - 1:
            continue
        chosen = pick
        break
    if not chosen:
        raise ValueError(f"Could not find a place matching “{place}”. Try a city or region name.")
    r = chosen
    local_name = (r.get("display_name") or place).split(",")[0].strip()
    # Use the tourist's typed place (English) so packs say "Florence" not "Firenze".
    head = place.split(",")[0].strip()
    for suffix in (" italy", " france", " spain", " germany", " usa", " us", " uk"):
        if head.lower().endswith(suffix):
            head = head[: -len(suffix)].strip()
    name = head.title() if head else local_name
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "name": name,
        "display": r.get("display_name", place),
        "bbox": r.get("boundingbox"),
    }


def _overpass_query(lat: float, lon: float, radius_m: int) -> str:
    # Prefer nodes first (faster); include ways as a second pass only if needed.
    return f"""
    [out:json][timeout:25];
    (
      node["tourism"="attraction"](around:{radius_m},{lat},{lon});
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      node["historic"~"monument|castle|ruins|church|cathedral|memorial"](around:{radius_m},{lat},{lon});
      node["amenity"="place_of_worship"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="attraction"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"](around:{radius_m},{lat},{lon});
      way["historic"~"monument|castle|church|cathedral"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def _parse_poi_elements(elements: list, origin_lat: float, origin_lon: float) -> list[dict]:
    pois = []
    seen = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name:en") or tags.get("name")
        if not name or len(name) < 2:
            continue
        key = name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if "lat" in el:
            plat, plon = float(el["lat"]), float(el["lon"])
        else:
            c = el.get("center") or {}
            if "lat" not in c:
                continue
            plat, plon = float(c["lat"]), float(c["lon"])
        score = 0
        if tags.get("tourism") == "attraction":
            score += 5
        if tags.get("tourism") == "museum":
            score += 4
        if tags.get("historic"):
            score += 3
        if tags.get("wikipedia") or tags.get("wikidata"):
            score += 2
        if tags.get("name:en"):
            score += 1
        pois.append(
            {
                "name": name.strip(),
                "lat": plat,
                "lng": plon,
                "tags": tags,
                "score": score,
                "dist": haversine_m(origin_lat, origin_lon, plat, plon),
            }
        )
    pois.sort(key=lambda p: (-p["score"], p["dist"]))
    return pois


def fetch_pois(lat: float, lon: float, radius_m: int = 1800) -> list[dict]:
    query = _overpass_query(lat, lon, radius_m)
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                payload = _http_json(endpoint, data=data, timeout=40)
                return _parse_poi_elements(payload.get("elements") or [], lat, lon)
            except Exception as e:
                last_err = e
                time.sleep(0.8 + attempt)
                continue
    raise RuntimeError(f"Attraction lookup timed out. Please try again in a moment. ({last_err})")


def haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    R = 6371000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def nearest_neighbor_order(pois: list[dict], start_lat: float, start_lon: float) -> list[dict]:
    remaining = list(pois)
    ordered = []
    cur_lat, cur_lon = start_lat, start_lon
    while remaining:
        remaining.sort(key=lambda p: haversine_m(cur_lat, cur_lon, p["lat"], p["lng"]))
        nxt = remaining.pop(0)
        ordered.append(nxt)
        cur_lat, cur_lon = nxt["lat"], nxt["lng"]
    return ordered


def wiki_summary(name: str, city: str) -> str | None:
    for title in (name, f"{name} ({city})", f"{name}, {city}"):
        slug = urllib.parse.quote(title.replace(" ", "_"), safe="")
        try:
            time.sleep(0.15)
            data = _http_json(WIKI + slug, timeout=12)
        except Exception:
            continue
        if data.get("type") == "disambiguation":
            continue
        extract = (data.get("extract") or "").strip()
        if extract and len(extract) > 40:
            # keep first ~2 sentences
            parts = re.split(r"(?<=[.!?])\s+", extract)
            return " ".join(parts[:2]).strip()
    return None


def build_script(name: str, city: str, tags: dict, wiki: str | None) -> list[str]:
    kind = tags.get("historic") or tags.get("tourism") or tags.get("amenity") or "landmark"
    kind = str(kind).replace("_", " ")
    paras = [
        f"You are at {name} in {city}.",
    ]
    if wiki:
        paras.append(wiki)
    else:
        paras.append(
            f"This {kind} is one of the places visitors seek out here. Take a moment to look at the details around you — façades, plaques, and the street life that frames it."
        )
    paras.append("When you are ready, continue walking to the next stop on your Passi tour.")
    return paras


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "stop")[:48]


def synthesize_audio(text: str, dest: Path) -> int:
    """Return duration seconds. Falls back to 0 if TTS unavailable."""
    try:
        import asyncio
        import edge_tts
        from mutagen.mp3 import MP3
    except ImportError:
        return 0

    async def _run():
        await edge_tts.Communicate(text, "en-GB-SoniaNeural", rate="-5%").save(str(dest))

    dest.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_run())
    try:
        from mutagen.mp3 import MP3

        return round(MP3(dest).info.length)
    except Exception:
        return 0


def generate_pack(
    place_query: str,
    stop_count: int,
    *,
    with_audio: bool = True,
    radius_m: int = 1800,
) -> dict:
    stop_count = max(3, min(int(stop_count), 12))
    geo = geocode(place_query)
    city = geo["name"]
    pois: list[dict] = []
    for r in (radius_m, 2800, 4500):
        try:
            pois = fetch_pois(geo["lat"], geo["lon"], radius_m=r)
        except RuntimeError:
            if pois:
                break
            continue
        if len(pois) >= stop_count:
            break
    if len(pois) < 3:
        raise ValueError(
            f"Not enough mapped attractions near “{place_query}”. Try a larger city or a well-known historic center."
        )

    # Pick the best-scored landmarks first (what tourists want), then order a walk.
    must_see = pois[:stop_count]
    chosen = nearest_neighbor_order(must_see, geo["lat"], geo["lon"])

    tour_id = f"ondemand-{slugify(city)}-{stop_count}-{int(time.time())}"
    media_rel = f"generated/{tour_id}"
    media_dir = MEDIA_GEN / tour_id / "audio"
    media_dir.mkdir(parents=True, exist_ok=True)

    stops = []
    for i, poi in enumerate(chosen, start=1):
        wiki = wiki_summary(poi["name"], city)
        script = build_script(poi["name"], city, poi["tags"], wiki)
        sid = f"{i:02d}-{slugify(poi['name'])}"
        audio_url = None
        duration = 0
        if with_audio:
            narration = " ... ".join(script)
            dest = media_dir / f"{sid}.mp3"
            try:
                duration = synthesize_audio(narration, dest)
                if duration:
                    audio_url = f"/media/{media_rel}/audio/{sid}.mp3"
            except Exception as e:
                print("TTS failed for", poi["name"], e)
        stops.append(
            {
                "id": sid,
                "order": i,
                "name": poi["name"],
                "shortName": poi["name"][:32],
                "lat": poi["lat"],
                "lng": poi["lng"],
                "walkFromPrev": "Start here." if i == 1 else "Walk to the next mapped stop.",
                "durationSec": duration,
                "audioUrl": audio_url,
                "script": script,
                "photos": [],
                "practical": {},
            }
        )

    pack = {
        "id": tour_id,
        "locale": "en",
        "city": city,
        "title": f"{city} — {stop_count} stops",
        "tagline": f"On-demand English walking tour around {city}.",
        "durationLabel": f"About {max(1, stop_count // 3)}–{max(2, stop_count // 2)} hours · {stop_count} stops",
        "distanceLabel": "Custom loop from mapped attractions",
        "unlockRadiusMeters": 90,
        "mapCenter": [geo["lat"], geo["lon"]],
        "mapZoom": 14,
        "generated": True,
        "query": place_query,
        "stops": stops,
    }

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GEN_DIR / f"{tour_id}.json"
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    pack["_path"] = str(path)
    return pack


if __name__ == "__main__":
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "Siena Italy"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    p = generate_pack(q, n, with_audio=False)
    print(p["id"], len(p["stops"]), [s["name"] for s in p["stops"]])
