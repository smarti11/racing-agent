# Passi MVP

On-demand English walking tours with temporary phone links.

## What it is

- **On-demand** — tourist names a city/region and chooses **3–12** locations of interest
- **Generate API** — `POST /api/generate` geocodes the place, finds nearby attractions (OpenStreetMap), orders a walk, narrates English TTS, returns a 48h session URL
- **Catalog fallback** — Florence Classic, Rome Lateran→Farnese, Corniglia still available as ready-made packs
- **Unified player** — map, GPS unlock, tap-to-play, written scripts
- **Locale** — English only in MVP (`locale: "en"`)

## Run

```bash
cd passi
python3 server.py
# http://127.0.0.1:8100/
```

### On-demand tour

```bash
curl -s -X POST http://127.0.0.1:8100/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"place":"Siena Italy","stopCount":6,"ttlHours":48,"withAudio":true}'
```

Open the returned `url` (e.g. `/t/abc123…`) on a phone.

### Ready-made catalog session

```bash
curl -s -X POST http://127.0.0.1:8100/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"tourId":"florence-classic-en","locale":"en","ttlHours":48}'
```

## Layout

```
passi/
  server.py              # sessions + generate + static
  generate.py            # geocode → Overpass POIs → wiki → TTS pack
  catalog.json
  packs/*.json           # curated packs (locale=en)
  packs/generated/       # on-demand packs (runtime, gitignored)
  media/{city}/audio     # curated TTS MP3s
  media/generated/       # on-demand TTS (runtime, gitignored)
  static/                # landing (city + stop count) + player
  data/sessions.db       # created at runtime
```

## Next

- Deploy behind a stable domain (not agent tunnels)
- Italian / ES / DE / FR packs (see store `audio-languages-roadmap.md`)
- Restaurant sponsorships (see store `local-business-marketplace.md`)
