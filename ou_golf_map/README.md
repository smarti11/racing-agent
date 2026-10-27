# OU Golf Map

GPS-aware map for Oakland University Golf & Learning Center:

- **Katke-Cousins** (18 holes)
- **R&S Sharf** (18 holes)

## Features

- Satellite basemap with labeled holes 1–18 per course
- Toggle Katke / Sharf / fairways & greens / **maintenance & cart paths**
- Live **GPS presence** (watch position + accuracy ring)
- Tap a hole number to zoom to that hole (par + black-tee yardage)

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
