# OU Golf Map

GPS-aware map for Oakland University Golf & Learning Center:

- **Katke-Cousins** (18 holes)
- **R&S Sharf** (18 holes)

## Features

- Satellite basemap with labeled holes 1–18 per course
- Toggle Katke / Sharf / fairways & greens / **maintenance & cart paths**
- Live **GPS presence** (watch position + accuracy ring)
- Tap a hole number to zoom to that hole (par + black-tee yardage)
- **Live yards to green** from your GPS when a hole is selected (updates as you walk; dashed aim line to the green)
- **Scorecard** for each course. Tap a hole, then say the strokes ("five", "birdie", "one over") or type them. Out is holes 1–9, In is holes 10–18, then the round total. Scores stay in this browser until you tap Clear. The microphone needs Safari or Chrome, and HTTPS or localhost.

## Data sources

- Hole lines, greens, fairways, tees, pins, cart paths: [OpenStreetMap](https://www.openstreetmap.org/) contributors
- Scorecard yardages / par: [oakland.edu/golf](https://www.oakland.edu/golf/courses/)
- Imagery: Esri World Imagery

Hole-to-course assignment uses OSM tags plus scorecard pars; a few holes may need field verification.

## Run locally

```bash
cd ou_golf_map
python3 -m http.server 8091
```

Open `http://localhost:8091` (GPS needs HTTPS or localhost).

## Deploy

Upload the whole `ou_golf_map/` folder (including `data/`) to Cloudflare Pages / Workers static assets, same way as Tee Align.
