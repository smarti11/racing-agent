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
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIDATA_LABEL = "https://www.wikidata.org/w/api.php"

_label_cache: dict[str, str] = {}


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
    name = _pretty_place_name(head) if head else local_name
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "name": name,
        "display": r.get("display_name", place),
        "bbox": r.get("boundingbox"),
    }


def _pretty_place_name(head: str) -> str:
    """Title-case a place while keeping short acronyms (DC, NYC, UK)."""
    keep = {"dc": "DC", "d.c.": "D.C.", "nyc": "NYC", "uk": "UK", "usa": "USA", "us": "US"}
    out = []
    for w in head.replace("_", " ").split():
        key = w.lower()
        if key in keep:
            out.append(keep[key])
        elif len(w) <= 3 and w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:] if w.islower() or w.istitle() else w[:1].upper() + w[1:].lower())
    return " ".join(out) or head


def _overpass_tourism_query(lat: float, lon: float, radius_m: int) -> str:
    """Fast pass: common tourist POIs as nodes/ways."""
    return f"""
    [out:json][timeout:25];
    (
      node["tourism"="attraction"](around:{radius_m},{lat},{lon});
      node["tourism"="museum"](around:{radius_m},{lat},{lon});
      node["tourism"="gallery"](around:{radius_m},{lat},{lon});
      node["tourism"="artwork"](around:{radius_m},{lat},{lon});
      node["historic"~"monument|castle|ruins|church|cathedral|memorial|palace|fort|wayside_shrine"](around:{radius_m},{lat},{lon});
      node["memorial"](around:{radius_m},{lat},{lon});
      node["amenity"="place_of_worship"]["name"](around:{radius_m},{lat},{lon});
      way["tourism"="attraction"](around:{radius_m},{lat},{lon});
      way["tourism"="museum"](around:{radius_m},{lat},{lon});
      way["tourism"="gallery"](around:{radius_m},{lat},{lon});
      way["tourism"="artwork"](around:{radius_m},{lat},{lon});
      way["historic"~"monument|castle|church|cathedral|palace|fort|memorial"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def _overpass_landmark_query(lat: float, lon: float, radius_m: int) -> str:
    """
    Second pass: government/civic landmarks often mapped as relations
    without tourism=* (e.g. White House, Smithsonian Institution Building).
    """
    return f"""
    [out:json][timeout:25];
    (
      nwr["building"="government"]["wikipedia"](around:{radius_m},{lat},{lon});
      nwr["office"="government"]["wikipedia"](around:{radius_m},{lat},{lon});
      nwr["building"="civic"]["wikipedia"](around:{radius_m},{lat},{lon});
      nwr["building"="public"]["wikipedia"](around:{radius_m},{lat},{lon});
      nwr["historic"="palace"](around:{radius_m},{lat},{lon});
      relation["tourism"="attraction"](around:{radius_m},{lat},{lon});
      relation["tourism"="museum"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def _overpass_heritage_query(lat: float, lon: float, radius_m: int) -> str:
    """
    Local history pass: statues, civic plazas/parks, and documented historic houses
    that walking tourists expect (Campus Martius, Whitney House, freedom memorials).
    """
    r = min(int(radius_m), 4800)
    return f"""
    [out:json][timeout:25];
    (
      node["tourism"="artwork"]["wikipedia"](around:{r},{lat},{lon});
      way["tourism"="artwork"]["wikipedia"](around:{r},{lat},{lon});
      nwr["leisure"="park"]["wikipedia"](around:{r},{lat},{lon});
      nwr["place"="square"](around:{min(r,3000)},{lat},{lon});
      nwr["historic"="building"]["wikipedia"](around:{r},{lat},{lon});
      nwr["building"]["wikipedia"]["name"~"House|Mansion|Manor|Hall|Homestead",i](around:{r},{lat},{lon});
      nwr["historic"="wayside_shrine"](around:{min(r,2500)},{lat},{lon});
    );
    out center tags;
    """


# Exact / near-exact landmark names tourists expect (avoid matching side offices).
_ICONIC_EXACT = {
    "white house",
    "the white house",
    "united states capitol",
    "us capitol",
    "u.s. capitol",
    "smithsonian institution building",
    "smithsonian castle",
    "the castle",
    "lincoln memorial",
    "jefferson memorial",
    "washington monument",
    "national archives",
    "us national archives",
    "u.s. national archives",
    "national gallery of art",
    "buckingham palace",
    "tower of london",
    "eiffel tower",
    "tour eiffel",
    "arc de triomphe",
    "arc du triomphe",
    "notre-dame de paris",
    "notre dame de paris",
    "cathedral of notre dame",
    "cathedral of notre-dame",
    "cathédrale notre-dame de paris",
    "statue of liberty",
    "colosseum",
    "the colosseum",
    "pantheon",
    "the pantheon",
    "sacré-cœur",
    "sacre-coeur",
    "basilica of the sacred heart of paris",
    "campus martius park",
    "campus martius",
    "gateway to freedom",
    "the spirit of detroit",
    "spirit of detroit",
    "monument to joe louis",
    "david whitney house",
    "whitney mansion",
}

_ICONIC_CONTAINS_RE = re.compile(
    r"("
    r"\bsmithsonian institution\b|"
    r"\bnational museum of\b|"
    r"\bnational air and space museum\b|"
    r"\beiffel tower\b|\btour eiffel\b|"
    r"\barc de triomphe\b|\barc du triomphe\b|"
    r"\bnotre[- ]dame de paris\b|"
    r"\bcathedral of notre[- ]dame\b|"
    r"\bcathédrale notre[- ]dame\b|"
    r"\blouvre\b|\bcolosseum\b|\bpantheon\b|\buffizi\b|"
    r"\bvatican\b|\bsagrada familia\b|\bacropolis\b|"
    r"\bempire state building\b|\bgolden gate bridge\b|"
    r"\bsacré[- ]cœur\b|\bsacre[- ]coeur\b|"
    r"\bcampus martius\b|"
    r"\bunderground railroad\b|\bgateway to freedom\b|"
    r"\bspirit of detroit\b|\bmonument to joe louis\b|"
    r"\bdavid whitney house\b|\bwhitney mansion\b"
    r")",
    re.I,
)

# Local-history subjects walking tourists often expect beyond museums.
_HERITAGE_SUBJECT_RE = re.compile(
    r"("
    r"underground railroad|gateway to freedom|abolition|emancipation|"
    r"\bfounders?(?:\s+(?:memorial|monument|statue|plaza))?\b|"
    r"\bpioneer(?:\s+(?:memorial|monument|statue))?\b|"
    r"\bfirst settler\b|"
    r"campus martius|"
    r"spirit of detroit|joe louis|the fist|"
    r"whitney (house|mansion)|historic (house|mansion|manor|homestead)|"
    r"civil rights|freedom statue|liberty statue|"
    r"soldiers?'? and sailors?'?|"
    r"\bfather of\b|\bcadillac\b"
    r")",
    re.I,
)

_NOISE_NAME_RE = re.compile(
    r"("
    r"peace vigil|carousel|bicycle|bike share|kindergarten|parking|"
    r"pollinator|garden path|tunnel|gift shop|visitor center restroom|"
    r"metro station|\bstation\b|bus stop|atm\b|"
    r"fellowship|conference center|commission on|task force|"
    r"tower tours|treasury of|crypte |pavilion|gustave eiffel's office|"
    r"carrousel de la tour|"
    r"pr[êe]tres du|priests of|hotel de cassini|h[ôo]tel de castries|"
    r"h[ôo]tel de brienne|tribunal de commerce|"
    r"\bone campus martius\b|\bcampus martius station\b|"
    r"\bcooperative\b|\bapartments?\b|\bcondo\b|"
    r"town square cooperative|dte town square"
    r")",
    re.I,
)

# Transit / non-attraction Nominatim classes we never want as walking stops.
_NOMINATIM_SKIP_TYPES = {
    ("railway", "station"),
    ("railway", "halt"),
    ("railway", "tram_stop"),
    ("railway", "subway_entrance"),
    ("highway", "bus_stop"),
    ("amenity", "bus_station"),
    ("public_transport", "station"),
    ("public_transport", "stop_position"),
    ("public_transport", "platform"),
    ("aeroway", "aerodrome"),
    ("shop", "mall"),
    ("office", "company"),
    ("office", "yes"),
}

# Wikipedia geosearch titles that look like local monuments / statues / founders / houses.
_WIKI_HERITAGE_TITLE_RE = re.compile(
    r"("
    r"\bstatue\b|\bmemorial\b|\bmonument\b|\bfountain\b|"
    r"\bmansion\b|\bhomestead\b|\bmanor\b|"
    r"\bfounders?\b|\bpioneer\b|\bsettler\b|"
    r"\bunderground railroad\b|\bgateway to freedom\b|"
    r"\bcivil rights\b|\bemancipation\b|\babolition\b|"
    r"\bplaza\b|\bpublic square\b|\btown square\b|"
    r"campus martius|spirit of detroit|joe louis|whitney house|"
    r"\bhistoric district\b|\bfort\b|\bpalace\b|\bcastillo\b"
    r")",
    re.I,
)


def _is_iconic_name(name: str) -> bool:
    low = name.lower().strip()
    if _NOISE_NAME_RE.search(low):
        return False
    if low in _ICONIC_EXACT:
        return True
    # Avoid office/plaza/station hangers-on of famous names ("Spirit of Detroit Plaza").
    if re.search(
        r"\b(plaza|station|tower|centre|center|apartments?|building|hotel|office)\b",
        low,
    ) and low not in _ICONIC_EXACT:
        # Still allow exact landmark phrases that legitimately include those words.
        if not re.fullmatch(
            r"(the )?(eiffel tower|washington monument|lincoln memorial)",
            low,
        ):
            # Only reject if this is a contains-match hanger-on, not an exact iconic.
            m = _ICONIC_CONTAINS_RE.search(low)
            if m and m.group(0).lower() != low and f"the {m.group(0).lower()}" != low:
                return False
    if _ICONIC_CONTAINS_RE.search(low):
        return True
    # "White House" alone — not "White House Conference Center"
    if re.fullmatch(r"(the )?white house", low):
        return True
    # Bare Notre-Dame / Notre Dame when it's clearly the cathedral (not a side chapel).
    if re.fullmatch(r"(cathedral of )?notre[- ]dame( de paris)?", low):
        return True
    return False


def _poi_score(name: str, tags: dict) -> int:
    """Rank what a walking tourist would actually want to stop for."""
    low = name.lower()
    if _NOISE_NAME_RE.search(low):
        return -50

    score = 0
    tourism = tags.get("tourism")
    historic = (tags.get("historic") or "").lower()
    building = (tags.get("building") or "").lower()
    office = (tags.get("office") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    leisure = (tags.get("leisure") or "").lower()
    place = (tags.get("place") or "").lower()
    artwork = (tags.get("artwork_type") or "").lower()
    memorial = (tags.get("memorial") or "").lower()
    iconic = _is_iconic_name(name)
    heritage_subject = bool(_HERITAGE_SUBJECT_RE.search(low))
    has_wiki = bool(tags.get("wikipedia") or tags.get("wikidata"))

    if tourism == "attraction":
        score += 5
    elif tourism == "museum":
        score += 7  # strong, but should not drown out local monuments
    elif tourism == "gallery":
        score += 5
    elif tourism == "artwork":
        score += 6
    elif tourism == "zoo":
        score += 6

    if historic in ("monument", "castle", "palace", "cathedral", "ruins", "fort"):
        score += 6
    elif building == "cathedral" or (historic == "church" and building == "cathedral"):
        score += 5
    elif historic in ("memorial", "wayside_shrine") or memorial:
        score += 5  # civic memory is a walking-tour staple
    elif historic == "building":
        score += 4
    elif historic == "church":
        score += 2
    elif historic:
        score += 1

    # Statues / public sculpture
    if artwork in ("statue", "sculpture", "bust") or memorial in ("statue", "sculpture", "bust"):
        score += 8
        if has_wiki:
            score += 6

    # Civic parks & squares (Campus Martius) — avoid corporate "Town Square" hangers-on.
    if leisure == "park" and has_wiki:
        score += 10
    if place == "square" or re.search(
        r"\b(public square|town square|plaza mayor|campus martius)\b", low
    ):
        score += 8
        if has_wiki:
            score += 6

    # Documented historic houses / mansions (Whitney House, etc.)
    if has_wiki and re.search(r"\b(house|mansion|manor|homestead|hall)\b", low):
        if historic in ("building", "house", "manor", "yes") or building not in ("", "apartments", "garage"):
            score += 12

    # Cathedrals / triumphal arches are headline tourist stops even when historic=church.
    if building in ("cathedral", "triumphal_arch", "tower") and (has_wiki or iconic):
        score += 14
    if historic == "monument" and has_wiki:
        score += 10

    # Landmark government / civic buildings (White House, Capitol) — not every office=government museum.
    if iconic and (building in ("government", "civic", "public", "palace") or office == "government"):
        score += 18
    elif building == "government" and has_wiki:
        score += 10
    elif building in ("civic", "public") and has_wiki and tourism not in ("museum", "gallery"):
        score += 8

    if tags.get("wikipedia"):
        score += 4
    elif tags.get("wikidata"):
        score += 2
    if tags.get("name:en"):
        score += 1
    if tags.get("heritage") or tags.get("heritage:operator"):
        score += 2

    # Local history subjects: underground railroad, founders, civic icons.
    if heritage_subject:
        score += 20
        if has_wiki or historic in ("monument", "memorial", "building"):
            score += 6

    # Demote street furniture / fountain memorials unless iconic by name.
    if amenity == "fountain" and not iconic and not heritage_subject:
        score -= 8
    if amenity in ("community_centre", "kindergarten", "bicycle_rental"):
        score -= 20
    # Aircraft / odd outdoor exhibits shouldn't beat civic monuments.
    if re.search(r"\b(hawker|hurricane p\d|aircraft|spitfire)\b", low):
        score -= 6
    # Keep walks on the queried city's side when possible (e.g. skip Windsor for Detroit).
    if re.search(r"\bwindsor\b", low) and "detroit" not in low:
        score -= 15

    if iconic:
        score += 28

    # National / Smithsonian museums are what visitors mean by "the Smithsonian".
    if re.search(r"\b(national museum|smithsonian|national gallery|national archives)\b", low):
        score += 10

    return score


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
        score = _poi_score(name.strip(), tags)
        if score < 0:
            continue
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


def _overpass_elements(query: str) -> list:
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                payload = _http_json(endpoint, data=data, timeout=40)
                return payload.get("elements") or []
            except Exception as e:
                last_err = e
                time.sleep(0.8 + attempt)
                continue
    if last_err:
        raise RuntimeError(str(last_err))
    return []


def fetch_pois(
    lat: float,
    lon: float,
    radius_m: int = 1800,
    *,
    include_landmarks: bool = True,
    include_heritage: bool = True,
) -> list[dict]:
    elements: list = []
    last_err: Exception | None = None
    try:
        elements.extend(_overpass_elements(_overpass_tourism_query(lat, lon, radius_m)))
    except Exception as e:
        last_err = e
    # Landmark/government pass is expensive at large radii; keep it for the city core only.
    if include_landmarks and radius_m <= 3600:
        try:
            elements.extend(_overpass_elements(_overpass_landmark_query(lat, lon, radius_m)))
        except Exception as e:
            last_err = e
            # Landmark pass is additive; tourism-only results are still usable.
    # Statues, plazas, and historic houses — key for local-history walking tours.
    if include_heritage:
        try:
            elements.extend(_overpass_elements(_overpass_heritage_query(lat, lon, radius_m)))
        except Exception as e:
            last_err = e
    if not elements:
        raise RuntimeError(
            f"Attraction lookup timed out. Please try again in a moment. ({last_err})"
        )
    return _parse_poi_elements(elements, lat, lon)


def fetch_nominatim_heritage(
    city: str,
    lat: float,
    lon: float,
    radius_m: int = 5000,
) -> list[dict]:
    """
    Seed statues, civic plazas, freedom memorials, and historic houses via Nominatim.
    Overpass often omits leisure=park / building=retail mansions even when Wikipedia-linked.
    """
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(0.25, abs(math.cos(math.radians(lat)))))
    west, east = lon - dlon, lon + dlon
    south, north = lat - dlat, lat + dlat
    viewbox = f"{west},{north},{east},{south}"  # left,top,right,bottom

    city_clean = (city or "").strip()
    # Generic exhaustive queries (any city) + a few high-signal local-history phrases.
    # Prefer "Campus Martius Park" over bare "Campus Martius" (tram stop namesake).
    queries = [
        f"Campus Martius Park {city_clean}",
        f"Gateway to Freedom {city_clean}",
        f"Underground Railroad memorial {city_clean}",
        f"David Whitney House {city_clean}",
        f"Whitney Mansion {city_clean}",
        f"Spirit of Detroit {city_clean}",
        f"Monument to Joe Louis {city_clean}",
        f"founders memorial {city_clean}",
        f"founders monument {city_clean}",
        f"pioneer monument {city_clean}",
        f"historic mansion {city_clean}",
        f"historic house {city_clean}",
        f"statue {city_clean}",
        f"sculpture memorial {city_clean}",
        f"monument {city_clean}",
        f"war memorial {city_clean}",
        f"town square {city_clean}",
        f"public square {city_clean}",
    ]

    pois: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        params = urllib.parse.urlencode(
            {
                "q": q,
                "format": "json",
                "limit": 6,
                "viewbox": viewbox,
                "bounded": 1,
                "extratags": 1,
                "namedetails": 1,
                "accept-language": "en",
            }
        )
        try:
            time.sleep(1.05)
            results = _http_json(f"{NOMINATIM}?{params}", timeout=25)
        except Exception:
            continue
        for r in results or []:
            cls, typ = (r.get("class") or ""), (r.get("type") or "")
            if (cls, typ) in _NOMINATIM_SKIP_TYPES or cls in (
                "railway",
                "highway",
                "public_transport",
                "aeroway",
            ):
                continue
            name = (
                (r.get("namedetails") or {}).get("name")
                or (r.get("display_name") or "").split(",")[0]
            ).strip()
            if not name or len(name) < 2:
                continue
            if _NOISE_NAME_RE.search(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            try:
                plat, plon = float(r["lat"]), float(r["lon"])
            except Exception:
                continue
            dist = haversine_m(lat, lon, plat, plon)
            if dist > radius_m * 1.15:
                continue
            # Skip far-away namesakes / wrong-city hits.
            display = (r.get("display_name") or "").lower()
            if city_clean and city_clean.lower() not in display:
                # Allow clearly relevant heritage names even if city string differs slightly.
                if not _HERITAGE_SUBJECT_RE.search(name) and not _is_iconic_name(name):
                    continue
            extras = r.get("extratags") or {}
            tags = {
                **extras,
                "name": name,
                "name:en": name,
            }
            # Map Nominatim class/type into OSM-like tags when missing.
            if cls == "tourism" and not tags.get("tourism"):
                tags["tourism"] = typ
            if cls == "historic" and not tags.get("historic"):
                tags["historic"] = typ
            if cls == "leisure" and not tags.get("leisure"):
                tags["leisure"] = typ
            if cls == "building" and not tags.get("building"):
                tags["building"] = typ or "yes"
            if cls == "place" and not tags.get("place"):
                tags["place"] = typ
            # Prefer park article over office/station namesakes for scoring.
            if "park" in typ or tags.get("leisure") == "park":
                tags.setdefault("leisure", "park")
            score = _poi_score(name, tags)
            # Nominatim heritage seeds are intentionally boosted into consideration.
            if _HERITAGE_SUBJECT_RE.search(name) or _is_iconic_name(name):
                score += 8
            if score < 0:
                continue
            seen.add(key)
            pois.append(
                {
                    "name": name,
                    "lat": plat,
                    "lng": plon,
                    "tags": tags,
                    "score": score,
                    "dist": dist,
                }
            )
    pois.sort(key=lambda p: (-p["score"], p["dist"]))
    return pois


def fetch_wikipedia_nearby_heritage(
    lat: float,
    lon: float,
    radius_m: int = 6000,
) -> list[dict]:
    """
    Exhaustive local-history pass: Wikipedia pages near the city center whose
    titles look like monuments, statues, memorials, founders, or historic houses.
    Catches places Overpass/Nominatim miss or mis-tag.
    """
    radius = max(1000, min(int(radius_m), 10000))
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": str(radius),
            "gslimit": "80",
            "format": "json",
        }
    )
    try:
        data = _http_json(f"{WIKI_API}?{params}", timeout=25)
    except Exception as e:
        print("wikipedia geosearch failed", e)
        return []

    pois: list[dict] = []
    seen: set[str] = set()
    for item in data.get("query", {}).get("geosearch") or []:
        title = (item.get("title") or "").strip()
        if not title or title in seen:
            continue
        if _NOISE_NAME_RE.search(title):
            continue
        # Keep heritage-shaped titles, plus anything already treated as iconic.
        if not (_WIKI_HERITAGE_TITLE_RE.search(title) or _is_iconic_name(title) or _HERITAGE_SUBJECT_RE.search(title)):
            continue
        try:
            plat, plon = float(item["lat"]), float(item["lon"])
        except Exception:
            continue
        dist = float(item.get("dist") or haversine_m(lat, lon, plat, plon))
        if dist > radius * 1.05:
            continue
        tags = {
            "name": title,
            "name:en": title,
            "wikipedia": f"en:{title}",
        }
        # Infer a light historic/artwork tag from the title for scoring.
        low = title.lower()
        if re.search(r"\b(statue|sculpture|bust)\b", low):
            tags["tourism"] = "artwork"
            tags["artwork_type"] = "statue"
        elif re.search(r"\b(memorial|monument)\b", low):
            tags["historic"] = "monument"
        elif re.search(r"\b(mansion|homestead|manor)\b", low) or re.search(
            r"\b\w+ house\b", low
        ):
            tags["historic"] = "building"
            tags["building"] = "yes"
        elif re.search(r"\b(park|plaza|square)\b", low):
            tags["leisure"] = "park" if "park" in low else tags.get("leisure", "")
            if "square" in low or "plaza" in low:
                tags["place"] = "square"
        score = _poi_score(title, tags)
        if _HERITAGE_SUBJECT_RE.search(title) or _is_iconic_name(title):
            score += 6
        if score < 4:
            continue
        seen.add(title)
        pois.append(
            {
                "name": title,
                "lat": plat,
                "lng": plon,
                "tags": tags,
                "score": score,
                "dist": dist,
            }
        )
    pois.sort(key=lambda p: (-p["score"], p["dist"]))
    return pois


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


def _osm_wiki_title(tags: dict) -> str | None:
    """Prefer the linked English Wikipedia article from OSM tags."""
    for key in ("wikipedia", "wikipedia:en"):
        val = (tags.get(key) or "").strip()
        if not val:
            continue
        if ":" in val:
            lang, title = val.split(":", 1)
            if lang.lower() == "en" and title.strip():
                return title.strip().replace("_", " ")
        else:
            return val.replace("_", " ")
    return None


def _wikidata_qid(tags: dict, summary: dict | None = None) -> str | None:
    qid = (tags.get("wikidata") or "").strip()
    if qid.startswith("Q"):
        return qid
    if summary and summary.get("wikibase_item"):
        return summary["wikibase_item"]
    return None


def _format_wikidata_time(value: dict) -> str | None:
    """Turn a Wikidata time claim into a spoken year / date."""
    raw = (value or {}).get("time") or ""
    # +1922-05-30T00:00:00Z
    m = re.match(r"([+-])(\d+)-(\d{2})-(\d{2})", raw)
    if not m:
        return None
    sign, year_s, month_s, day_s = m.groups()
    year = int(year_s) * (1 if sign == "+" else -1)
    if year <= 0:
        return f"{abs(year) + 1} BCE" if year < 0 else None
    precision = int((value or {}).get("precision") or 9)
    month = int(month_s)
    day = int(day_s)
    months = (
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    if precision >= 11 and month and day:
        return f"{months[month]} {day}, {year}"
    if precision >= 10 and month:
        return f"{months[month]} {year}"
    return str(year)


def _wikidata_label(qid: str) -> str | None:
    if not qid or not qid.startswith("Q"):
        return None
    if qid in _label_cache:
        return _label_cache[qid]
    try:
        time.sleep(0.05)
        q = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": qid,
                "props": "labels",
                "languages": "en",
                "format": "json",
            }
        )
        data = _http_json(f"{WIKIDATA_LABEL}?{q}", timeout=12)
        label = (
            data.get("entities", {})
            .get(qid, {})
            .get("labels", {})
            .get("en", {})
            .get("value")
        )
        if label:
            _label_cache[qid] = label
            return label
    except Exception:
        return None
    return None


