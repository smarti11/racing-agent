# OU Golf Map

GPS-aware map for Oakland University Golf & Learning Center:

- **Katke-Cousins** (18 holes)
- **R&S Sharf** (18 holes)

## Features

- Satellite basemap with labeled holes 1–18 per course
- Toggle Katke / Sharf / fairways & greens / **maintenance & cart paths**
- Live **GPS presence** (watch position + accuracy ring)
- Live **wind** on the map: speed, the direction it is coming from, humidity, and, once a hole is selected, whether that wind is into you or helping. The reading is the latest observation from Pontiac airport, the National Weather Service station nearest the course, and it refreshes while the map is open.
- **Yardage curves** on the selected hole: a thin red line at 100 yards from the middle of the green, white at 150, and blue at 200. A curve that would fall behind the tee is left off. Reset clears them
- **Breaks** on each green: a slope picture and arrows showing which way a ball rolls. Drag the ball and the flag and a gold line shows the putt that finishes in the hole, bent by the slope, plus how far left or right to start it. Built from the free USGS 3DEP 1-meter elevation, which comes from the 2016 Oakland County lidar scan. The read is the general fall of the green. A small break can be finer than that scan.
- Tap a hole number to zoom to that hole (par + black-tee yardage), then **Fly over** to zoom in and follow that hole from the tee to the green. Stop, pick another hole, or drag the map to cancel. **Reset** clears the selected hole on either course and zooms back out. Scores stay saved.
- **Front, center, and back** of the green from your GPS, in one short bar. Tap the map to measure to a bunker or a layup. **Center** puts the number back on the middle of the green.
- **Scorecard** for the course you are playing. Katke-Cousins and R&S Sharf each have their own holes and totals; the other course stays hidden until you switch. Each hole shows its handicap (men's or women's, from the Oakland University card). Pick the tee (Black through Silver) to see that tee's yardage and a **plays-like** yardage: one yard added for every three feet the green sits above the tee, and one yard subtracted for every three feet it sits below. Elevations are from USGS 3DEP at the mapped tee and green. Tap a hole, then say the strokes ("five", "birdie", "one over") or type them. Out is holes 1–9, In is holes 10–18, and **18 holes** is the full round. Scores stay in this browser until you tap Clear. **Save this score**, under that course, opens the phone share sheet so the card can be kept in Files or Notes. The microphone needs Safari or Chrome, and HTTPS or localhost.

## Data sources

- Hole lines, greens, fairways, tees, pins, cart paths: [OpenStreetMap](https://www.openstreetmap.org/) contributors
- Scorecard yardages / par: [oakland.edu/golf](https://www.oakland.edu/golf/courses/)
- Imagery: Esri World Imagery
- Wind: [National Weather Service](https://www.weather.gov/) observation at Pontiac airport (KPTK)
- Green breaks: [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) 1-meter elevation from the 2016 Oakland County lidar (quality level 2)

Hole-to-course assignment uses OSM tags plus scorecard pars; a few holes may need field verification.

## Run locally

```bash
cd ou_golf_map
python3 -m http.server 8091
```

Open `http://localhost:8091` (GPS needs HTTPS or localhost).

## Deploy

Upload the files inside `ou_golf_map/` to the existing Cloudflare Worker (`tiny-thunder-291b`) with **New deployment**. Drag the files themselves so `index.html`, `app.js`, and the `.geojson` files are side by side. Cloudflare does not keep a `data` folder, and the map loads those course files from next to `index.html`.
