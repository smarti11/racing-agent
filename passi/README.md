# Passi MVP

English walking-tour sessions with temporary links.

## What it is

- **Catalog** of English tours: Florence Classic, Rome Lateran→Farnese, Corniglia
- **Session API** — `POST /api/sessions` creates a 48h token URL `/t/{token}`
- **Unified player** — map, GPS unlock, tap-to-play, scripts, photos (Florence)
- **Locale** — English only in MVP (`locale: "en"`)

## Run

```bash
cd passi
python3 server.py
# http://127.0.0.1:8100/
```

Create a session:

```bash
curl -s -X POST http://127.0.0.1:8100/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"tourId":"florence-classic-en","locale":"en","ttlHours":48}'
```

Open the returned `url` (e.g. `/t/abc123…`) on a phone.

## Layout

```
passi/
  server.py           # catalog + sessions + static
  catalog.json
  packs/*.json        # tour packs (locale=en)
  media/{city}/audio  # TTS MP3s
  media/florence/images
  static/             # landing + player PWA shell
  data/sessions.db    # created at runtime
```

## Next

- Deploy behind a stable domain (not agent tunnels)
- Italian / ES / DE / FR packs (see store `audio-languages-roadmap.md`)
- Nearby generator + restaurant sponsorships