def _claim_values(claims: dict, pid: str) -> list:
    out = []
    for c in (claims.get(pid) or [])[:4]:
        snak = c.get("mainsnak") or {}
        dv = snak.get("datavalue") or {}
        if "value" in dv:
            out.append(dv["value"])
    return out


def fetch_wikidata_facts(qid: str) -> dict:
    """Structured tourist facts: when built/dedicated, architect, style."""
    facts: dict = {}
    if not qid:
        return facts
    try:
        time.sleep(0.1)
        data = _http_json(WIKIDATA_ENTITY.format(qid=qid), timeout=15)
        ent = (data.get("entities") or {}).get(qid) or {}
        claims = ent.get("claims") or {}
    except Exception:
        return facts

    # Prefer opening/dedication date, then inception / construction
    for pid, key in (
        ("P1619", "opened"),
        ("P571", "built"),
        ("P580", "started"),
        ("P577", "published"),
    ):
        for val in _claim_values(claims, pid):
            if isinstance(val, dict) and "time" in val:
                formatted = _format_wikidata_time(val)
                if formatted:
                    facts[key] = formatted
                    break
        if key in facts:
            break

    architects = []
    for val in _claim_values(claims, "P84"):
        if isinstance(val, dict) and val.get("id"):
            label = _wikidata_label(val["id"])
            if label:
                architects.append(label)
    if architects:
        facts["architect"] = ", ".join(architects[:2])

    creators = []
    for val in _claim_values(claims, "P170"):
        if isinstance(val, dict) and val.get("id"):
            label = _wikidata_label(val["id"])
            if label and label not in architects:
                creators.append(label)
    if creators:
        facts["creator"] = ", ".join(creators[:2])

    for val in _claim_values(claims, "P149"):
        if isinstance(val, dict) and val.get("id"):
            label = _wikidata_label(val["id"])
            if label:
                facts["style"] = label
                break

    for val in _claim_values(claims, "P2048"):  # height
        if isinstance(val, dict) and "amount" in val:
            try:
                amount = float(val["amount"].lstrip("+"))
                unit = val.get("unit", "")
                # metres entity Q11573
                if amount >= 3:
                    if unit.endswith("Q11573") or "metre" in unit.lower():
                        facts["height"] = f"{int(round(amount))} meters"
                    else:
                        facts["height"] = f"{int(round(amount))} units tall"
            except Exception:
                pass
            break

    return facts


def facts_from_osm(tags: dict) -> dict:
    facts: dict = {}
    start = tags.get("start_date") or tags.get("year_of_construction") or tags.get("building:year")
    if start:
        # OSM often uses 1922 or 1922-05-30
        m = re.match(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", str(start).strip())
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            months = (
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )
            if d and mo:
                facts["built"] = f"{months[int(mo)]} {int(d)}, {y}"
            elif mo:
                facts["built"] = f"{months[int(mo)]} {y}"
            else:
                facts["built"] = y
        else:
            facts["built"] = str(start).strip()
    if tags.get("architect"):
        facts["architect"] = tags["architect"]
    if tags.get("architect:name"):
        facts["architect"] = tags["architect:name"]
    if tags.get("heritage") or tags.get("heritage:operator"):
        facts["heritage"] = tags.get("heritage:operator") or "protected heritage site"
    return facts


def _split_sentences(text: str) -> list[str]:
    """Split on sentence ends without breaking common abbreviations (U.S., Dr., etc.)."""
    protected = text
    repl = {
        "U.S.": "U\u200bS\u200b",
        "U.S.A.": "U\u200bS\u200bA\u200b",
        "D.C.": "D\u200bC\u200b",
        "Dr.": "Dr\u200b",
        "Mr.": "Mr\u200b",
        "Mrs.": "Mrs\u200b",
        "Ms.": "Ms\u200b",
        "St.": "St\u200b",
        "Mt.": "Mt\u200b",
        "No.": "No\u200b",
        "Gen.": "Gen\u200b",
        "Jr.": "Jr\u200b",
        "Sr.": "Sr\u200b",
    }
    for a, b in repl.items():
        protected = protected.replace(a, b)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", protected) if p.strip()]
    return [p.replace("\u200b", ".") for p in parts]


def _trim_extract(extract: str, max_sentences: int = 6, max_chars: int = 1100) -> str:
    parts = _split_sentences(extract)
    # Drop boilerplate / see-also style tails
    cleaned = []
    for p in parts:
        low = p.lower()
        if low.startswith("coordinates ") or low.startswith("this article"):
            continue
        # Drop orphan fragments without a verb (common in wiki intros)
        if len(p) < 40 and not re.search(r"\b(is|was|are|were|has|had|built|opened|dedicated)\b", low):
            continue
        cleaned.append(p)
    if not cleaned:
        return ""
    # Prefer an opening sentence plus sentences that carry dates / people / design.
    def _score(s: str) -> int:
        low = s.lower()
        score = 0
        if re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", s):
            score += 5
        if any(w in low for w in ("built", "dedicat", "complet", "opened", "construct", "design", "architect")):
            score += 3
        if any(w in low for w in ("statue", "marble", "museum", "memorial", "cathedral", "commission")):
            score += 1
        return score

    keep = [cleaned[0]]
    ranked = sorted(enumerate(cleaned[1:], start=1), key=lambda iv: (-_score(iv[1]), iv[0]))
    for _, sentence in ranked:
        if sentence in keep:
            continue
        keep.append(sentence)
        if len(keep) >= max_sentences:
            break
    # Restore original order for a natural read
    order = {s: i for i, s in enumerate(cleaned)}
    keep.sort(key=lambda s: order.get(s, 99))
    text = " ".join(keep).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return text


def fetch_place_story(name: str, city: str, tags: dict) -> dict:
    """
    Gather a longer Wikipedia extract + structured when/who/style facts.
    Returns {extract, facts, title, qid}.
    """
    titles = []
    osm_title = _osm_wiki_title(tags)
    if osm_title:
        titles.append(osm_title)
    titles.extend(
        [
            name,
            f"{name} ({city})",
            f"{name}, {city}",
            f"{name} ({city} {tags.get('historic') or tags.get('tourism') or ''})".strip(),
        ]
    )
    # De-dupe while preserving order
    seen = set()
    uniq_titles = []
    for t in titles:
        key = t.lower()
        if t and key not in seen:
            seen.add(key)
            uniq_titles.append(t)

    summary = None
    title_used = None
    for title in uniq_titles:
        slug = urllib.parse.quote(title.replace(" ", "_"), safe="")
        try:
            time.sleep(0.12)
            data = _http_json(WIKI + slug, timeout=12)
        except Exception:
            continue
        if data.get("type") == "disambiguation":
            continue
        extract = (data.get("extract") or "").strip()
        if extract and len(extract) > 40:
            summary = data
            title_used = data.get("title") or title
            break

    extract_text = ""
    qid = _wikidata_qid(tags, summary)
    if summary:
        extract_text = _trim_extract(summary.get("extract") or "")
        # Always try the fuller intro extract — REST summaries often omit dedication/build lines.
        if title_used:
            try:
                q = urllib.parse.urlencode(
                    {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "redirects": 1,
                        "titles": title_used,
                        "format": "json",
                    }
                )
                time.sleep(0.12)
                page_data = _http_json(f"{WIKI_API}?{q}", timeout=15)
                page = next(iter((page_data.get("query") or {}).get("pages", {}).values()))
                longer = (page.get("extract") or "").strip()
                if longer:
                    trimmed = _trim_extract(longer)
                    # Prefer the version that keeps calendar years / build verbs.
                    def _richness(t: str) -> int:
                        return len(re.findall(r"\b(1[0-9]{3}|20[0-2][0-9])\b", t)) + (
                            2 if re.search(r"dedicat|built|architect|complet", t, re.I) else 0
                        )

                    if _richness(trimmed) >= _richness(extract_text) and len(trimmed) >= len(extract_text) * 0.8:
                        extract_text = trimmed
            except Exception:
                pass

    facts = facts_from_osm(tags)
    wd_facts = fetch_wikidata_facts(qid) if qid else {}
    # Wikidata wins on structured fields when present
    for k, v in wd_facts.items():
        if v:
            facts[k] = v

    return {
        "title": title_used,
        "qid": qid,
        "extract": extract_text or None,
        "facts": facts,
    }


def _fact_sentences(facts: dict, *, memorial: bool = False) -> list[str]:
    """Turn structured facts into spoken lines."""
    lines = []
    def _prep(date: str) -> str:
        """Year-only → 'in 1885'; full dates → 'on May 30, 1922'."""
        return "in" if re.fullmatch(r"\d{4}", date or "") else "on"

    built = facts.get("built") or facts.get("started")
    opened = facts.get("opened")
    # Day-level memorial dates from Wikidata inception are usually dedications.
    day_level = bool(built and re.search(r"[A-Za-z]+ \d+, \d{4}", built or ""))
    if built and opened and built != opened:
        lines.append(f"Construction dates to {built}; it opened {_prep(opened)} {opened}.")
    elif opened:
        lines.append(f"It opened {_prep(opened)} {opened}.")
    elif built and (memorial or day_level):
        lines.append(f"It was dedicated {_prep(built)} {built}.")
    elif built:
        lines.append(f"It was built {_prep(built)} {built}.")
    if facts.get("architect"):
        arch = facts["architect"].rstrip(".")
        lines.append(f"The architect was {arch}.")
    if facts.get("creator") and facts.get("creator") != facts.get("architect"):
        lines.append(f"Key artwork here is by {facts['creator']}.")
    style = facts.get("style")
    if style:
        style = re.sub(r"\s+architecture$", "", style, flags=re.I)
        lines.append(f"The style is {style}.")
    if facts.get("height"):
        lines.append(f"It rises about {facts['height']}.")
    return lines


def build_script(name: str, city: str, tags: dict, story: dict) -> list[str]:
    kind = tags.get("historic") or tags.get("tourism") or tags.get("amenity") or "landmark"
    kind = str(kind).replace("_", " ")
    facts = story.get("facts") or {}
    extract = story.get("extract") or ""
    memorial = str(tags.get("historic") or "").lower() in ("memorial", "monument") or "memorial" in name.lower()

    paras = [f"You are at {name} in {city}."]

    # Lead with concrete when/who facts so tourists always hear the specifics.
    fact_lines = _fact_sentences(facts, memorial=memorial)
    filtered = []
    extract_l = extract.lower()
    for line in fact_lines:
        low = line.lower()
        year_m = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", line)
        if year_m and year_m.group(1) in extract:
            if any(w in extract_l for w in ("dedicat", "built", "complet", "opened", "dates to", "construction")):
                continue
        arch = facts.get("architect")
        if arch and arch.lower() in extract_l and "architect" in low:
            continue
        creator = facts.get("creator")
        if creator and creator.lower() in extract_l and ("artwork" in low or "associated" in low):
            continue
        style = facts.get("style") or ""
        style_core = re.sub(r"\s+architecture$", "", style, flags=re.I).lower()
        if style_core and style_core in extract_l and "style" in low:
            continue
        if "neoclassical" in extract_l and "greek revival" in low:
            continue
        filtered.append(line)
    if filtered:
        paras.append(" ".join(filtered))

    if extract:
        paras.append(extract)
    elif not filtered:
        paras.append(
            f"This {kind} is one of the places visitors seek out here. Look for plaques, dates carved in stone, and the details of how it was made."
        )
    else:
        paras.append("Take a moment to look at the materials, inscriptions, and views that make this stop distinctive.")

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


def _name_family(name: str) -> str:
    """Collapse near-duplicate attractions (Louvre Museum / Pyramid / Palace)."""
    low = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    for stem in (
        "louvre",
        "eiffel",
        "notre dame",
        "arc de triomphe",
        "smithsonian",
        "white house",
        "washington monument",
        "lincoln memorial",
        "pantheon",
        "orsay",
        "sacre coeur",
        "sacr coeur",
        "sacred heart",
        "invalides",
        "joe louis",
        "spirit of detroit",
        "gateway to freedom",
        "campus martius",
        "whitney",
    ):
        # Normalize accents for family matching
        norm = (
            low.replace("é", "e")
            .replace("è", "e")
            .replace("ê", "e")
            .replace("ô", "o")
            .replace("ç", "c")
        )
        if stem in norm or stem in low:
            return stem.replace(" ", "_")
    # First two significant tokens
    parts = [p for p in low.split() if p not in {"the", "of", "de", "du", "la", "le", "des", "national", "museum"}]
    return " ".join(parts[:2]) if parts else low


def _too_close_duplicate(candidate: dict, selected: list[dict], min_m: float = 220) -> bool:
    """Skip a stop if we already picked a same-family site nearby."""
    fam = _name_family(candidate["name"])
    for s in selected:
        if _name_family(s["name"]) != fam:
            continue
        if haversine_m(candidate["lat"], candidate["lng"], s["lat"], s["lng"]) < min_m:
            return True
        # Same family even a bit farther (Louvre cluster spans ~200–400m;
        # Detroit civic icons also cluster within a few blocks).
        if fam in {
            "louvre",
            "notre_dame",
            "eiffel",
            "smithsonian",
            "spirit_of_detroit",
            "joe_louis",
            "gateway_to_freedom",
            "campus_martius",
            "whitney",
        } and haversine_m(
            candidate["lat"], candidate["lng"], s["lat"], s["lng"]
        ) < 550:
            return True
    return False


def _pick_tour_stops(pois: list[dict], stop_count: int) -> list[dict]:
    """
    Prefer world-famous landmarks and local heritage (statues, plazas, historic
    houses), then diversify museum/monument/civic — don't let museums fill every slot.
    """
    if len(pois) <= stop_count:
        return list(pois)

    def _category(p: dict) -> str:
        tags = p.get("tags") or {}
        name = p["name"].lower()
        artwork = (tags.get("artwork_type") or "").lower()
        memorial = (tags.get("memorial") or "").lower()
        hist = (tags.get("historic") or "").lower()
        building = (tags.get("building") or "").lower()
        leisure = (tags.get("leisure") or "").lower()
        place = (tags.get("place") or "").lower()

        if _HERITAGE_SUBJECT_RE.search(name) or tags.get("tourism") == "artwork" or artwork in (
            "statue",
            "sculpture",
            "bust",
        ):
            return "heritage"
        if hist in ("memorial", "monument") or memorial:
            return "heritage"
        if leisure == "park" and (tags.get("wikipedia") or "campus martius" in name):
            return "heritage"
        if place == "square" or re.search(r"\b(public square|town square|plaza mayor)\b", name):
            return "heritage"
        if tags.get("wikipedia") and re.search(r"\b(house|mansion|manor|homestead)\b", name):
            return "heritage"
        if tags.get("tourism") in ("museum", "gallery") or "smithsonian" in name or "national museum" in name:
            return "museum"
        if hist in ("palace", "castle", "cathedral") or building in (
            "cathedral",
            "triumphal_arch",
            "tower",
        ):
            return "monument"
        if re.fullmatch(r"(the )?white house", name) or "capitol" in name:
            return "civic"
        if tags.get("building") == "government" and _is_iconic_name(p["name"]):
            return "civic"
        if tags.get("tourism") == "attraction":
            return "attraction"
        return "other"

    selected: list[dict] = []
    seen = set()

    def _add(p: dict) -> bool:
        if p["name"] in seen or _too_close_duplicate(p, selected):
            return False
        selected.append(p)
        seen.add(p["name"])
        return True

    # 1) Force world-famous names into the tour whenever mapped nearby.
    iconics = [p for p in pois if _is_iconic_name(p["name"])]
    iconic_slots = min(len(iconics), max(3, stop_count // 2 + 1))
    for p in iconics:
        if len(selected) >= iconic_slots:
            break
        _add(p)

    # 2) Seed local heritage early (statues / plazas / historic houses / freedom memorials).
    heritage_slots = min(
        sum(1 for p in pois if _category(p) == "heritage"),
        max(2, stop_count // 3),
    )
    for p in pois:
        if len([s for s in selected if _category(s) == "heritage"]) >= heritage_slots:
            break
        if _category(p) == "heritage":
            _add(p)

    # 3) Seed remaining category diversity.
    for want in ("civic", "museum", "monument"):
        if len(selected) >= stop_count:
            break
        for p in pois:
            if _category(p) == want and _add(p):
                break

    # 4) Fill by score, but cap museums so heritage keeps room on long tours.
    museum_cap = max(3, stop_count // 2) if stop_count >= 8 else stop_count
    for p in pois:
        if len(selected) >= stop_count:
            break
        if _category(p) == "museum":
            museum_count = sum(1 for s in selected if _category(s) == "museum")
            if museum_count >= museum_cap:
                continue
        _add(p)

    # If dedupe/caps left us short, relax and fill.
    if len(selected) < stop_count:
        for p in pois:
            if len(selected) >= stop_count:
                break
            if p["name"] in seen:
                continue
            selected.append(p)
            seen.add(p["name"])

    return selected[:stop_count]


def _write_stop_audio(pack: dict, stop: dict, media_rel: str, media_dir: Path) -> bool:
    """Synthesize one stop's MP3 and mutate stop fields. Returns True on success."""
    if stop.get("audioUrl"):
        return False
    narration = " ... ".join(stop.get("script") or [])
    if not narration.strip():
        return False
    dest = media_dir / f"{stop['id']}.mp3"
    duration = synthesize_audio(narration, dest)
    if not duration:
        return False
    stop["durationSec"] = duration
    stop["audioUrl"] = f"/media/{media_rel}/audio/{stop['id']}.mp3"
    return True


def fill_pack_audio(tour_id: str, *, skip_existing: bool = True) -> None:
    """Synthesize TTS for an already-saved pack (used in a background thread)."""
    path = GEN_DIR / f"{tour_id}.json"
    if not path.exists():
        return
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print("fill_pack_audio load failed", tour_id, e)
        return
    media_rel = f"generated/{tour_id}"
    media_dir = MEDIA_GEN / tour_id / "audio"
    media_dir.mkdir(parents=True, exist_ok=True)
    changed = False
    for stop in pack.get("stops") or []:
        if skip_existing and stop.get("audioUrl"):
            continue
        try:
            if _write_stop_audio(pack, stop, media_rel, media_dir):
                changed = True
                path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print("TTS bg failed for", stop.get("name"), e)
    if changed:
        path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    print("fill_pack_audio done", tour_id)


def prime_pack_audio(tour_id: str, count: int = 1) -> int:
    """Synchronously synthesize the first N stops so play works immediately."""
    path = GEN_DIR / f"{tour_id}.json"
    if not path.exists():
        return 0
    pack = json.loads(path.read_text(encoding="utf-8"))
    media_rel = f"generated/{tour_id}"
    media_dir = MEDIA_GEN / tour_id / "audio"
    media_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for stop in (pack.get("stops") or [])[: max(0, count)]:
        try:
            if _write_stop_audio(pack, stop, media_rel, media_dir):
                done += 1
        except Exception as e:
            print("TTS prime failed for", stop.get("name"), e)
    if done:
        path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    return done


def generate_pack(
    place_query: str,
    stop_count: int,
    *,
    with_audio: bool = True,
    radius_m: int = 2200,
) -> dict:
    stop_count = max(3, min(int(stop_count), 12))
    geo = geocode(place_query)
    city = geo["name"]
    # One primary wide ring (fast). Widen once only if famous landmarks are missing.
    # Eiffel/Arc sit ~4–4.5km from Paris center — need ≥5km for big stop counts.
    if stop_count >= 10:
        primary = max(radius_m, 5200)
        widen_to = 7000
    elif stop_count >= 6:
        primary = max(radius_m, 4200)
        widen_to = 6000
    else:
        primary = max(radius_m, 2800)
        widen_to = 4800

    merged: dict[str, dict] = {}
    last_err: Exception | None = None

    def _absorb(batch: list[dict]) -> None:
        for p in batch:
            key = p["name"].strip().lower()
            prev = merged.get(key)
            if prev is None or p["score"] > prev["score"]:
                merged[key] = p

    try:
        _absorb(
            fetch_pois(
                geo["lat"],
                geo["lon"],
                radius_m=primary,
                include_landmarks=primary <= 3600,
            )
        )
    except RuntimeError as e:
        last_err = e

    iconic_hits = sum(1 for p in merged.values() if _is_iconic_name(p["name"]))
    if iconic_hits < 3 or len(merged) < max(stop_count, 8):
        try:
            _absorb(
                fetch_pois(
                    geo["lat"],
                    geo["lon"],
                    radius_m=widen_to,
                    include_landmarks=False,
                )
            )
        except RuntimeError as e:
            last_err = e

    # Nominatim + Wikipedia heritage seeds fill gaps Overpass misses
    # (parks, mansions, named memorials, statues, founders).
    try:
        _absorb(
            fetch_nominatim_heritage(
                city,
                geo["lat"],
                geo["lon"],
                radius_m=max(primary, 5000),
            )
        )
    except Exception as e:
        print("nominatim heritage seed failed", e)
    try:
        _absorb(
            fetch_wikipedia_nearby_heritage(
                geo["lat"],
                geo["lon"],
                radius_m=max(primary, 6000),
            )
        )
    except Exception as e:
        print("wikipedia heritage seed failed", e)

    pois = sorted(merged.values(), key=lambda p: (-p["score"], p["dist"]))
    if len(pois) < 3:
        raise ValueError(
            f"Not enough mapped attractions near “{place_query}”. Try a larger city or a well-known historic center."
            + (f" ({last_err})" if last_err and not merged else "")
        )

    # Pick the best-scored landmarks (iconics first), then order a walk.
    must_see = _pick_tour_stops(pois, stop_count)
    chosen = nearest_neighbor_order(must_see, geo["lat"], geo["lon"])

    tour_id = f"ondemand-{slugify(city)}-{stop_count}-{int(time.time())}"
    media_rel = f"generated/{tour_id}"
    media_dir = MEDIA_GEN / tour_id / "audio"
    media_dir.mkdir(parents=True, exist_ok=True)

    stops = []
    for i, poi in enumerate(chosen, start=1):
        story = fetch_place_story(poi["name"], city, poi["tags"])
        script = build_script(poi["name"], city, poi["tags"], story)
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
                "facts": story.get("facts") or {},
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
        "mapZoom": 14 if stop_count < 10 else 13,
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
